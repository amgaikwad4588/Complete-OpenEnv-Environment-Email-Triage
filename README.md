---
title: Email Triage Env
emoji: "\U0001F4E7"
colorFrom: blue
colorTo: purple
sdk: docker
pinned: false
tags:
  - openenv
---

# Email Triage OpenEnv

A realistic customer support email triage environment for training and evaluating AI agents. Agents must read, classify, prioritize, and respond to support emails — with tool use, policy compliance, and incident management challenges.

## Motivation

Email triage is one of the most common knowledge-worker tasks: every support team manually reads, categorizes, routes, and responds to incoming tickets. This environment models that workflow faithfully so agents can be trained and benchmarked on a task with real commercial value.

## Action Space

Each action is a JSON object with an `action_type` and relevant fields:

| action_type      | Required fields                       | Description                          |
|------------------|---------------------------------------|--------------------------------------|
| `read_email`     | `email_id`                            | Open and read an email               |
| `classify_email` | `email_id`, `category`                | Assign category to an email          |
| `set_priority`   | `email_id`, `priority`                | Assign priority level                |
| `use_tool`       | `tool_name`, `tool_params`            | Call an environment tool             |
| `draft_response` | `email_id`, `response_text`           | Draft a response (not yet sent)      |
| `send_response`  | `email_id`                            | Send the drafted response            |
| `escalate`       | `email_id`, `escalation_team`, `escalation_reason` | Escalate to a team     |
| `resolve`        | `email_id`                            | Mark email as resolved               |
| `mark_duplicate` | `email_id`, `duplicate_of`            | Mark as duplicate of another email   |

**Categories**: `shipping`, `billing`, `technical`, `refund`, `general`, `outage`, `press`

**Priorities**: `low`, `medium`, `high`, `urgent`

**Escalation teams**: `engineering`, `billing`, `legal`, `pr`, `vip_support`, `senior_support`

## Observation Space

Each observation contains:

| Field              | Type          | Description                                    |
|--------------------|---------------|------------------------------------------------|
| `task_id`          | string        | Current task ID                                |
| `step`             | integer       | Current step number                            |
| `max_steps`        | integer       | Episode step limit                             |
| `inbox_summary`    | array         | Email summaries with status, category, priority|
| `current_email`    | object\|null  | Full email after `read_email`; null otherwise  |
| `available_tools`  | array         | Tool definitions callable via `use_tool`       |
| `last_tool_result` | object\|null  | Result from most recent tool call              |
| `email_statuses`   | object        | Map of email_id to current status              |
| `classified_as`    | object        | Map of email_id to assigned category           |
| `priorities`       | object        | Map of email_id to assigned priority           |
| `message`          | string        | Human-readable result of the last action       |
| `done`             | boolean       | Whether the episode has ended                  |
| `score`            | number        | Running cumulative score (0.0-1.0)             |

## Tasks

### Easy: Email Classification (max 15 steps)
Classify 5 support emails by category and priority. No tools required.
**Scoring**: Category accuracy (50%) + priority accuracy (30%) + all emails read (10%) + completion bonus (10%).

### Medium: Tool-Assisted Response Drafting (max 30 steps)
Handle 3 support emails requiring account/order lookups before crafting responses.
**Tools**: `lookup_order`, `get_customer_info`, `check_refund_eligibility`, `lookup_known_issues`.
**Scoring**: Per-email category + priority + tool usage + response quality. Efficiency bonus for completing in 18 steps or fewer.

### Hard: Incident Management Workflow (max 60 steps)
Manage 10 emails during a live platform outage. Includes VIP customers, press inquiries (CRITICAL: no technical details), duplicate detection, angry customers, and unrelated tickets.
**Tools**: All 6 tools available.
**Scoring**: Priority accuracy (20%) + duplicate detection (10%) + VIP handling (15%) + escalation correctness (15%) + non-outage separation (10%) + response quality (15%) + policy compliance (15%) + completion (10%) + efficiency (5%). Press policy violation incurs -0.30 penalty.

## Setup

### Docker (recommended)
```bash
docker build -t email-triage-env .
docker run -p 7860:7860 email-triage-env
```

### Local
```bash
pip install -r requirements.txt
uvicorn app:app --host 0.0.0.0 --port 7860
```

### Verify
```bash
curl http://localhost:7860/health
curl -X POST http://localhost:7860/reset -H "Content-Type: application/json" -d '{"task_id": "easy"}'
```

## Running Inference

Set environment variables and run:
```bash
export API_BASE_URL="https://router.huggingface.co/v1"
export MODEL_NAME="your-model-name"
export HF_TOKEN="your-hf-token"
export ENV_BASE_URL="http://localhost:7860"

python inference.py
```

## Baseline Scores

Heuristic baseline (no LLM):

| Task   | Score  | Passed |
|--------|--------|--------|
| easy   | 0.72   | Yes    |
| medium | 0.54   | No     |
| hard   | 0.89   | Yes    |

## API Endpoints

| Method | Path       | Description                              |
|--------|------------|------------------------------------------|
| GET    | `/`        | Root — confirms environment is running   |
| POST   | `/reset`   | Start/reset an episode                   |
| POST   | `/step`    | Take one action                          |
| GET    | `/state`   | Current observation (no step consumed)   |
| GET    | `/tasks`   | List tasks and Action JSON schema        |
| GET    | `/grader`  | Deterministic grader score               |
| POST   | `/baseline`| Run heuristic baseline on all 3 tasks    |
| GET    | `/health`  | Health check                             |
| GET    | `/docs`    | Interactive API documentation (Swagger)  |
