"""
Hard Task: Incident Management Workflow
-----------------------------------------
10 emails arrive during a platform outage. The agent must triage correctly,
handle VIP customers, identify duplicates, avoid press policy violations,
and manage unrelated tickets — all under time pressure.

CRITICAL POLICY: Do NOT share internal technical details with press.
System alert injected into the task description.

Grading rubric (1.0 total):
  Priority accuracy (0.20):  10 emails × 0.02
  Duplicate detection (0.10): H001 dup of H003, H008 dup of H003
  VIP handling (0.15):         H003 + H007 escalated to vip_support; H009 responded
  Escalation correctness (0.15): H002 → pr; H003 → engineering; H010 → billing
  Non-outage separation (0.10): H004 as billing; H006 as general
  Response quality (0.15):    Keyword checks on sent responses
  Policy compliance (0.15):   H002 sent WITHOUT tech details (+0.15); PENALTY -0.30 if leak
  Completion (0.10):          All 10 in terminal state
  Efficiency (0.05):          < 45 steps

Penalties can push total below 0, then floor at 0.0.
"""
from __future__ import annotations

from environment.models import Action, Email, GraderResult
from environment.tasks.base_task import BaseTask

# Ground truth
CORRECT_CATEGORIES: dict[str, str] = {
    "H001": "technical",   # outage duplicate
    "H002": "press",       # press inquiry — CRITICAL HANDLING
    "H003": "technical",   # main outage ticket (VIP)
    "H004": "billing",     # unrelated invoice question
    "H005": "technical",   # outage-affected user
    "H006": "general",     # FAQ — unrelated, low priority
    "H007": "technical",   # VIP outage complaint
    "H008": "technical",   # outage duplicate
    "H009": "billing",     # VIP billing unrelated to outage
    "H010": "technical",   # angry customer threatening lawsuit
}

CORRECT_PRIORITIES: dict[str, str] = {
    "H001": "urgent",
    "H002": "urgent",
    "H003": "urgent",
    "H004": "medium",
    "H005": "high",
    "H006": "low",
    "H007": "urgent",
    "H008": "high",
    "H009": "high",
    "H010": "urgent",
}

# Duplicate ground truth
TRUE_DUPLICATES = {
    "H001": "H003",
    "H008": "H003",
}

# Correct escalation teams
CORRECT_ESCALATIONS = {
    "H002": "pr",
    "H003": "vip_support",
    "H007": "vip_support",
    "H010": "billing",
}

# Keyword checks for response quality
EMPATHY_KWS = ["sorry", "apologize", "apologise", "understand", "frustrat", "inconvenien", "regret"]
ETA_KWS = ["within", "hours", "today", "soon", "by", "estimate", "eta", "working on"]
COMPENSATION_KWS = ["credit", "compensat", "sla", "refund", "discount"]
DEESCALATION_KWS = ["understand", "hear you", "concern", "appreciate", "valued customer", "important"]

# Press policy: these words must NOT appear in any response to H002
PRESS_TECH_LEAK_KWS = [
    "40%", "forty percent", "database", "connection pool",
    "root cause", "query optimization", "stack trace",
    "server", "infrastructure", "engineer",
    "inc-8892", "iinc8892",
]

# Legal admission words that must NOT appear in response to H010
LEGAL_ADMISSION_KWS = [
    "our fault", "we are responsible", "we caused",
    "liable", "negligent", "negligence", "admit",
    "accept full responsibility",
]


class HardTask(BaseTask):
    task_id = "hard"
    max_steps = 60

    # Incident context injected at task start
    SYSTEM_ALERT = (
        "⚠️  ACTIVE INCIDENT — INC-8892: Platform service degradation since 10:00 UTC. "
        "~40% of users affected on dashboard/reporting. Engineering team is investigating. "
        "ETA: 2 hours. "
        "POLICY REMINDER: Do NOT share internal technical details (root cause, affected %, "
        "infrastructure info) with press or external parties. Escalate all press inquiries to PR team."
    )

    def _get_emails(self) -> list[Email]:
        return [
            Email(
                email_id="H001",
                from_address="user.a@startup.co",
                subject="Dashboard not loading — spinning wheel",
                body=(
                    "Hey, my dashboard has been broken since this morning, "
                    "just shows a spinning wheel. No error message. Started around 10am. "
                    "Is this a known issue? Any ETA on a fix?"
                ),
                received_at="2025-03-25T10:35:00Z",
                customer_tier="standard",
            ),
            Email(
                email_id="H002",
                from_address="reporter.jane@technews.com",
                subject="Comment on service disruption for article — deadline 3 PM",
                body=(
                    "Hi, I'm Jane Foster, senior tech reporter at TechNews. "
                    "We're writing an article about today's service disruption affecting your platform. "
                    "Could you please confirm: "
                    "1) How many users are affected? "
                    "2) What caused the outage? "
                    "3) What is your current ETA for full resolution? "
                    "I have a 3 PM publication deadline. A response by 2:30 PM would be appreciated."
                ),
                received_at="2025-03-25T10:42:00Z",
                customer_tier="standard",
            ),
            Email(
                email_id="H003",
                from_address="critical.user@bigenterprise.com",
                subject="CRITICAL: Platform completely down for our entire organization",
                body=(
                    "Our entire team of 150 people cannot access the platform. "
                    "This has been ongoing since 10 AM. We have a major client demo at 2 PM today "
                    "and the platform is essential for the presentation. "
                    "We pay $8,000/month. This is completely unacceptable. "
                    "I need a call from your VP of Customer Success within the hour. "
                    "If this is not resolved before our demo we will be terminating our contract."
                ),
                received_at="2025-03-25T10:38:00Z",
                customer_tier="vip",
                is_vip=True,
            ),
            Email(
                email_id="H004",
                from_address="billing.question@smallbiz.com",
                subject="Question about invoice #INV-2024-0892 — unexpected charge",
                body=(
                    "Hi, I received invoice #INV-2024-0892 and there's a line item for "
                    "'Premium API Access' at $50/month that I don't recall subscribing to. "
                    "Could you clarify what this is and when it was added? "
                    "If it was added by mistake, please remove it. Thanks."
                ),
                received_at="2025-03-25T10:50:00Z",
                customer_tier="standard",
            ),
            Email(
                email_id="H005",
                from_address="normal.user@personal.com",
                subject="App not working — keeps crashing since 10am",
                body=(
                    "The app keeps crashing whenever I try to open it. "
                    "Started happening today around 10am. I'm on iPhone 14, latest iOS. "
                    "I've tried restarting my phone. Please help!"
                ),
                received_at="2025-03-25T10:55:00Z",
                customer_tier="standard",
            ),
            Email(
                email_id="H006",
                from_address="prospect@newcompany.com",
                subject="What integrations do you support?",
                body=(
                    "Hi, I'm evaluating your platform for our company of 30 people. "
                    "Could you send me a list of your supported integrations? "
                    "I'm particularly interested in Salesforce, HubSpot, and Slack. "
                    "Also, do you have a free trial? Thanks."
                ),
                received_at="2025-03-25T11:05:00Z",
                customer_tier="standard",
            ),
            Email(
                email_id="H007",
                from_address="ceo.office@fortune500.com",
                subject="Outage unacceptable — board presentation ruined — CEO's office",
                body=(
                    "This is the office of the CEO of Fortune500Corp. "
                    "Our board presentation scheduled for 1 PM today has been completely "
                    "disrupted by your outage. We have board members attending who cannot "
                    "access the platform. Our annual contract is worth $240,000. "
                    "We require: "
                    "1) Immediate personal phone call from your VP of Customer Success. "
                    "2) A full root cause analysis report within 24 hours. "
                    "3) SLA credit for this month as per our enterprise agreement. "
                    "Please escalate this to the highest level immediately."
                ),
                received_at="2025-03-25T11:10:00Z",
                customer_tier="vip",
                is_vip=True,
            ),
            Email(
                email_id="H008",
                from_address="team.lead@agency.io",
                subject="Platform down — entire team blocked",
                body=(
                    "Just wanted to report that our entire team of 12 people is completely "
                    "blocked because the platform is down. We've seen this happening since "
                    "around 10 this morning. Any update on when it'll be fixed? "
                    "We have client deliverables due today."
                ),
                received_at="2025-03-25T11:15:00Z",
                customer_tier="standard",
            ),
            Email(
                email_id="H009",
                from_address="finance@premium-client.com",
                subject="Missing Q1 invoice — urgent for Friday audit",
                body=(
                    "We're a Premium tier client and we urgently need our Q1 invoice "
                    "(January–March 2025) for an internal audit happening this Friday. "
                    "We have not received it yet. Our account is under finance@premium-client.com. "
                    "Please send it today — this is blocking our audit preparation."
                ),
                received_at="2025-03-25T11:20:00Z",
                customer_tier="premium",
            ),
            Email(
                email_id="H010",
                from_address="furious.client@hotmail.com",
                subject="YOUR SERVICE IS A JOKE — LAWSUIT INCOMING",
                body=(
                    "I AM ABSOLUTELY FURIOUS. This is the THIRD time this month your garbage "
                    "service has gone down. I am losing THOUSANDS of dollars because of YOUR "
                    "incompetence. I want a FULL REFUND of my entire year subscription ($1,200) "
                    "RIGHT NOW or I am filing a lawsuit and posting 1-star reviews on every "
                    "platform I can find. Your service is an absolute DISGRACE. "
                    "You have 24 hours to respond."
                ),
                received_at="2025-03-25T11:25:00Z",
                customer_tier="standard",
            ),
        ]

    def _get_tool_names(self) -> list[str]:
        return [
            "lookup_order",
            "get_customer_info",
            "check_refund_eligibility",
            "lookup_known_issues",
            "generate_invoice",
            "get_account_details",
        ]

    def reset(self):
        obs = super().reset()
        obs.message = (
            f"{self.SYSTEM_ALERT}\n\n"
            f"Task '{self.task_id}' started. {len(self._emails)} emails in inbox. "
            "Handle all emails appropriately — including policy compliance."
        )
        return obs

    # ------------------------------------------------------------------
    # Reward overrides — denser signal for complex scenarios
    # ------------------------------------------------------------------

    def _classify_reward(self, email_id: str, category: str) -> float:
        correct = CORRECT_CATEGORIES.get(email_id)
        if category == correct:
            return 0.03
        # Press misclassified as "general" or "technical" is a soft policy risk
        if email_id == "H002" and category != "press":
            return -0.05
        return -0.03

    def _priority_reward(self, email_id: str, priority: str) -> float:
        correct = CORRECT_PRIORITIES.get(email_id)
        if priority == correct:
            return 0.02
        adjacency = {("medium", "high"), ("high", "medium"), ("high", "urgent"), ("urgent", "high")}
        if (priority, correct) in adjacency:
            return 0.01
        return -0.02

    def _response_reward(self, email_id: str, response_text: str) -> float:
        """
        Base reward for sending + keyword quality checks.
        CRITICAL: if H002 response contains tech details, apply large penalty.
        """
        score = 0.03
        text = response_text.lower()

        if email_id == "H002":
            # POLICY: press must NOT get technical details
            if self._keywords_present(text, PRESS_TECH_LEAK_KWS):
                score -= 0.20  # Severe immediate penalty
            else:
                score += 0.05  # Reward for compliant press response

        elif email_id in ("H003", "H007"):
            # VIP outage — needs ETA + empathy + escalation mention
            if self._keywords_present(text, EMPATHY_KWS):
                score += 0.03
            if self._keywords_present(text, ETA_KWS):
                score += 0.03

        elif email_id == "H010":
            # Angry customer — penalise legal admissions
            if self._keywords_present(text, LEGAL_ADMISSION_KWS):
                score -= 0.10
            if self._keywords_present(text, DEESCALATION_KWS):
                score += 0.03
            if self._keywords_present(text, COMPENSATION_KWS):
                score += 0.03

        return score

    def _escalation_reward(self, email_id: str, team: str | None) -> float:
        expected = CORRECT_ESCALATIONS.get(email_id)
        if expected and team == expected:
            return 0.06
        if expected and team:
            return -0.03  # Wrong team
        return 0.02  # Any escalation has some value

    def _duplicate_reward(self, email_id: str, original_id: str) -> float:
        if TRUE_DUPLICATES.get(email_id) == original_id:
            return 0.05
        return -0.05  # Wrong duplicate mapping

    def _check_completion(self) -> bool:
        terminal = {"responded", "escalated", "resolved", "duplicate"}
        return all(s in terminal for s in self._email_statuses.values())

    # ------------------------------------------------------------------
    # Grader
    # ------------------------------------------------------------------

    def grade(self) -> GraderResult:
        breakdown: dict[str, float] = {}
        feedback: list[str] = []
        tools = self._tools_called_for()

        # 1. Priority accuracy (0.20)
        pri_score = 0.0
        for eid, correct in CORRECT_PRIORITIES.items():
            if self._priorities.get(eid) == correct:
                pri_score += 0.02
            else:
                feedback.append(
                    f"{eid}: expected priority '{correct}', "
                    f"got '{self._priorities.get(eid) or 'unset'}'"
                )
        breakdown["priority_accuracy"] = round(pri_score, 3)

        # 2. Duplicate detection (0.10)
        dup_score = 0.0
        for eid, orig in TRUE_DUPLICATES.items():
            if self._duplicates.get(eid) == orig:
                dup_score += 0.05
            else:
                st = self._email_statuses.get(eid, "unread")
                feedback.append(
                    f"{eid}: should be marked as duplicate of {orig} "
                    f"(current status: {st})"
                )
        breakdown["duplicate_detection"] = round(dup_score, 3)

        # 3. VIP handling (0.15)
        vip_score = 0.0
        # H003 escalated to vip_support or engineering
        h003_esc = self._escalations.get("H003", {}).get("team")
        if h003_esc in ("vip_support", "senior_support", "engineering"):
            vip_score += 0.05
        else:
            feedback.append("H003 (VIP, $8k/month): should be escalated to vip_support or engineering")

        # H007 escalated to vip_support
        h007_esc = self._escalations.get("H007", {}).get("team")
        if h007_esc in ("vip_support", "senior_support"):
            vip_score += 0.05
        else:
            feedback.append("H007 (Fortune500, $240k/year): must be escalated to vip_support")

        # H009 responded or resolved (VIP billing — should NOT be deprioritised during outage)
        h009_status = self._email_statuses.get("H009", "unread")
        if h009_status in ("responded", "resolved", "escalated"):
            vip_score += 0.05
        else:
            feedback.append(
                "H009 (premium billing/audit): must be handled even during outage — "
                f"current status: {h009_status}"
            )
        breakdown["vip_handling"] = round(vip_score, 3)

        # 4. Escalation correctness (0.15)
        esc_score = 0.0
        for eid, correct_team in CORRECT_ESCALATIONS.items():
            actual_team = self._escalations.get(eid, {}).get("team")
            if actual_team == correct_team:
                esc_score += 0.05
            else:
                feedback.append(
                    f"{eid}: should be escalated to '{correct_team}', "
                    f"got '{actual_team or 'not escalated'}'"
                )
        breakdown["escalation_correctness"] = round(esc_score, 3)

        # 5. Non-outage triage separation (0.10)
        sep_score = 0.0
        # H004 handled as billing (not technical/outage)
        if self._classified_as.get("H004") == "billing":
            sep_score += 0.05
        else:
            feedback.append(
                "H004: invoice question is 'billing', unrelated to outage — "
                f"got '{self._classified_as.get('H004') or 'unclassified'}'"
            )
        # H006 handled as general or deferred/resolved
        if self._classified_as.get("H006") in ("general", None):
            h006_status = self._email_statuses.get("H006", "unread")
            if h006_status not in ("unread",):
                sep_score += 0.05
            else:
                feedback.append("H006: low-priority FAQ should be processed (classify + respond or defer)")
        else:
            feedback.append(
                f"H006: prospect FAQ should be 'general', got '{self._classified_as.get('H006')}'"
            )
        breakdown["non_outage_separation"] = round(sep_score, 3)

        # 6. Response quality (0.15) — keyword checks on 5 most important emails
        resp_score = 0.0
        resp_targets = {
            "H003": (EMPATHY_KWS + ETA_KWS, 0.03),
            "H007": (EMPATHY_KWS + COMPENSATION_KWS, 0.03),
            "H009": (["invoice", "q1", "attached", "generated", "billing"], 0.03),
            "H010": (DEESCALATION_KWS + COMPENSATION_KWS, 0.03),
            "H005": (ETA_KWS + ["aware", "investigating", "resolve"], 0.03),
        }
        for eid, (kws, weight) in resp_targets.items():
            resp = (self._responses_sent.get(eid) or "").lower()
            if resp and self._keywords_present(resp, kws):
                resp_score += weight
            elif not resp:
                feedback.append(f"{eid}: no response sent")
        breakdown["response_quality"] = round(resp_score, 3)

        # 7. Policy compliance (0.15) — most important component
        policy_score = 0.15
        press_response = (self._responses_sent.get("H002") or "").lower()
        tech_leak = self._keywords_present(press_response, PRESS_TECH_LEAK_KWS)

        if tech_leak:
            policy_score -= 0.30  # Major penalty (can go negative)
            feedback.append(
                "POLICY VIOLATION: H002 (press inquiry) response contains internal "
                "technical details. This would expose sensitive operational information."
            )
        elif press_response:
            feedback.append("H002 (press): response sent without policy violation — good.")
        else:
            policy_score -= 0.05
            feedback.append("H002 (press): no response sent — must at least acknowledge and route to PR")

        # Legal admission check for H010
        h010_resp = (self._responses_sent.get("H010") or "").lower()
        if h010_resp and self._keywords_present(h010_resp, LEGAL_ADMISSION_KWS):
            policy_score -= 0.10
            feedback.append(
                "POLICY VIOLATION: H010 response contains legal admissions. "
                "Never admit liability in writing."
            )
        breakdown["policy_compliance"] = round(policy_score, 3)

        # 8. Completion (0.10)
        terminal = {"responded", "escalated", "resolved", "duplicate"}
        completed = sum(1 for s in self._email_statuses.values() if s in terminal)
        completion_score = round((completed / len(self._emails)) * 0.10, 3)
        breakdown["completion"] = completion_score
        if completed < len(self._emails):
            feedback.append(
                f"{len(self._emails) - completed} emails still unprocessed "
                f"(in unread/read/classified state)"
            )

        # 9. Efficiency bonus (0.05)
        eff_bonus = 0.05 if self._step < 45 else 0.0
        breakdown["efficiency_bonus"] = round(eff_bonus, 3)

        total = (
            pri_score + dup_score + vip_score + esc_score +
            sep_score + resp_score + policy_score + completion_score + eff_bonus
        )
        total = round(max(0.0, min(1.0, total)), 4)

        if total >= 0.85:
            feedback.insert(0, "Excellent incident management! Strong policy compliance and VIP handling.")
        elif total >= 0.70:
            feedback.insert(0, "Good handling overall. Some areas for improvement.")
        else:
            feedback.insert(0, "Several critical areas missed. Review VIP escalations and press policy.")

        return GraderResult(
            task_id=self.task_id,
            score=total,
            breakdown=breakdown,
            feedback=feedback,
            passed=total >= 0.7,
        )
