"""
Medium Task: Tool-Assisted Response Drafting
----------------------------------------------
Agent must handle 3 support emails that require tool lookups before
crafting accurate, helpful responses.

Scoring per email (~0.33 each):
  M001 — Delayed order:
    correct category (shipping):         0.04
    correct priority (high):             0.03
    used lookup_order:                   0.08
    used get_customer_info:              0.04
    response mentions delay reason:      0.05
    response offers compensation:        0.05
    empathetic tone:                     0.03
    sub-total:                           0.32

  M002 — Refund request (over 30 days):
    correct category (refund):           0.04
    correct priority (medium):           0.03
    used check_refund_eligibility:       0.08
    used get_customer_info:              0.04
    granted goodwill exception:          0.08
    goodwill/apology language:           0.03
    sub-total:                           0.30

  M003 — SSO broken (VIP):
    correct category (technical):        0.04
    correct priority (urgent):           0.05
    used get_customer_info:              0.04
    used lookup_known_issues:            0.08
    response includes workaround:        0.07
    response includes ETA:              0.04
    escalated or mentions account mgr:  0.03
    sub-total:                           0.35

  Efficiency bonus:                      0.05 (if total_steps <= 18)
  Total max: ~1.02 → capped at 1.0
"""
from __future__ import annotations

from environment.models import Action, Email, GraderResult
from environment.tasks.base_task import BaseTask

CORRECT_CATEGORIES = {"M001": "shipping", "M002": "refund",   "M003": "technical"}
CORRECT_PRIORITIES  = {"M001": "high",     "M002": "medium",   "M003": "urgent"}

# Keyword lists for response quality checks
EMPATHY_KWS = ["sorry", "apologize", "apologise", "understand", "frustrat", "inconvenien", "regret"]
COMPENSATION_KWS = ["credit", "discount", "compensat", "refund", "reimburse", "expedit"]
CUSTOMS_KWS = ["customs", "customs office", "customs hold", "import", "border"]
GOODWILL_KWS = ["exception", "goodwill", "one-time", "one time", "courtesy", "special", "waive"]
WORKAROUND_KWS = ["magic link", "workaround", "temporarily", "alternative", "bypass", "instead"]
ETA_KWS = ["18:00", "6 pm", "6pm", "fix", "resolved", "hours", "today", "eta", "soon", "by "]
ACCOUNT_MGR_KWS = ["account manager", "jessica", "jessica wang", "dedicated", "reach out"]


class MediumTask(BaseTask):
    task_id = "medium"
    max_steps = 30

    def _get_emails(self) -> list[Email]:
        return [
            Email(
                email_id="M001",
                from_address="angry.customer2024@gmail.com",
                subject="Order #92847 — 2 weeks late, I want compensation",
                body=(
                    "This is absolutely unacceptable. I placed order #92847 two weeks ago "
                    "and it's STILL not here. I've tried calling three times and been put on "
                    "hold each time. I am a premium customer and I expect premium service. "
                    "I want a refund, an apology, and a discount on my next order. "
                    "This is my LAST chance for your company to make this right before I "
                    "dispute the charge."
                ),
                received_at="2025-03-25T07:45:00Z",
                customer_tier="premium",
            ),
            Email(
                email_id="M002",
                from_address="first.time.buyer@outlook.com",
                subject="Can I get a refund? Bought 32 days ago",
                body=(
                    "Hi, I bought the 'Premium Analytics Dashboard' plan on February 21st. "
                    "I've tried using it but honestly it's just too complicated for my small team. "
                    "We don't have the technical expertise to get value from it. "
                    "I see your refund policy says 30 days, but I'm just 2 days over. "
                    "Is there any flexibility? I would really appreciate it — it was $299."
                ),
                received_at="2025-03-25T09:55:00Z",
                customer_tier="standard",
            ),
            Email(
                email_id="M003",
                from_address="enterprise.admin@megacorp.com",
                subject="SSO integration broken after your update",
                body=(
                    "We're the IT team at MegaCorp. Since your platform update yesterday "
                    "(March 24th), our SAML SSO integration has completely stopped working. "
                    "Our 200 employees cannot log in to the platform at all. "
                    "We've checked our IdP — nothing changed on our end. "
                    "The SAML error logs show 'Assertion validation failed'. "
                    "We need this resolved today — we have board presentations using your "
                    "platform tomorrow morning at 9 AM."
                ),
                received_at="2025-03-25T10:10:00Z",
                customer_tier="vip",
                is_vip=True,
            ),
        ]

    def _get_tool_names(self) -> list[str]:
        return ["lookup_order", "get_customer_info", "check_refund_eligibility", "lookup_known_issues"]

    # ------------------------------------------------------------------
    # Reward overrides
    # ------------------------------------------------------------------

    def _classify_reward(self, email_id: str, category: str) -> float:
        return 0.04 if category == CORRECT_CATEGORIES.get(email_id) else -0.04

    def _priority_reward(self, email_id: str, priority: str) -> float:
        return 0.03 if priority == CORRECT_PRIORITIES.get(email_id) else -0.02

    def _tool_reward(self, tool_name: str, params: dict, result: dict) -> float:
        if result.get("error"):
            return -0.01
        # Relevant tool usage gets a small bonus
        relevant_map = {
            "M001_phase": {"lookup_order", "get_customer_info"},
            "M002_phase": {"check_refund_eligibility", "get_customer_info"},
            "M003_phase": {"get_customer_info", "lookup_known_issues"},
        }
        return 0.03

    def _response_reward(self, email_id: str, response_text: str) -> float:
        """Keyword-based response quality signal."""
        score = 0.03  # base for sending
        text = response_text.lower()
        if email_id == "M001":
            if self._keywords_present(text, CUSTOMS_KWS):
                score += 0.04
            if self._keywords_present(text, COMPENSATION_KWS):
                score += 0.04
            if self._keywords_present(text, EMPATHY_KWS):
                score += 0.02
        elif email_id == "M002":
            if self._keywords_present(text, GOODWILL_KWS):
                score += 0.06
            if self._keywords_present(text, EMPATHY_KWS):
                score += 0.02
        elif email_id == "M003":
            if self._keywords_present(text, WORKAROUND_KWS):
                score += 0.05
            if self._keywords_present(text, ETA_KWS):
                score += 0.03
            if self._keywords_present(text, ACCOUNT_MGR_KWS):
                score += 0.02
        return score

    def _check_completion(self) -> bool:
        terminal = {"responded", "escalated", "resolved"}
        return all(s in terminal for s in self._email_statuses.values())

    # ------------------------------------------------------------------
    # Grader (deterministic)
    # ------------------------------------------------------------------

    def grade(self) -> GraderResult:
        breakdown: dict[str, float] = {}
        feedback: list[str] = []
        tools = self._tools_called_for()

        # ---- M001 ----
        m001_score = 0.0
        if self._classified_as.get("M001") == "shipping":
            m001_score += 0.04
        else:
            feedback.append("M001: should be classified as 'shipping'")

        if self._priorities.get("M001") == "high":
            m001_score += 0.03
        else:
            feedback.append("M001: priority should be 'high' (premium customer, 2-week delay)")

        if "lookup_order" in tools:
            m001_score += 0.08
        else:
            feedback.append("M001: should have used lookup_order to get order status")

        if "get_customer_info" in tools:
            m001_score += 0.04
        else:
            feedback.append("M001: should have used get_customer_info to check premium tier")

        resp_m001 = (self._responses_sent.get("M001") or "").lower()
        if resp_m001:
            if self._keywords_present(resp_m001, CUSTOMS_KWS):
                m001_score += 0.05
            else:
                feedback.append("M001 response: should mention the customs delay reason")
            if self._keywords_present(resp_m001, COMPENSATION_KWS):
                m001_score += 0.05
            else:
                feedback.append("M001 response: should offer credit/compensation to premium customer")
            if self._keywords_present(resp_m001, EMPATHY_KWS):
                m001_score += 0.03
        else:
            feedback.append("M001: no response was sent")
        breakdown["M001"] = round(m001_score, 3)

        # ---- M002 ----
        m002_score = 0.0
        if self._classified_as.get("M002") == "refund":
            m002_score += 0.04
        else:
            feedback.append("M002: should be classified as 'refund'")

        if self._priorities.get("M002") == "medium":
            m002_score += 0.03
        else:
            feedback.append("M002: priority should be 'medium'")

        if "check_refund_eligibility" in tools:
            m002_score += 0.08
        else:
            feedback.append("M002: should have used check_refund_eligibility before responding")

        if "get_customer_info" in tools:
            m002_score += 0.04

        resp_m002 = (self._responses_sent.get("M002") or "").lower()
        if resp_m002:
            if self._keywords_present(resp_m002, GOODWILL_KWS):
                m002_score += 0.08
            else:
                feedback.append(
                    "M002 response: first-time buyer 2 days over policy — goodwill exception warranted"
                )
            if self._keywords_present(resp_m002, EMPATHY_KWS):
                m002_score += 0.03
        else:
            feedback.append("M002: no response was sent")
        breakdown["M002"] = round(m002_score, 3)

        # ---- M003 ----
        m003_score = 0.0
        if self._classified_as.get("M003") == "technical":
            m003_score += 0.04
        else:
            feedback.append("M003: should be classified as 'technical'")

        if self._priorities.get("M003") == "urgent":
            m003_score += 0.05
        else:
            feedback.append("M003: VIP with 200 blocked users — priority should be 'urgent'")

        if "get_customer_info" in tools:
            m003_score += 0.04
        else:
            feedback.append("M003: should have used get_customer_info (VIP account)")

        if "lookup_known_issues" in tools:
            m003_score += 0.08
        else:
            feedback.append("M003: should have used lookup_known_issues to find BUG-4421")

        resp_m003 = (self._responses_sent.get("M003") or "").lower()
        if resp_m003:
            if self._keywords_present(resp_m003, WORKAROUND_KWS):
                m003_score += 0.07
            else:
                feedback.append(
                    "M003 response: should include the Magic Link workaround"
                )
            if self._keywords_present(resp_m003, ETA_KWS):
                m003_score += 0.04
            else:
                feedback.append("M003 response: should include fix ETA (18:00 UTC)")
            if self._keywords_present(resp_m003, ACCOUNT_MGR_KWS):
                m003_score += 0.03
        else:
            feedback.append("M003: no response was sent (VIP customer!)")
        breakdown["M003"] = round(m003_score, 3)

        # Efficiency bonus
        eff_bonus = 0.05 if self._step <= 18 else 0.0
        breakdown["efficiency_bonus"] = round(eff_bonus, 3)

        total = min(1.0, m001_score + m002_score + m003_score + eff_bonus)

        if not feedback:
            feedback.append("Excellent! All three emails handled correctly with proper tool use.")

        return GraderResult(
            task_id=self.task_id,
            score=round(total, 4),
            breakdown=breakdown,
            feedback=feedback,
            passed=total >= 0.7,
        )
