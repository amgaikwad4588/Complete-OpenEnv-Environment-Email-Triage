"""
EmailTriageEnv — the main environment coordinator.
Instantiates the correct task, delegates step/reset/state/grade to it,
and exposes the clean OpenEnv API.
"""
from __future__ import annotations

from environment.models import Action, GraderResult, Observation, StepResult
from environment.tasks import TASK_REGISTRY
from environment.tasks.base_task import BaseTask


class EmailTriageEnv:
    """
    Stateful environment instance (one per session).

    Usage:
        env = EmailTriageEnv()
        obs = env.reset(task_id="easy")
        result = env.step(action)
        grade = env.grade()
    """

    def __init__(self) -> None:
        self._task: BaseTask | None = None
        self._task_id: str | None = None

    # ------------------------------------------------------------------
    # OpenEnv API
    # ------------------------------------------------------------------

    def reset(self, task_id: str = "easy") -> Observation:
        """
        Reset the environment for the given task.
        Creates a fresh task instance and returns the initial observation.

        Args:
            task_id: One of "easy", "medium", "hard"

        Returns:
            Initial Observation
        """
        if task_id not in TASK_REGISTRY:
            raise ValueError(
                f"Unknown task_id '{task_id}'. Valid options: {list(TASK_REGISTRY.keys())}"
            )
        self._task_id = task_id
        self._task = TASK_REGISTRY[task_id]()
        return self._task.reset()

    def step(self, action: Action) -> StepResult:
        """
        Take one action in the environment.

        Args:
            action: An Action object specifying what to do

        Returns:
            StepResult with observation, reward, done flag, and info dict
        """
        if self._task is None:
            raise RuntimeError("Call reset() before step()")
        return self._task.step(action)

    def state(self) -> Observation:
        """
        Get the current observation without consuming a step.

        Returns:
            Current Observation
        """
        if self._task is None:
            raise RuntimeError("Call reset() before state()")
        return self._task.state()

    def grade(self) -> GraderResult:
        """
        Run the deterministic grader and return the score.
        Can be called at any point during or after an episode.

        Returns:
            GraderResult with score, breakdown, and feedback
        """
        if self._task is None:
            raise RuntimeError("Call reset() before grade()")
        return self._task.grade()

    @property
    def task_id(self) -> str | None:
        return self._task_id

    @property
    def is_reset(self) -> bool:
        return self._task is not None
