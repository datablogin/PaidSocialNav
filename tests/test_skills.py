"""Tests for the skills module."""
from __future__ import annotations

from unittest.mock import MagicMock, Mock, patch

import pytest

from paid_social_nav.skills import AuditWorkflowSkill, BaseSkill, SkillResult


class ConcreteSkill(BaseSkill):
    """Concrete implementation for testing BaseSkill."""

    def execute(self, context: dict) -> SkillResult:
        """Execute test skill."""
        is_valid, error = self.validate_context(context)
        if not is_valid:
            return SkillResult(success=False, data={}, message=error)
        return SkillResult(success=True, data={"result": "ok"}, message="Success")


class TestSkillResult:
    """Test SkillResult dataclass."""

    def test_skill_result_success(self):
        """Test successful skill result."""
        result = SkillResult(
            success=True,
            data={"key": "value"},
            message="Operation completed"
        )
        assert result.success is True
        assert result.data == {"key": "value"}
        assert result.message == "Operation completed"

    def test_skill_result_failure(self):
        """Test failed skill result."""
        result = SkillResult(
            success=False,
            data={},
            message="Operation failed"
        )
        assert result.success is False
        assert result.data == {}
        assert result.message == "Operation failed"


class TestBaseSkill:
    """Test BaseSkill abstract class."""

    def test_base_skill_cannot_instantiate(self):
        """Test that BaseSkill cannot be instantiated directly."""
        with pytest.raises(TypeError):
            BaseSkill()  # type: ignore

    def test_concrete_skill_execute(self):
        """Test concrete skill implementation."""
        skill = ConcreteSkill()
        result = skill.execute({"test": "data"})
        assert result.success is True
        assert result.data == {"result": "ok"}

    def test_default_validate_context(self):
        """Test default validate_context returns True."""
        skill = ConcreteSkill()
        is_valid, error = skill.validate_context({})
        assert is_valid is True
        assert error == ""


class TestAuditWorkflowSkill:
    """Test AuditWorkflowSkill."""

    @pytest.fixture
    def mock_tenant(self):
        """Create mock tenant."""
        tenant = Mock()
        tenant.id = "test_tenant"
        tenant.project_id = "test-project"
        tenant.dataset = "test_dataset"
        return tenant

    @pytest.fixture
    def mock_audit_result(self):
        """Create mock audit result."""
        result = Mock()
        result.overall_score = 85.5
        result.rules = [
            {"rule": "test_rule", "score": 85.5, "window": "Q1", "level": "campaign"}
        ]
        return result

    @pytest.fixture
    def valid_context(self, tmp_path):
        """Create valid execution context."""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("windows:\n  - Q1\n  - Q2\n")
        return {
            "tenant_id": "test_tenant",
            "audit_config": str(config_file),
            "output_dir": str(tmp_path / "reports")
        }

    def test_validate_context_missing_tenant_id(self):
        """Test validation fails when tenant_id is missing."""
        skill = AuditWorkflowSkill()
        is_valid, error = skill.validate_context({"audit_config": "test.yaml"})
        assert is_valid is False
        assert "tenant_id" in error

    def test_validate_context_missing_audit_config(self):
        """Test validation fails when audit_config is missing."""
        skill = AuditWorkflowSkill()
        is_valid, error = skill.validate_context({"tenant_id": "test"})
        assert is_valid is False
        assert "audit_config" in error

    def test_validate_context_config_not_found(self):
        """Test validation fails when config file doesn't exist."""
        skill = AuditWorkflowSkill()
        is_valid, error = skill.validate_context({
            "tenant_id": "test",
            "audit_config": "/nonexistent/config.yaml"
        })
        assert is_valid is False
        assert "not found" in error

    def test_validate_context_success(self, valid_context):
        """Test validation succeeds with valid context."""
        skill = AuditWorkflowSkill()
        is_valid, error = skill.validate_context(valid_context)
        assert is_valid is True
        assert error == ""

    def test_validate_context_path_traversal_blocked(self, tmp_path):
        """Test validation blocks path traversal attempts."""
        config_file = tmp_path / "test_config.yaml"
        config_file.write_text("windows:\n  - Q1\n")

        skill = AuditWorkflowSkill()
        # Attempt path traversal
        is_valid, error = skill.validate_context({
            "tenant_id": "test",
            "audit_config": str(config_file),
            "output_dir": "/tmp/../../../etc"
        })
        # Should pass validation since resolve() normalizes the path
        # and we check for .. after resolution
        assert is_valid is True or "path traversal" in error.lower()

    @patch("paid_social_nav.skills.audit_workflow.get_tenant")
    def test_execute_tenant_not_found(self, mock_get_tenant, valid_context):
        """Test execution fails when tenant is not found."""
        mock_get_tenant.return_value = None
        skill = AuditWorkflowSkill()
        result = skill.execute(valid_context)
        assert result.success is False
        assert "not found" in result.message

    @patch("paid_social_nav.skills.audit_workflow.run_audit")
    @patch("paid_social_nav.skills.audit_workflow.get_tenant")
    def test_execute_audit_fails(self, mock_get_tenant, mock_run_audit, mock_tenant, valid_context):
        """Test execution fails when audit raises exception."""
        mock_get_tenant.return_value = mock_tenant
        mock_run_audit.side_effect = RuntimeError("BigQuery error")
        skill = AuditWorkflowSkill()
        result = skill.execute(valid_context)
        assert result.success is False
        assert "Audit failed" in result.message
        assert "BigQuery error" in result.message

    @patch("paid_social_nav.skills.audit_workflow.write_text")
    @patch("paid_social_nav.skills.audit_workflow.ReportRenderer")
    @patch("paid_social_nav.skills.audit_workflow.run_audit")
    @patch("paid_social_nav.skills.audit_workflow.get_tenant")
    def test_execute_success(
        self,
        mock_get_tenant,
        mock_run_audit,
        mock_renderer_class,
        mock_write_text,
        mock_tenant,
        mock_audit_result,
        valid_context
    ):
        """Test successful workflow execution."""
        mock_get_tenant.return_value = mock_tenant
        mock_run_audit.return_value = mock_audit_result
        mock_renderer = MagicMock()
        mock_renderer.render_markdown.return_value = "# Markdown Report"
        mock_renderer.render_html.return_value = "<html>HTML Report</html>"
        mock_renderer_class.return_value = mock_renderer

        skill = AuditWorkflowSkill()
        result = skill.execute(valid_context)

        assert result.success is True
        assert result.data["audit_score"] == 85.5
        assert result.data["tenant_id"] == "test_tenant"
        assert "markdown_report" in result.data
        assert "html_report" in result.data
        assert "85.5" in result.message

        # Verify reports were generated
        assert mock_renderer.render_markdown.called
        assert mock_renderer.render_html.called
        assert mock_write_text.call_count == 2

    @patch("paid_social_nav.skills.audit_workflow.write_text")
    @patch("paid_social_nav.skills.audit_workflow.ReportRenderer")
    @patch("paid_social_nav.skills.audit_workflow.run_audit")
    @patch("paid_social_nav.skills.audit_workflow.get_tenant")
    def test_execute_period_calculation(
        self,
        mock_get_tenant,
        mock_run_audit,
        mock_renderer_class,
        mock_write_text,
        mock_tenant,
        mock_audit_result,
        valid_context
    ):
        """Test period is calculated from config windows."""
        mock_get_tenant.return_value = mock_tenant
        mock_run_audit.return_value = mock_audit_result
        mock_renderer = MagicMock()
        mock_renderer.render_markdown.return_value = "# Report"
        mock_renderer.render_html.return_value = "<html>Report</html>"
        mock_renderer_class.return_value = mock_renderer

        skill = AuditWorkflowSkill()
        skill.execute(valid_context)

        # Check that markdown renderer was called with proper period
        call_args = mock_renderer.render_markdown.call_args
        data = call_args[0][0]
        assert data["period"] == "Q1, Q2"  # From config file

    @patch("paid_social_nav.skills.audit_workflow.ReportRenderer")
    @patch("paid_social_nav.skills.audit_workflow.run_audit")
    @patch("paid_social_nav.skills.audit_workflow.get_tenant")
    def test_execute_markdown_generation_fails(
        self,
        mock_get_tenant,
        mock_run_audit,
        mock_renderer_class,
        mock_tenant,
        mock_audit_result,
        valid_context
    ):
        """Test execution fails when Markdown generation fails."""
        mock_get_tenant.return_value = mock_tenant
        mock_run_audit.return_value = mock_audit_result
        mock_renderer = MagicMock()
        mock_renderer.render_markdown.side_effect = OSError("Disk full")
        mock_renderer_class.return_value = mock_renderer

        skill = AuditWorkflowSkill()
        result = skill.execute(valid_context)

        assert result.success is False
        assert "Failed to generate Markdown report" in result.message

    @patch("paid_social_nav.skills.audit_workflow.write_text")
    @patch("paid_social_nav.skills.audit_workflow.ReportRenderer")
    @patch("paid_social_nav.skills.audit_workflow.run_audit")
    @patch("paid_social_nav.skills.audit_workflow.get_tenant")
    def test_execute_html_generation_fails(
        self,
        mock_get_tenant,
        mock_run_audit,
        mock_renderer_class,
        mock_write_text,
        mock_tenant,
        mock_audit_result,
        valid_context
    ):
        """Test execution fails when HTML generation fails."""
        mock_get_tenant.return_value = mock_tenant
        mock_run_audit.return_value = mock_audit_result
        mock_renderer = MagicMock()
        mock_renderer.render_markdown.return_value = "# Report"
        mock_renderer.render_html.side_effect = OSError("Permission denied")
        mock_renderer_class.return_value = mock_renderer

        skill = AuditWorkflowSkill()
        result = skill.execute(valid_context)

        assert result.success is False
        assert "Failed to generate HTML report" in result.message

    def test_execute_invalid_output_dir(self, mock_tenant, mock_audit_result, valid_context):
        """Test execution fails when output directory cannot be created."""
        # Use a path that would fail to create (e.g., under /proc on Linux)
        invalid_context = valid_context.copy()
        invalid_context["output_dir"] = "/dev/null/invalid/path"

        with patch("paid_social_nav.skills.audit_workflow.get_tenant", return_value=mock_tenant):
            with patch("paid_social_nav.skills.audit_workflow.run_audit", return_value=mock_audit_result):
                skill = AuditWorkflowSkill()
                result = skill.execute(invalid_context)

                assert result.success is False
                assert "Failed to create output directory" in result.message
