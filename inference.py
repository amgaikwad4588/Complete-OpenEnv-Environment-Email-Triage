"""
Inference Script
===================================
MANDATORY
- Before submitting, ensure the following variables are defined in your environment configuration:
    API_BASE_URL   The API endpoint for the LLM.
    MODEL_NAME     The model identifier to use for inference.
    HF_TOKEN       Your Hugging Face / API key.

- The inference script must be named `inference.py` and placed in the root directory of the project
- Participants must use OpenAI Client for all LLM calls using above variables
"""

from __future__ import annotations

import json
import os
import re
import sys
import time
from typing import Any

import httpx
from openai import OpenAI

# ---------------------------------------------------------------------------
# Configuration (mandatory env vars)
# ---------------------------------------------------------------------------

API_BASE_URL = os.getenv("API_BASE_URL", "https://router.huggingface.co/v1")
API_KEY = os.getenv("HF_TOKEN") or os.getenv("API_KEY")
MODEL_NAME = os.getenv(
    "MODEL_NAME", "meta-llama/Llama-4-Maverick-17B-128E-Instruct-FP8"
)

ENV_BASE_URL = os.getenv("ENV_BASE_URL", "http://localhost:7860").rstrip("/")
SEED = 42
MAX_RETRIES = 3
REQUEST_TIMEOUT = 30.0

SYSTEM_PROMPT = """You are an expert customer support agent. You are working in an email triage system.
Your job is to process each email in the inbox by:

1. Reading emails one at a time using read_email
2. Classifying each email by category and priority
3. Using available tools when needed (lookup_order, get_customer_info, etc.)
4. Drafting and sending appropriate responses
5. Escalating to the right team when required
6. Marking duplicate emails
7. Resolving emails when done

IMPORTANT RULES:
- Always read an email before classifying or responding to it
- For press/media inquiries: ONLY say you'll have a public statement — do NOT share any technical details, numbers, or root cause information
- Escalate VIP customers (vip tier) with critical issues to vip_support team
- For duplicate emails: use mark_duplicate action pointing to the original
- Use tools when they would help you give a more accurate response
- Respond with genuine empathy and professionalism

You must respond with a single JSON object matching this Action schema:
{
  "action_type": "<one of: read_email | classify_email | set_priority | use_tool | draft_response | send_response | escalate | resolve | mark_duplicate>",
  "email_id": "<email ID or null>",
  "category": "<shipping|billing|technical|refund|general|outage|press or null>",
  "priority": "<low|medium|high|urgent or null>",
  "tool_name": "<tool name or null>",
  "tool_params": {<params dict> or null},
  "response_text": "<response text or null>",
  "escalation_team": "<engineering|billing|legal|pr|vip_support|senior_support or null>",
  "escalation_reason": "<reason or null>",
  "duplicate_of": "<email_id or null>"
}

Only include fields relevant to the action. All other fields should be null or omitted.
"""


# ---------------------------------------------------------------------------
# Observation formatter
# ---------------------------------------------------------------------------


def format_observation(obs: dict[str, Any]) -> str:
    """Convert observation dict to a clear natural-language prompt."""
    lines = [
        f"=== INBOX STATUS | Task: {obs['task_id']} | Step {obs['step']}/{obs['max_steps']} ===",
        f"Score so far: {obs.get('score', 0):.3f}",
    ]

    if obs.get("message"):
        lines.append(f"\nLast action result: {obs['message']}")

    lines.append("\n--- INBOX ---")
    for email in obs.get("inbox_summary", []):
        status_icon = {
            "unread": "[NEW]",
            "read": "[READ]",
            "classified": "[CLASSIFIED]",
            "responded": "[RESPONDED]",
            "escalated": "[ESCALATED]",
            "resolved": "[RESOLVED]",
            "duplicate": "[DUPLICATE]",
        }.get(email["status"], "[?]")
        cat = f" [{email.get('category', '?')}]" if email.get("category") else ""
        pri = f" {email.get('priority', '?').upper()}" if email.get("priority") else ""
        tier = (
            f" ({email['customer_tier']})"
            if email["customer_tier"] != "standard"
            else ""
        )
        lines.append(
            f"  {status_icon} {email['email_id']}{tier}: {email['subject']}{cat}{pri}"
        )

    if obs.get("current_email"):
        e = obs["current_email"]
        tier_note = (
            f" [{e['customer_tier'].upper()} CUSTOMER]"
            if e["customer_tier"] != "standard"
            else ""
        )
        lines.extend(
            [
                f"\n--- CURRENT EMAIL: {e['email_id']}{tier_note} ---",
                f"From: {e['from_address']}",
                f"Subject: {e['subject']}",
                f"Received: {e.get('received_at', 'unknown')}",
                f"Body:\n{e['body']}",
            ]
        )

    if obs.get("last_tool_result"):
        tr = obs["last_tool_result"]
        lines.extend(
            [
                f"\n--- TOOL RESULT ({tr.get('tool', 'unknown')}) ---",
                json.dumps(tr.get("result", {}), indent=2),
            ]
        )

    if obs.get("available_tools"):
        tool_names = [t["name"] for t in obs["available_tools"]]
        lines.append(f"\nAvailable tools: {', '.join(tool_names)}")

    lines.append("\nWhat action do you take? Respond with JSON only.")
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Episode runner
# ---------------------------------------------------------------------------


def run_episode(client: OpenAI, task_id: str, verbose: bool = False) -> dict[str, Any]:
    """Run a single episode for a task using the LLM agent."""

    resp = httpx.post(
        f"{ENV_BASE_URL}/reset",
        json={"task_id": task_id},
        timeout=REQUEST_TIMEOUT,
    )
    resp.raise_for_status()
    data = resp.json()
    session_id = data["session_id"]
    obs = data["observation"]
    headers = {"X-Session-ID": session_id}

    if verbose:
        print(f"\n[{task_id}] Session: {session_id}")
        print(f"[{task_id}] Starting episode with {len(obs['inbox_summary'])} emails")

    conversation: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]

    step_count = 0
    done = obs.get("done", False)

    while not done:
        user_msg = format_observation(obs)
        conversation.append({"role": "user", "content": user_msg})

        for attempt in range(MAX_RETRIES):
            try:
                response = client.chat.completions.create(
                    model=MODEL_NAME,
                    messages=conversation,
                    response_format={"type": "json_object"},
                    temperature=0.0,
                    seed=SEED,
                    max_tokens=512,
                )
                action_text = response.choices[0].message.content
                break
            except Exception as exc:
                if attempt == MAX_RETRIES - 1:
                    raise
                print(f"  LLM call failed (attempt {attempt + 1}): {exc}")
                time.sleep(2**attempt)

        try:
            action_dict = json.loads(action_text)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", action_text, re.DOTALL)
            action_dict = (
                json.loads(match.group()) if match else {"action_type": "resolve"}
            )

        conversation.append({"role": "assistant", "content": action_text})

        if verbose:
            print(
                f"  Step {step_count + 1}: {action_dict.get('action_type')} "
                f"email={action_dict.get('email_id')} "
                f"cat={action_dict.get('category')} "
                f"tool={action_dict.get('tool_name')}"
            )

        step_resp = httpx.post(
            f"{ENV_BASE_URL}/step",
            json=action_dict,
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
        step_resp.raise_for_status()
        step_data = step_resp.json()

        obs = step_data["observation"]
        done = step_data["done"]
        step_count += 1

        if step_count > obs.get("max_steps", 60) + 5:
            print(f"  WARNING: Exceeded max steps, breaking")
            break

    grade_resp = httpx.get(
        f"{ENV_BASE_URL}/grader",
        headers=headers,
        timeout=REQUEST_TIMEOUT,
    )
    grade_resp.raise_for_status()
    grade_data = grade_resp.json()["grader"]

    result = {
        "task_id": task_id,
        "score": grade_data["score"],
        "passed": grade_data["passed"],
        "steps_taken": step_count,
        "grader_breakdown": grade_data["breakdown"],
        "feedback": grade_data.get("feedback", [])[:5],
        "session_id": session_id,
    }

    if verbose:
        print(f"[{task_id}] Final score: {result['score']:.4f} | Steps: {step_count}")
        for line in result["feedback"]:
            print(f"  - {line}")

    return result


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------


def main() -> None:
    if not API_KEY:
        print("ERROR: HF_TOKEN environment variable not set", file=sys.stderr)
        sys.exit(1)

    client = OpenAI(base_url=API_BASE_URL, api_key=API_KEY)

    # Verify server is reachable
    try:
        health = httpx.get(f"{ENV_BASE_URL}/health", timeout=5.0)
        health.raise_for_status()
        print(f"Server OK: {ENV_BASE_URL}")
    except Exception as exc:
        print(f"ERROR: Cannot reach server at {ENV_BASE_URL}: {exc}", file=sys.stderr)
        print(
            "Start the server with: uvicorn app:app --host 0.0.0.0 --port 7860",
            file=sys.stderr,
        )
        sys.exit(1)

    results = []
    for task_id in ["easy", "medium", "hard"]:
        print(f"\n{'=' * 60}")
        print(f"Running task: {task_id.upper()}")
        print("=" * 60)
        try:
            result = run_episode(client, task_id, verbose=True)
            results.append(result)
        except Exception as exc:
            print(f"ERROR on task {task_id}: {exc}", file=sys.stderr)
            results.append(
                {
                    "task_id": task_id,
                    "score": 0.0,
                    "passed": False,
                    "steps_taken": 0,
                    "grader_breakdown": {},
                    "feedback": [str(exc)],
                    "error": str(exc),
                }
            )

    # Summary
    print(f"\n{'=' * 60}")
    print("INFERENCE RESULTS SUMMARY")
    print("=" * 60)
    print(f"{'Task':<12} {'Score':>8} {'Passed':>8} {'Steps':>8}")
    print("-" * 40)
    for r in results:
        status = "PASS" if r["passed"] else "FAIL"
        print(
            f"{r['task_id']:<12} {r['score']:>8.4f} {status:>8} {r['steps_taken']:>8}"
        )

    avg = sum(r["score"] for r in results) / len(results) if results else 0
    print(f"\nAverage score: {avg:.4f}")
    print(f"Model: {MODEL_NAME}")
    print(f"API Base: {API_BASE_URL}")


if __name__ == "__main__":
    main()
