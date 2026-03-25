# Email Triage OpenEnv

[![OpenEnv](https://img.shields.io/badge/OpenEnv-1.0.0-blue)](https://openenv.dev)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

A **real-world customer support email triage environment** for training and evaluating AI agents. Agents must read, classify, prioritise, and respond to support emails — using tool calls where needed — across three tasks of increasing complexity.

---

## Why This Environment?

Every customer-facing company has a support inbox. Training agents to triage and respond to support emails is one of the most immediately applicable AI use cases. This environment models:

- **Multi-step decision making** — read → classify → tool use → respond → escalate
- **Policy compliance** — critical rules (never share technical details with press)
- **Priority judgement** — VIP customers, incident management, duplicate detection
- **Tool use under uncertainty** — agents must call the right tools to get the information needed to respond accurately

---

## Environment Description

The environment simulates a customer support inbox. At each step the agent takes one action from the action space. Rewards provide dense signals throughout the episode, and a deterministic grader scores the final state.

### Action Space

| Action | Required Fields | Description |
|--------|-----------------|-------------|
| `read_email` | `email_id` | Read the full body of an email |
| `classify_email` | `email_id`, `category` | Assign category: `shipping` \| `billing` \| `technical` \| `refund` \| `general` \| `outage` \| `press` |
| `set_priority` | `email_id`, `priority` | Set priority: `low` \| `medium` \| `high` \| `urgent` |
| `use_tool` | `tool_name`, `tool_params` | Call a named tool (lookup_order, get_customer_info, etc.) |
| `draft_response` | `email_id`, `response_text` | Preview a response (no side effects) |
| `send_response` | `email_id`, `response_text` | Send a response to the customer |
| `escalate` | `email_id`, `escalation_team`, `escalation_reason` | Route to: `engineering` \| `billing` \| `legal` \| `pr` \| `vip_support` \| `senior_support` |
| `resolve` | `email_id` | Mark email as resolved |
| `mark_duplicate` | `email_id`, `duplicate_of` | Mark email as duplicate of another |

### Observation Space

Each observation contains:
- `task_id` — current task
- `step` / `max_steps` — progress tracking
- `inbox_summary` — list of all emails with current status (category, priority)
- `current_email` — full email content (only after `read_email`)
- `available_tools` — tool definitions for the current task
- `last_tool_result` — result of the most recent tool call
- `email_statuses` — map of email_id → status
- `classified_as` / `priorities` — current classifications
- `message` — human-readable result of the last action
- `done` — whether the episode has ended
- `score` — running cumulative score estimate (0.0–1.0)

### Available Tools

| Tool | Description |
|------|-------------|
| `lookup_order(order_id)` | Get order status, tracking, and delivery info |
| `get_customer_info(email)` | Retrieve customer account and tier information |
| `check_refund_eligibility(email, purchase_date)` | Check if a customer qualifies for a refund |
| `lookup_known_issues(issue_type, date)` | Find known engineering issues and workarounds |
| `generate_invoice(email, period)` | Generate or retrieve a billing invoice |
| `get_account_details(email)` | Full account + subscription details |

---

## Tasks

### Task 1: Easy — Email Classification (15 steps max)

**Objective**: Classify 5 support emails by category and priority.

5 emails covering: shipping delay, billing duplicate charge, API outage, wrong item return, general inquiry.

**Scoring**:
- Category accuracy: 5 × 0.10 = **0.50**
- Priority accuracy: 5 × 0.06 = **0.30**
- All emails read: **0.10**
- Completion bonus: **0.10**

**Expected difficulty**: A capable LLM should score ~0.80+

### Task 2: Medium — Tool-Assisted Response Drafting (30 steps max)

**Objective**: Handle 3 emails requiring tool lookups before accurate responses can be sent.

Emails: (1) premium customer with a 2-week delayed order stuck at customs, (2) first-time buyer requesting a refund 32 days after purchase (2 days past policy), (3) VIP enterprise customer with broken SSO after a platform update.

**Scoring** (per email): category + priority + correct tool use + response quality keywords. Efficiency bonus for ≤18 steps.

**Key insight**: The refund email requires checking eligibility AND customer history (first-time buyer) to determine a goodwill exception is warranted. The SSO email requires finding the known issue and workaround.

**Expected difficulty**: Requires multi-step reasoning and appropriate tool selection.

### Task 3: Hard — Incident Management Workflow (60 steps max)

**Objective**: Manage 10 emails during a live product outage.

The system alert at episode start reads:
> ⚠️ ACTIVE INCIDENT — INC-8892: Platform service degradation since 10:00 UTC. ~40% of users affected. Engineering team investigating. POLICY REMINDER: Do NOT share internal technical details with press.

| Email | Scenario | Key Requirement |
|-------|----------|-----------------|
| H001 | User reports spinning dashboard | Mark as duplicate of H003 |
| H002 | Press inquiry (Jane Foster, TechNews) | Escalate to PR — **NEVER share technical details** |
| H003 | VIP ($8k/month) with 150 blocked employees | Escalate to vip_support + engineering |
| H004 | Billing question about invoice | Handle as billing — **unrelated to outage** |
| H005 | User app crashing since 10am | Acknowledge outage, send ETA |
| H006 | Prospect asking about integrations | Handle as general, low priority |
| H007 | Fortune500 CEO office ($240k/year) | Escalate to vip_support immediately |
| H008 | Team of 12 blocked | Mark as duplicate of H003 |
| H009 | Premium client needs Q1 invoice for audit | **Must not be deprioritised** — use generate_invoice |
| H010 | Angry customer threatening lawsuit | De-escalate, escalate to billing — **no legal admissions** |

**Scoring**: Priority (0.20) + duplicates (0.10) + VIP handling (0.15) + escalations (0.15) + non-outage separation (0.10) + response quality (0.15) + **policy compliance (0.15)** + completion (0.10) + efficiency (0.05).

**Penalty**: Sharing technical details with the press (H002) incurs **-0.30** penalty. Legal admissions in H010 response incur **-0.10**.

**Expected difficulty**: Challenges frontier models on policy compliance + multi-dimensional triage.

---

## Reward Function

Rewards are provided at each step (dense signal):

| Action | Reward |
|--------|--------|
| `read_email` | +0.01 |
| `classify_email` (correct) | +0.03–0.10 (task-dependent) |
| `classify_email` (wrong) | −0.03–0.05 |
| `use_tool` (successful) | +0.03 |
| `use_tool` (invalid tool) | −0.05 |
| `send_response` (quality bonus) | +0.03–0.15 |
| `escalate` (correct team) | +0.05–0.08 |
| `escalate` (wrong team) | −0.03 |
| `mark_duplicate` (correct) | +0.05 |
| `mark_duplicate` (wrong) | −0.05 |
| Press response with tech details | −0.20 (immediate) |
| Episode completion before limit | +0.05 × (remaining/max) |

Final authoritative score is always from the deterministic grader (`GET /grader`).

---

## API Reference

All endpoints return JSON. Session state is managed via `X-Session-ID` header.

### POST /reset

Start or reset an episode.

```bash
curl -X POST http://localhost:7860/reset \
  -H "Content-Type: application/json" \
  -d '{"task_id": "easy"}'
```

Response includes `session_id` — use this in all subsequent requests.

### POST /step

Take one action.

```bash
curl -X POST http://localhost:7860/step \
  -H "Content-Type: application/json" \
  -H "X-Session-ID: <session_id>" \
  -d '{"action_type": "read_email", "email_id": "E001"}'
```

### GET /state

View current observation without consuming a step.

```bash
curl http://localhost:7860/state \
  -H "X-Session-ID: <session_id>"
```

### GET /tasks

List all tasks and the Action JSON Schema.

```bash
curl http://localhost:7860/tasks
```

### GET /grader

Get deterministic grader score.

```bash
curl http://localhost:7860/grader \
  -H "X-Session-ID: <session_id>"
```

### POST /baseline

Run the built-in heuristic baseline on all 3 tasks.

```bash
curl -X POST http://localhost:7860/baseline
```

---

## Setup

### Local Development

```bash
# Install dependencies
pip install -r requirements.txt

# Start server
uvicorn app:app --reload --host 0.0.0.0 --port 7860

# Or with uv:
uv run uvicorn app:app --host 0.0.0.0 --port 7860
```

### Docker

```bash
# Build
docker build -t email-triage-env .

# Run (server only)
docker run -p 7860:7860 email-triage-env

# Run with OpenAI key (for LLM baseline)
docker run -p 7860:7860 -e OPENAI_API_KEY=sk-... email-triage-env
```

### Run LLM Baseline

```bash
export OPENAI_API_KEY=sk-...
export ENV_BASE_URL=http://localhost:7860  # default

# Full verbose run
python -m baseline.run_baseline

# Or quiet mode
python -m baseline.run_baseline --quiet
```

### Run Heuristic Baseline (no API key needed)

```bash
python -m baseline.heuristic_baseline
```

---

## Baseline Scores

Scores from the built-in heuristic (rule-based, no LLM) baseline:

| Task | Score | Notes |
|------|-------|-------|
| easy | ~0.82 | Near-perfect classification; some priority misses |
| medium | ~0.68 | Correct tool use; response quality partially matched |
| hard | ~0.55 | Duplicates detected; VIP handled; some escalation gaps |

LLM baseline (gpt-4o-mini, seed=42):

| Task | Score | Notes |
|------|-------|-------|
| easy | ~0.90 | Almost perfect classification |
| medium | ~0.75 | Good tool use and response quality |
| hard | ~0.62 | Press policy compliance is the key differentiator |

*(Scores may vary slightly with model updates)*

---

## Project Structure

```
email-triage-env/
├── openenv.yaml              # OpenEnv spec manifest
├── Dockerfile                # Container config (HF Spaces compatible)
├── requirements.txt          # Python dependencies
├── pyproject.toml            # Package config
├── README.md                 # This file
├── app.py                    # FastAPI server (all endpoints)
├── environment/
│   ├── __init__.py
│   ├── models.py             # Pydantic models (Observation, Action, etc.)
│   ├── env.py                # EmailTriageEnv coordinator
│   ├── tools.py              # Deterministic mock tool functions
│   └── tasks/
│       ├── __init__.py       # Task registry
│       ├── base_task.py      # Abstract base with action dispatch
│       ├── task_easy.py      # Easy: classify 5 emails
│       ├── task_medium.py    # Medium: tool-assisted responses
│       └── task_hard.py      # Hard: incident management
└── baseline/
    ├── __init__.py
    ├── heuristic_baseline.py # Rule-based baseline (no API key needed)
    └── run_baseline.py       # LLM-based baseline (requires OPENAI_API_KEY)
```

---

## License

MIT
