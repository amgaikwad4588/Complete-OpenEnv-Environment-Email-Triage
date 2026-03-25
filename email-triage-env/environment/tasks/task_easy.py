"""
Easy Task: Basic Email Classification
--------------------------------------
Agent must classify 5 support emails into the correct category and priority.
No tools required — pure reading and classification.

Scoring:
  - Category accuracy: 5 × 0.10 = 0.50
  - Priority accuracy: 5 × 0.06 = 0.30
  - All emails read:          0.10
  - Completion bonus:         0.10
  Total max: 1.0
"""
from __future__ import annotations

from environment.models import Action, Email, GraderResult
from environment.tasks.base_task import BaseTask


# Ground truth answers
CORRECT_CATEGORIES: dict[str, str] = {
    "E001": "shipping",
    "E002": "billing",
    "E003": "technical",
    "E004": "refund",
    "E005": "general",
}

CORRECT_PRIORITIES: dict[str, str] = {
    "E001": "medium",
    "E002": "high",
    "E003": "high",
    "E004": "medium",
    "E005": "low",
}


class EasyTask(BaseTask):
    task_id = "easy"
    max_steps = 15

    def _get_emails(self) -> list[Email]:
        return [
            Email(
                email_id="E001",
                from_address="james.chen@gmail.com",
                subject="Where is my order #78432?",
                body=(
                    "Hi, I placed order #78432 five days ago and was promised 3-day delivery. "
                    "The tracking page just says 'In Transit' but hasn't updated in 48 hours. "
                    "I'm starting to worry. Can you tell me where my package is? "
                    "I need it before the weekend."
                ),
                received_at="2025-03-25T08:14:00Z",
                customer_tier="standard",
            ),
            Email(
                email_id="E002",
                from_address="sarah.mitchell@company.com",
                subject="Charged twice for subscription renewal",
                body=(
                    "I was just reviewing my credit card statement and noticed I've been "
                    "charged $149 twice this month for my Pro subscription — once on March 15th "
                    "and again on March 18th. Total unexpected charge of $298. "
                    "Please investigate immediately and refund the duplicate charge. "
                    "My account email is sarah.mitchell@company.com."
                ),
                received_at="2025-03-25T09:02:00Z",
                customer_tier="premium",
            ),
            Email(
                email_id="E003",
                from_address="dev.ops@techstartup.io",
                subject="API returning 503 errors — production down",
                body=(
                    "URGENT: Our production integration with your REST API has been throwing "
                    "503 Service Unavailable errors since approximately 09:00 UTC today. "
                    "Endpoint: POST /v2/process. Error rate: 100%. "
                    "We have 50k daily active users affected. "
                    "We've tried rotating API keys and confirming our payload format is correct. "
                    "This needs immediate attention. Our SLA requires 99.9% uptime and "
                    "we're breaching it right now."
                ),
                received_at="2025-03-25T09:23:00Z",
                customer_tier="premium",
            ),
            Email(
                email_id="E004",
                from_address="lucy.patel@hotmail.com",
                subject="Return request for order #65109",
                body=(
                    "Hello, I received my order #65109 last Tuesday but the item is completely "
                    "different from what I ordered. I ordered the blue 'Nova Wireless Headphones' "
                    "but received red 'Echo Wired Earbuds'. This is clearly a wrong-item situation. "
                    "I'd like to return this and either get the correct item or a full refund. "
                    "Please advise on the return process."
                ),
                received_at="2025-03-25T10:45:00Z",
                customer_tier="standard",
            ),
            Email(
                email_id="E005",
                from_address="curious.customer@yahoo.com",
                subject="Do you ship internationally?",
                body=(
                    "Hi there, I'm based in Australia and I've been browsing your website. "
                    "I really like some of your products but before I order I wanted to check — "
                    "do you ship to Australia? And if so, roughly how long does international "
                    "shipping take and what are the approximate costs? Thanks for your help."
                ),
                received_at="2025-03-25T11:30:00Z",
                customer_tier="standard",
            ),
        ]

    def _get_tool_names(self) -> list[str]:
        return []  # No tools in easy task

    # ------------------------------------------------------------------
    # Reward overrides — immediate feedback per action
    # ------------------------------------------------------------------

    def _classify_reward(self, email_id: str, category: str) -> float:
        correct = CORRECT_CATEGORIES.get(email_id)
        if category == correct:
            return 0.10  # Full credit
        # Partial credit for plausible-but-wrong (e.g. "technical" when it's "billing")
        return -0.05

    def _priority_reward(self, email_id: str, priority: str) -> float:
        correct = CORRECT_PRIORITIES.get(email_id)
        if priority == correct:
            return 0.06
        # Adjacent priority (e.g. medium vs high) gets partial credit
        adjacency = {
            ("low", "medium"), ("medium", "low"),
            ("medium", "high"), ("high", "medium"),
            ("high", "urgent"), ("urgent", "high"),
        }
        if (priority, correct) in adjacency:
            return 0.02
        return -0.02

    def _check_completion(self) -> bool:
        """Done when all 5 emails are classified."""
        return len(self._classified_as) == len(self._emails)

    # ------------------------------------------------------------------
    # Grader
    # ------------------------------------------------------------------

    def grade(self) -> GraderResult:
        breakdown: dict[str, float] = {}
        feedback: list[str] = []

        # 1. Category accuracy (0.50)
        cat_score = 0.0
        for eid, correct in CORRECT_CATEGORIES.items():
            given = self._classified_as.get(eid)
            if given == correct:
                cat_score += 0.10
            else:
                feedback.append(
                    f"Email {eid}: expected category '{correct}', got '{given or 'unclassified'}'"
                )
        breakdown["category_accuracy"] = round(cat_score, 3)

        # 2. Priority accuracy (0.30)
        pri_score = 0.0
        for eid, correct in CORRECT_PRIORITIES.items():
            given = self._priorities.get(eid)
            if given == correct:
                pri_score += 0.06
            else:
                feedback.append(
                    f"Email {eid}: expected priority '{correct}', got '{given or 'unset'}'"
                )
        breakdown["priority_accuracy"] = round(pri_score, 3)

        # 3. All emails read (0.10)
        all_read = all(
            self._email_statuses.get(eid) != "unread" for eid in self._emails
        )
        read_score = 0.10 if all_read else len([
            eid for eid in self._emails
            if self._email_statuses.get(eid) != "unread"
        ]) * 0.02
        breakdown["all_emails_read"] = round(read_score, 3)
        if not all_read:
            feedback.append("Not all emails were read before classification.")

        # 4. Completion bonus (0.10)
        all_classified = len(self._classified_as) == len(self._emails)
        completion = 0.10 if all_classified else 0.0
        breakdown["completion_bonus"] = round(completion, 3)
        if not all_classified:
            unclassified = [e for e in self._emails if e not in self._classified_as]
            feedback.append(f"Unclassified emails: {unclassified}")

        total = min(1.0, cat_score + pri_score + read_score + completion)

        if not feedback:
            feedback.append("Perfect score! All emails correctly classified and prioritised.")

        return GraderResult(
            task_id=self.task_id,
            score=round(total, 4),
            breakdown=breakdown,
            feedback=feedback,
            passed=total >= 0.7,
        )
