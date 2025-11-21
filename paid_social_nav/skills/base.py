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
    next_step: str | None = None


class BaseSkill(ABC):
    """Base class for Claude skills that orchestrate multi-step workflows."""

    @abstractmethod
    def execute(self, context: dict[str, Any]) -> SkillResult:
        """Execute the skill workflow.

        Args:
            context: Input parameters and configuration

        Returns:
            SkillResult with success status and output data
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
