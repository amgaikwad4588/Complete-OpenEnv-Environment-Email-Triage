"""
Pydantic v2 models for the Email Triage OpenEnv environment.
These define the typed Observation, Action, and result schemas
that the OpenEnv spec requires.
"""
from __future__ import annotations

from typing import Any, Literal, Optional
from pydantic import BaseModel, Field, ConfigDict


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------

class Email(BaseModel):
    """A single email in the support inbox."""
    model_config = ConfigDict(frozen=False)

    email_id: str = Field(..., description="Unique identifier for this email")
    from_address: str = Field(..., description="Sender's email address")
    subject: str = Field(..., description="Email subject line")
    body: str = Field(..., description="Full email body text (only visible after read_email)")
    received_at: str = Field(..., description="ISO 8601 datetime when email was received")
    customer_tier: Literal["standard", "premium", "vip"] = Field(
        "standard", description="Support tier of the sending customer"
    )
    is_vip: bool = Field(False, description="Whether sender is a VIP/enterprise account")
    metadata: dict[str, Any] = Field(default_factory=dict, description="Task-specific metadata")


class EmailSummary(BaseModel):
    """Lightweight summary of an email shown in the inbox list."""
    email_id: str
    from_address: str
    subject: str
    received_at: str
    status: Literal["unread", "read", "classified", "responded", "escalated", "resolved", "duplicate"]
    category: Optional[str] = None
    priority: Optional[str] = None
    customer_tier: Literal["standard", "premium", "vip"] = "standard"


class ToolDefinition(BaseModel):
    """Description of an available tool the agent can call."""
    name: str = Field(..., description="Tool name used in use_tool action")
    description: str = Field(..., description="What this tool does")
    parameters: dict[str, Any] = Field(default_factory=dict, description="JSON Schema for params")


# ---------------------------------------------------------------------------
# Observation — what the agent sees
# ---------------------------------------------------------------------------

class Observation(BaseModel):
    """
    The complete observation returned by reset(), step(), and state().
    Agents should use this to understand the current state of the inbox
    and decide on the next action.
    """
    task_id: str = Field(..., description="ID of the current task: easy | medium | hard")
    step: int = Field(..., description="Current step number (0-indexed)")
    max_steps: int = Field(..., description="Maximum steps allowed before episode ends")

    # Inbox view
    inbox_summary: list[EmailSummary] = Field(
        default_factory=list,
        description="Lightweight list of all emails with current status"
    )
    current_email: Optional[Email] = Field(
        None,
        description="Full email content if read_email was the last action, else None"
    )

    # Tool state
    available_tools: list[ToolDefinition] = Field(
        default_factory=list,
        description="Tools the agent can call using use_tool action"
    )
    last_tool_result: Optional[dict[str, Any]] = Field(
        None,
        description="Result dict from the most recent use_tool call"
    )

    # Tracking
    email_statuses: dict[str, str] = Field(
        default_factory=dict,
        description="Map of email_id -> current status string"
    )
    classified_as: dict[str, str] = Field(
        default_factory=dict,
        description="Map of email_id -> assigned category"
    )
    priorities: dict[str, str] = Field(
        default_factory=dict,
        description="Map of email_id -> assigned priority"
    )

    # Meta
    message: str = Field("", description="Human-readable info about the last action's result")
    done: bool = Field(False, description="True when the episode has ended")
    score: float = Field(0.0, ge=0.0, le=1.0, description="Running cumulative score estimate")


# ---------------------------------------------------------------------------
# Action — what the agent does
# ---------------------------------------------------------------------------

class Action(BaseModel):
    """
    An agent action. Set action_type and the relevant fields for that type.

    Action types:
      read_email      — Read the full body of an email (required before other actions)
      classify_email  — Assign a category to an email
      set_priority    — Assign a priority level to an email
      use_tool        — Call a named tool with parameters
      draft_response  — Preview a response (no effect on state, for planning)
      send_response   — Send a response to the customer
      escalate        — Route email to a specialist team
      resolve         — Mark an email as resolved
      mark_duplicate  — Mark an email as a duplicate of another
    """
    action_type: Literal[
        "read_email",
        "classify_email",
        "set_priority",
        "use_tool",
        "draft_response",
        "send_response",
        "escalate",
        "resolve",
        "mark_duplicate",
    ] = Field(..., description="Type of action to perform")

    # Target email
    email_id: Optional[str] = Field(
        None, description="Email ID to act on (required for most actions)"
    )

    # Classification fields
    category: Optional[Literal[
        "shipping", "billing", "technical", "refund", "general", "outage", "press"
    ]] = Field(None, description="Category for classify_email action")

    priority: Optional[Literal["low", "medium", "high", "urgent"]] = Field(
        None, description="Priority level for set_priority action"
    )

    # Tool use
    tool_name: Optional[str] = Field(
        None, description="Name of tool to call (matches ToolDefinition.name)"
    )
    tool_params: Optional[dict[str, Any]] = Field(
        None, description="Parameters to pass to the tool"
    )

    # Response
    response_text: Optional[str] = Field(
        None, description="Response text for draft_response or send_response"
    )

    # Escalation
    escalation_team: Optional[Literal[
        "engineering", "billing", "legal", "pr", "vip_support", "senior_support"
    ]] = Field(None, description="Team to escalate to")
    escalation_reason: Optional[str] = Field(
        None, description="Brief reason for escalation"
    )

    # Duplicate detection
    duplicate_of: Optional[str] = Field(
        None, description="Email ID that this email is a duplicate of"
    )


# ---------------------------------------------------------------------------
# Step result
# ---------------------------------------------------------------------------

class StepResult(BaseModel):
    """Full result returned by POST /step."""
    observation: Observation
    reward: float = Field(..., description="Immediate reward signal for this step")
    done: bool = Field(..., description="Whether the episode has ended")
    info: dict[str, Any] = Field(
        default_factory=dict,
        description="Diagnostic info (step count, classified count, etc.)"
    )


# ---------------------------------------------------------------------------
# Grader result
# ---------------------------------------------------------------------------

class GraderResult(BaseModel):
    """Deterministic grader output returned by GET /grader."""
    task_id: str
    score: float = Field(..., ge=0.0, le=1.0, description="Final score between 0.0 and 1.0")
    breakdown: dict[str, float] = Field(
        default_factory=dict,
        description="Component scores (classification, tool_use, response_quality, etc.)"
    )
    feedback: list[str] = Field(
        default_factory=list,
        description="Human-readable feedback strings"
    )
    passed: bool = Field(..., description="True if score >= 0.7 (passing threshold)")


# ---------------------------------------------------------------------------
# Task info (for /tasks endpoint)
# ---------------------------------------------------------------------------

class TaskInfo(BaseModel):
    """Metadata about a task, returned by GET /tasks."""
    task_id: str
    name: str
    description: str
    max_steps: int
    difficulty: Literal["easy", "medium", "hard"]
    scoring_description: str


# ---------------------------------------------------------------------------
# Baseline result
# ---------------------------------------------------------------------------

class BaselineResult(BaseModel):
    """Result of running baseline agent on a single task."""
    task_id: str
    score: float
    steps_taken: int
    grader_breakdown: dict[str, float]
    error: Optional[str] = None
