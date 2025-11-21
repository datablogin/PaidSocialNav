from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Any


@dataclass
class SkillResult:
    """Result returned by a skill execution."""
    success: bool
    data: dict[str, Any]
    message: str


class BaseSkill(ABC):
    """Base class for Claude skills that orchestrate multi-step workflows."""

    @abstractmethod
    def execute(self, context: dict[str, Any]) -> SkillResult:
        """Execute the skill workflow.

        Args:
            context: Input parameters dictionary. Required keys depend on
                the skill implementation. Common keys:
                - tenant_id (str): Tenant identifier
                - audit_config (str): Path to audit configuration file
                - output_dir (str, optional): Path for output files

        Returns:
            SkillResult with:
                - success (bool): Whether execution succeeded
                - data (dict): Skill-specific output data
                - message (str): Human-readable status message

        Raises:
            ValueError: If context validation fails
            RuntimeError: If skill execution encounters an error

        Example:
            >>> skill = AuditWorkflowSkill()
            >>> result = skill.execute({
            ...     "tenant_id": "acme",
            ...     "audit_config": "configs/audit_acme.yaml",
            ...     "output_dir": "reports/"
            ... })
            >>> if result.success:
            ...     print(f"Success: {result.message}")
            ...     print(f"Report: {result.data['markdown_report']}")
        """
        pass

    def validate_context(self, context: dict[str, Any]) -> tuple[bool, str]:
        """Validate required context parameters.

        Args:
            context: Input parameters to validate

        Returns:
            Tuple of (is_valid, error_message)
        """
        return True, ""
