"""
Email Triage OpenEnv — FastAPI Server
=======================================
Exposes the full OpenEnv API:
  POST /reset           — Start or reset an episode
  POST /step            — Take one action
  GET  /state           — View current state (no step consumed)
  GET  /tasks           — List tasks and Action schema
  GET  /grader          — Get deterministic grade for current session
  POST /baseline        — Run baseline agent on all 3 tasks and return scores
  GET  /health          — Health check (returns 200)

Session management:
  Each session is identified by a UUID passed in the X-Session-ID header.
  /reset creates a new session and returns the session_id in the response body.
  All subsequent calls must include X-Session-ID.
"""
from __future__ import annotations

import asyncio
import time
import threading
import uuid
from contextlib import asynccontextmanager
from dataclasses import dataclass, field
from typing import Any, Optional

from fastapi import FastAPI, Header, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from environment.env import EmailTriageEnv
from environment.models import (
    Action,
    BaselineResult,
    GraderResult,
    Observation,
    StepResult,
    TaskInfo,
)
from environment.tasks import TASK_REGISTRY


# ---------------------------------------------------------------------------
# Session store
# ---------------------------------------------------------------------------

@dataclass
class SessionRecord:
    env: EmailTriageEnv
    created_at: float = field(default_factory=time.time)
    last_used: float = field(default_factory=time.time)


class SessionStore:
    """Thread-safe in-memory session store with TTL eviction."""

    def __init__(self, ttl_seconds: int = 7200) -> None:
        self._store: dict[str, SessionRecord] = {}
        self._lock = threading.Lock()
        self._ttl = ttl_seconds

    def get(self, session_id: str) -> EmailTriageEnv | None:
        with self._lock:
            record = self._store.get(session_id)
            if record:
                record.last_used = time.time()
                return record.env
            return None

    def create(self) -> tuple[str, EmailTriageEnv]:
        sid = str(uuid.uuid4())
        env = EmailTriageEnv()
        with self._lock:
            self._store[sid] = SessionRecord(env=env)
        return sid, env

    def get_or_create(self, session_id: str | None) -> tuple[str, EmailTriageEnv]:
        if session_id:
            env = self.get(session_id)
            if env:
                return session_id, env
        return self.create()

    def cleanup_stale(self) -> int:
        cutoff = time.time() - self._ttl
        with self._lock:
            stale = [k for k, v in self._store.items() if v.last_used < cutoff]
            for k in stale:
                del self._store[k]
        return len(stale)

    def __len__(self) -> int:
        with self._lock:
            return len(self._store)


store = SessionStore()


# ---------------------------------------------------------------------------
# App lifecycle
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Background cleanup task removes stale sessions every 30 minutes."""
    async def _cleanup_loop():
        while True:
            await asyncio.sleep(1800)
            evicted = store.cleanup_stale()
            if evicted:
                print(f"[SessionStore] Evicted {evicted} stale sessions")

    task = asyncio.create_task(_cleanup_loop())
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(
    title="Email Triage OpenEnv",
    description=(
        "A realistic customer support email triage environment for training "
        "and evaluating AI agents. Implements the OpenEnv spec with 3 tasks "
        "ranging from easy classification to complex incident management."
    ),
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class ResetRequest(BaseModel):
    task_id: str = "easy"


class ResetResponse(BaseModel):
    session_id: str
    observation: dict


class StepResponse(BaseModel):
    observation: dict
    reward: float
    done: bool
    info: dict


class GraderResponse(BaseModel):
    session_id: str
    grader: dict


class BaselineResponse(BaseModel):
    results: list[dict]
    summary: dict[str, float]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _require_session(session_id: str | None, endpoint: str) -> tuple[str, EmailTriageEnv]:
    """Resolve session or raise 404 with helpful message."""
    if not session_id:
        raise HTTPException(
            status_code=400,
            detail=f"X-Session-ID header is required for {endpoint}. Call POST /reset first.",
        )
    env = store.get(session_id)
    if env is None:
        raise HTTPException(
            status_code=404,
            detail=f"Session '{session_id}' not found. Sessions expire after 2 hours. Call POST /reset.",
        )
    return session_id, env


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------

@app.get("/health")
async def health() -> dict:
    """Health check — returns 200 with server status."""
    return {
        "status": "ok",
        "active_sessions": len(store),
        "tasks": list(TASK_REGISTRY.keys()),
    }


@app.post("/reset", response_model=ResetResponse, summary="Reset or start an episode")
async def reset(
    request: ResetRequest,
    x_session_id: Optional[str] = Header(default=None),
) -> ResetResponse:
    """
    Reset the environment for the given task.
    Creates a new session if X-Session-ID is not provided or not found.

    **task_id**: one of `easy`, `medium`, `hard`

    Returns `session_id` — include this in `X-Session-ID` header for all subsequent calls.
    """
    if request.task_id not in TASK_REGISTRY:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid task_id '{request.task_id}'. Valid: {list(TASK_REGISTRY.keys())}",
        )
    sid, env = store.get_or_create(x_session_id)
    obs: Observation = env.reset(task_id=request.task_id)
    return ResetResponse(session_id=sid, observation=obs.model_dump())


@app.post("/step", response_model=StepResponse, summary="Take one action")
async def step(
    action: Action,
    x_session_id: Optional[str] = Header(default=None),
) -> StepResponse:
    """
    Take one action in the current episode.

    Include `X-Session-ID` (returned by `/reset`) in the request header.
    Returns the new observation, reward, done flag, and diagnostic info.
    """
    _, env = _require_session(x_session_id, "/step")
    if not env.is_reset:
        raise HTTPException(status_code=400, detail="Call /reset before /step")

    result: StepResult = env.step(action)
    return StepResponse(
        observation=result.observation.model_dump(),
        reward=result.reward,
        done=result.done,
        info=result.info,
    )


@app.get("/state", summary="Get current observation without consuming a step")
async def state(
    x_session_id: Optional[str] = Header(default=None),
) -> dict:
    """
    Returns the current observation without counting as a step.
    Useful for inspecting state after calling `/reset`.
    """
    _, env = _require_session(x_session_id, "/state")
    if not env.is_reset:
        raise HTTPException(status_code=400, detail="Call /reset before /state")
    obs: Observation = env.state()
    return obs.model_dump()


@app.get("/tasks", summary="List all tasks and Action schema")
async def tasks() -> dict:
    """
    Returns metadata for all available tasks and the full Action JSON Schema.
    Use the action schema to understand what fields are valid per action_type.
    """
    task_list = [
        TaskInfo(
            task_id="easy",
            name="Email Classification",
            description=(
                "Classify 5 support emails by category and priority. "
                "No tools required. Score = classification accuracy."
            ),
            max_steps=15,
            difficulty="easy",
            scoring_description=(
                "Category accuracy 0.50 + priority accuracy 0.30 + "
                "all emails read 0.10 + completion bonus 0.10"
            ),
        ),
        TaskInfo(
            task_id="medium",
            name="Tool-Assisted Response Drafting",
            description=(
                "Handle 3 support emails that require account/order lookups "
                "before crafting accurate responses. Tools: lookup_order, "
                "get_customer_info, check_refund_eligibility, lookup_known_issues."
            ),
            max_steps=30,
            difficulty="medium",
            scoring_description=(
                "Per email: category + priority + tool use + response quality. "
                "Efficiency bonus for ≤18 steps."
            ),
        ),
        TaskInfo(
            task_id="hard",
            name="Incident Management Workflow",
            description=(
                "Manage 10 emails during a live product outage. Includes VIP customers, "
                "press inquiries (CRITICAL: no technical details), duplicate detection, "
                "angry customers, and unrelated tickets. "
                "6 tools available."
            ),
            max_steps=60,
            difficulty="hard",
            scoring_description=(
                "Priority accuracy + duplicates + VIP handling + escalation correctness "
                "+ non-outage separation + response quality + policy compliance (heavy penalty "
                "for press tech leak) + completion + efficiency."
            ),
        ),
    ]

    return {
        "tasks": [t.model_dump() for t in task_list],
        "action_schema": Action.model_json_schema(),
    }


@app.get("/grader", summary="Get deterministic grader score for current session")
async def grader(
    x_session_id: Optional[str] = Header(default=None),
) -> GraderResponse:
    """
    Run the deterministic grader on the current episode state.
    Returns score (0.0–1.0), component breakdown, and feedback strings.
    Can be called at any point during or after an episode.
    """
    sid, env = _require_session(x_session_id, "/grader")
    if not env.is_reset:
        raise HTTPException(status_code=400, detail="Call /reset before /grader")
    result: GraderResult = env.grade()
    return GraderResponse(session_id=sid, grader=result.model_dump())


@app.post("/baseline", summary="Run baseline agent on all 3 tasks")
async def baseline() -> BaselineResponse:
    """
    Runs the built-in baseline agent (keyword-heuristic, no LLM) against
    all 3 tasks and returns reproducible baseline scores.

    For the LLM-based baseline, see `baseline/run_baseline.py`
    (requires OPENAI_API_KEY environment variable).
    """
    from baseline.heuristic_baseline import run_heuristic_baseline
    results = run_heuristic_baseline()
    summary = {r["task_id"]: r["score"] for r in results}
    return BaselineResponse(results=results, summary=summary)


# ---------------------------------------------------------------------------
# Entry point (for uv run server and direct execution)
# ---------------------------------------------------------------------------

def main():
    """Entry point for `uv run server` and `python app.py`."""
    import uvicorn
    uvicorn.run("app:app", host="0.0.0.0", port=7860, reload=False)


if __name__ == "__main__":
    main()
