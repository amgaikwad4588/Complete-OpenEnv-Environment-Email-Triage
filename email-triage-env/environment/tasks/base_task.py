"""
Abstract base class for all Email Triage tasks.
Handles common action processing, state tracking, and observation building.
Concrete tasks override _get_emails(), _get_tool_names(), grade(), etc.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from environment.models import (
    Action,
    Email,
    EmailSummary,
    GraderResult,
    Observation,
    StepResult,
    ToolDefinition,
)
from environment.tools import TOOL_REGISTRY, call_tool


class BaseTask(ABC):
    """Abstract base for all tasks. Subclasses must implement the abstract methods."""

    task_id: str = "base"
    max_steps: int = 30

    def __init__(self) -> None:
        # These are initialised by reset()
        self._step: int = 0
        self._done: bool = False
        self._cumulative_reward: float = 0.0

        # Email state
        self._emails: dict[str, Email] = {}
        self._email_statuses: dict[str, str] = {}
        self._classified_as: dict[str, str] = {}
        self._priorities: dict[str, str] = {}
        self._responses_sent: dict[str, str] = {}
        self._escalations: dict[str, dict[str, str]] = {}
        self._duplicates: dict[str, str] = {}   # email_id -> original email_id
        self._tools_called: list[dict[str, Any]] = []
        self._current_email_id: str | None = None
        self._last_tool_result: dict[str, Any] | None = None

        # Draft buffer (send_response finalises it)
        self._drafts: dict[str, str] = {}

        # Call child-class setup
        self._setup()

    def _setup(self) -> None:
        """Initialise email data and tool availability. Called by __init__."""
        for email in self._get_emails():
            self._emails[email.email_id] = email
            self._email_statuses[email.email_id] = "unread"

    # ------------------------------------------------------------------
    # Abstract interface that subclasses MUST implement
    # ------------------------------------------------------------------

    @abstractmethod
    def _get_emails(self) -> list[Email]:
        """Return the initial list of Email objects for this task."""

    @abstractmethod
    def _get_tool_names(self) -> list[str]:
        """Return names of tools available for this task (from TOOL_REGISTRY)."""

    @abstractmethod
    def grade(self) -> GraderResult:
        """Compute and return the deterministic GraderResult for this task."""

    # ------------------------------------------------------------------
    # OpenEnv API methods
    # ------------------------------------------------------------------

    def reset(self) -> Observation:
        """Reset all state and return the initial observation."""
        self.__init__()
        return self._build_observation(
            f"Task '{self.task_id}' started. {len(self._emails)} emails in inbox."
        )

    def step(self, action: Action) -> StepResult:
        """Process one action and return a StepResult."""
        if self._done:
            obs = self._build_observation("Episode already finished. Call reset() to start over.")
            return StepResult(observation=obs, reward=0.0, done=True, info={})

        self._step += 1
        reward, message = self._dispatch_action(action)
        self._cumulative_reward = min(1.0, max(0.0, self._cumulative_reward + reward))

        # Check step limit
        if self._step >= self.max_steps and not self._done:
            self._done = True
            message += " [Max steps reached]"

        # Let subclass check task-specific completion
        if not self._done and self._check_completion():
            self._done = True
            reward += self._completion_bonus()

        obs = self._build_observation(message)
        obs.score = self._cumulative_reward

        info = {
            "step": self._step,
            "classified_count": len(self._classified_as),
            "responded_count": len(self._responses_sent),
            "escalated_count": len(self._escalations),
            "resolved_count": sum(
                1 for s in self._email_statuses.values() if s == "resolved"
            ),
        }
        return StepResult(observation=obs, reward=reward, done=self._done, info=info)

    def state(self) -> Observation:
        """Return current observation without consuming a step."""
        return self._build_observation("")

    # ------------------------------------------------------------------
    # Action dispatcher
    # ------------------------------------------------------------------

    def _dispatch_action(self, action: Action) -> tuple[float, str]:
        handlers = {
            "read_email": self._act_read_email,
            "classify_email": self._act_classify_email,
            "set_priority": self._act_set_priority,
            "use_tool": self._act_use_tool,
            "draft_response": self._act_draft_response,
            "send_response": self._act_send_response,
            "escalate": self._act_escalate,
            "resolve": self._act_resolve,
            "mark_duplicate": self._act_mark_duplicate,
        }
        handler = handlers.get(action.action_type)
        if not handler:
            return -0.02, f"Unknown action_type: '{action.action_type}'"
        return handler(action)

    # ------------------------------------------------------------------
    # Individual action handlers (can be overridden by subclasses)
    # ------------------------------------------------------------------

    def _act_read_email(self, action: Action) -> tuple[float, str]:
        eid = action.email_id
        if not eid or eid not in self._emails:
            return -0.02, f"email_id '{eid}' not found. Check inbox_summary for valid IDs."
        if self._email_statuses[eid] == "unread":
            self._email_statuses[eid] = "read"
        self._current_email_id = eid
        self._last_tool_result = None
        return 0.01, f"Opened email {eid}: \"{self._emails[eid].subject}\""

    def _act_classify_email(self, action: Action) -> tuple[float, str]:
        eid = action.email_id
        if not eid or eid not in self._emails:
            return -0.02, "Must provide valid email_id for classify_email."
        if not action.category:
            return -0.02, "Must provide category for classify_email."
        old = self._classified_as.get(eid)
        self._classified_as[eid] = action.category
        if self._email_statuses[eid] in ("unread", "read"):
            self._email_statuses[eid] = "classified"
        reward = self._classify_reward(eid, action.category)
        change = f"(changed from {old})" if old else ""
        return reward, f"Classified {eid} as '{action.category}' {change}".strip()

    def _act_set_priority(self, action: Action) -> tuple[float, str]:
        eid = action.email_id
        if not eid or eid not in self._emails:
            return -0.02, "Must provide valid email_id for set_priority."
        if not action.priority:
            return -0.02, "Must provide priority for set_priority."
        self._priorities[eid] = action.priority
        reward = self._priority_reward(eid, action.priority)
        return reward, f"Set priority of {eid} to '{action.priority}'"

    def _act_use_tool(self, action: Action) -> tuple[float, str]:
        available = self._get_tool_names()
        if not action.tool_name:
            return -0.02, "Must provide tool_name for use_tool."
        if action.tool_name not in available:
            return -0.05, (
                f"Tool '{action.tool_name}' not available. "
                f"Available: {available}"
            )
        params = action.tool_params or {}
        result = call_tool(action.tool_name, params)
        self._last_tool_result = {"tool": action.tool_name, "params": params, "result": result}
        self._tools_called.append(self._last_tool_result)
        reward = self._tool_reward(action.tool_name, params, result)
        return reward, f"Tool '{action.tool_name}' returned results."

    def _act_draft_response(self, action: Action) -> tuple[float, str]:
        eid = action.email_id
        if not eid or eid not in self._emails:
            return -0.02, "Must provide valid email_id for draft_response."
        if not action.response_text:
            return -0.02, "Must provide response_text for draft_response."
        self._drafts[eid] = action.response_text
        return 0.01, f"Response drafted for {eid}. Use send_response to send it."

    def _act_send_response(self, action: Action) -> tuple[float, str]:
        eid = action.email_id
        if not eid or eid not in self._emails:
            return -0.02, "Must provide valid email_id for send_response."
        if not action.response_text:
            return -0.02, "Must provide response_text for send_response."
        self._responses_sent[eid] = action.response_text
        if self._email_statuses.get(eid) not in ("escalated", "resolved"):
            self._email_statuses[eid] = "responded"
        reward = self._response_reward(eid, action.response_text)
        return reward, f"Response sent to {self._emails[eid].from_address}"

    def _act_escalate(self, action: Action) -> tuple[float, str]:
        eid = action.email_id
        if not eid or eid not in self._emails:
            return -0.02, "Must provide valid email_id for escalate."
        self._escalations[eid] = {
            "team": action.escalation_team or "unspecified",
            "reason": action.escalation_reason or "",
        }
        self._email_statuses[eid] = "escalated"
        reward = self._escalation_reward(eid, action.escalation_team)
        return reward, f"Email {eid} escalated to '{action.escalation_team}' team."

    def _act_resolve(self, action: Action) -> tuple[float, str]:
        eid = action.email_id
        if not eid or eid not in self._emails:
            return -0.02, "Must provide valid email_id for resolve."
        self._email_statuses[eid] = "resolved"
        reward = self._resolve_reward(eid)
        return reward, f"Email {eid} marked as resolved."

    def _act_mark_duplicate(self, action: Action) -> tuple[float, str]:
        eid = action.email_id
        orig = action.duplicate_of
        if not eid or eid not in self._emails:
            return -0.02, "Must provide valid email_id for mark_duplicate."
        if not orig or orig not in self._emails:
            return -0.02, "Must provide a valid duplicate_of email ID."
        if eid == orig:
            return -0.02, "email_id and duplicate_of must be different."
        self._duplicates[eid] = orig
        self._email_statuses[eid] = "duplicate"
        reward = self._duplicate_reward(eid, orig)
        return reward, f"Email {eid} marked as duplicate of {orig}."

    # ------------------------------------------------------------------
    # Reward hooks — subclasses override to provide task-specific rewards
    # ------------------------------------------------------------------

    def _classify_reward(self, email_id: str, category: str) -> float:
        return 0.03  # Default: small reward just for classifying

    def _priority_reward(self, email_id: str, priority: str) -> float:
        return 0.02

    def _tool_reward(self, tool_name: str, params: dict, result: dict) -> float:
        return 0.03 if not result.get("error") else -0.01

    def _response_reward(self, email_id: str, response_text: str) -> float:
        return 0.05

    def _escalation_reward(self, email_id: str, team: str | None) -> float:
        return 0.05

    def _resolve_reward(self, email_id: str) -> float:
        return 0.03

    def _duplicate_reward(self, email_id: str, original_id: str) -> float:
        return 0.03

    def _check_completion(self) -> bool:
        """Return True when the task is naturally complete (before step limit)."""
        return False

    def _completion_bonus(self) -> float:
        """Extra reward for finishing before the step limit."""
        remaining_ratio = max(0.0, (self.max_steps - self._step) / self.max_steps)
        return remaining_ratio * 0.05

    # ------------------------------------------------------------------
    # Observation builder
    # ------------------------------------------------------------------

    def _build_observation(self, message: str) -> Observation:
        # Build inbox summary
        inbox_summary = [
            EmailSummary(
                email_id=eid,
                from_address=email.from_address,
                subject=email.subject,
                received_at=email.received_at,
                status=self._email_statuses.get(eid, "unread"),  # type: ignore[arg-type]
                category=self._classified_as.get(eid),
                priority=self._priorities.get(eid),
                customer_tier=email.customer_tier,
            )
            for eid, email in self._emails.items()
        ]

        # Current email (only revealed after read_email)
        current_email = None
        if self._current_email_id and self._current_email_id in self._emails:
            current_email = self._emails[self._current_email_id]

        # Tool definitions
        available_tools = [
            ToolDefinition(**TOOL_REGISTRY[name]["definition"])
            for name in self._get_tool_names()
            if name in TOOL_REGISTRY
        ]

        return Observation(
            task_id=self.task_id,
            step=self._step,
            max_steps=self.max_steps,
            inbox_summary=inbox_summary,
            current_email=current_email,
            available_tools=available_tools,
            last_tool_result=self._last_tool_result,
            email_statuses=dict(self._email_statuses),
            classified_as=dict(self._classified_as),
            priorities=dict(self._priorities),
            message=message,
            done=self._done,
            score=min(1.0, max(0.0, self._cumulative_reward)),
        )

    # ------------------------------------------------------------------
    # Utility helpers used by subclasses
    # ------------------------------------------------------------------

    @staticmethod
    def _keywords_present(text: str, keywords: list[str]) -> bool:
        """Check if any keyword appears in text (case-insensitive)."""
        lower = text.lower()
        return any(kw.lower() in lower for kw in keywords)

    def _tools_called_for(self, email_id: str | None = None) -> list[str]:
        """Return list of tool names called (optionally filtered by context)."""
        return [t["tool"] for t in self._tools_called]
