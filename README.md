# SupportCommander

Autonomous customer-support resolution system powered by a multi-agent AI pipeline. Tickets come in, the agents triage, plan, check policies, execute actions, and draft a customer response — most of the time without any human involvement.

Built with LangGraph, OpenAI, FastAPI, MongoDB, MCP tools, and a vanilla JS dashboard.

---

## Quick Start

### Prerequisites

- Docker & Docker Compose
- An OpenAI API key

### 1. Clone and configure

```bash
cp .env.example .env
```

Edit `.env` and set:

```
OPENAI_API_KEY=sk-...your-key...
OPENAI_MODEL=gpt-4o          # or gpt-4o-mini for lower cost
MONGO_ROOT_USERNAME=supportadmin
MONGO_ROOT_PASSWORD=pick-a-password
```

### 2. Build and start

```bash
docker compose up --build -d
```

This starts two containers:
- **mongo** — MongoDB 8 on port `27017`
- **app** — FastAPI on port `8000` (waits for Mongo health check)

### 3. Open the dashboard

```
http://localhost:8000/app/
```

You're ready. Upload a CSV dataset and PDF knowledge base through the UI — processing happens automatically.

### 4. (Optional) Seed the built-in demo dataset

If you want the pre-loaded 8,469 demo tickets with synthetic customer/order/payment data, run these one-time scripts **inside the container or with `PYTHONPATH=src`**:

```bash
PYTHONPATH=src python scripts/4_prepare_tickets.py
PYTHONPATH=src python scripts/8_generate_domain_data.py
PYTHONPATH=src python scripts/10_load_domain_data.py
PYTHONPATH=src python scripts/23_build_policy_index.py
```

This gives you ticket IDs 1–8469 to test with. **Skip this step** if you only plan to use your own CSV datasets and PDFs uploaded through the UI.

---

## How to Use

### Running a ticket from the built-in dataset

1. Open `http://localhost:8000/app/`
2. In the sidebar under **Run a Workflow**, type a ticket ID (e.g. `42`)
3. Click **Run**
4. Watch the pipeline stages appear in real time: Triage → Analysis → Suggestion → Policy Gate → (optional Human Review) → Actions → Response → Handoff

### Running a ticket from your own CSV dataset

1. Switch to the **Datasets** tab in the sidebar
2. Enter a user ID (e.g. `nishi`) and upload a CSV file with columns like `customer_identifier`, `ticket_text`, `ticket_date`
3. Once uploaded, switch back to **Workflows**
4. Enter the same user ID, click **Load** to see your datasets
5. Select a dataset from the dropdown — the ticket ID field now shows row IDs
6. Enter a row ID and click **Run**

### Uploading a Knowledge Base PDF

1. Switch to the **KB** tab
2. Click **Choose PDF files** and select up to 5 PDF documents
3. Click **Upload to Knowledge Base**
4. The PDFs are chunked, embedded, and indexed — the RAG pipeline uses them alongside the built-in policies when drafting responses

### Human-in-the-loop approval

When the policy gate flags an action (high-value refund, restricted account, sensitive data change), the workflow pauses and shows a structured approval card:

- **Approve** — proceed with the agent's recommendation
- **Modify** — change the proposed action (e.g. partial refund instead of full)
- **Reject** — decline the action; customer is notified

After your decision, the agent executes (or skips) the action and drafts the final customer response.

---

## Features

| Feature | Description |
|---|---|
| **Multi-agent pipeline** | 7 specialized agents orchestrated by LangGraph |
| **Autonomous resolution** | Most tickets resolve end-to-end without human intervention |
| **Deterministic policy gate** | Python rules enforce financial limits, eligibility windows, risk thresholds — no LLM decides authorization |
| **Human approval flow** | Structured approve / modify / reject with rich agent briefing |
| **Custom dataset support** | Upload any CSV of support tickets; agent derives customer name from email and resolves using KB |
| **Knowledge Base (PDF)** | Upload company policy PDFs; RAG retrieval grounds responses in your actual documentation |
| **RAG pipeline** | Intent-aware policy retrieval using OpenAI embeddings + cosine similarity |
| **MCP tool execution** | Refunds, replacements, cancellations executed through controlled FastMCP tools with idempotency and verification |
| **Risk scoring** | Deterministic risk assessment from account status, payment issues, order value, refund/replacement history |
| **Cost tracking** | Per-workflow LLM cost breakdown — input/output tokens, latency, cost per agent call |
| **Audit trail** | Every agent action, decision, and state change is timestamped and stored |
| **Real-time dashboard** | Vanilla HTML/CSS/JS UI — no build step, no framework, just open the browser |

---

## How Each Feature Works

### Autonomous Resolution

When a ticket enters the pipeline, it flows through all 7 agents. If the triage intent is non-transactional (e.g. product inquiry, tracking question, complaint), the resolution planner proposes `provide_information` and the policy gate allows it automatically. The response agent drafts a personalized reply using the customer's name (derived from the CSV email if needed) and KB content.

For transactional actions (refund, replacement, cancellation), the system checks:
- Is the amount within the auto-approval limit? ($200 refund / $300 replacement / $500 cancellation)
- Is the order within the eligibility window? (30 days)
- Is the account restricted? Is risk low?

If all checks pass → auto-execute. Otherwise → human approval.

### Dataset Ticket Handling

Uploaded CSV tickets have no customer/order records in the backend database. The system handles this gracefully:
- Customer name is derived from the email identifier (e.g. `aarav.sharma@example.com` → "Aarav Sharma")
- Risk assessment returns `low` (0.0) instead of penalizing for missing backend data
- The resolution planner prefers `provide_information` from the KB rather than escalating
- Non-transactional actions skip the customer ID requirement in the execution layer

### Policy Gate Rules

The gate evaluates each proposed action independently:

**Refunds:**
- Restricted account → escalate
- Payment not in `paid` / `partially_refunded` → reject
- Amount > recorded payment → reject
- Existing completed refund → reject
- Outside 30-day window → require approval
- Missing dates → escalate
- High risk → escalate; Medium risk → require approval
- Amount > $200 → require approval
- Otherwise → allow

**Replacements:** Similar structure with $300 limit and 30-day window.

**Cancellations:** Checks shipment status (can't cancel if shipped/delivered), $500 limit.

**Non-transactional** (`provide_information`, `troubleshoot`, `no_action`): Always allowed.

**Escalation actions**: Always escalated to human.

The overall decision is the most restrictive across all proposed actions.

### Human-in-the-Loop Triggers

The triage agent detects signals that may need human review:
- `security_concern` — unauthorized access, fraud, account compromise
- `personal_data_change` — requests to change email, password, payment method

Only these serious triggers mandate human approval. Common signals like customer frustration are noted but do not block autonomous resolution.

### Cost Tracking

Every LLM call records:
- Agent name, model used
- Input/output token counts
- Call latency
- Computed cost in USD

The dashboard shows per-workflow cost breakdowns. Cost logs are persisted to `cost_logs/` as JSON.

---

## Agent Architecture

```
                        ┌─────────────────────┐
                        │  LangGraph           │
                        │  Coordinator         │
                        └──────────┬───────────┘
                                   │
              ┌────────────────────┼────────────────────┐
              │                    │                     │
     ┌────────▼────────┐  ┌───────▼────────┐  ┌────────▼────────┐
     │  Triage Agent    │  │  Context Agent  │  │  Knowledge Agent │
     │  (LLM)           │  │  (MCP tools)    │  │  (RAG)           │
     └────────┬─────────┘  └───────┬─────────┘  └────────┬─────────┘
              │            ┌───────▼─────────┐           │
              │            │  Risk Agent      │           │
              │            │  (deterministic) │           │
              │            └───────┬──────────┘           │
              └────────────────────┼──────────────────────┘
                                   │
                       ┌───────────▼───────────┐
                       │  Resolution Planner    │
                       │  (LLM)                 │
                       └───────────┬────────────┘
                                   │
                       ┌───────────▼───────────┐
                       │  Deterministic         │
                       │  Policy Gate           │
                       │  (Python rules — no LLM)│
                       └───────────┬────────────┘
                                   │
                    ┌──────────────┼──────────────┐
                    │              │               │
              ┌─────▼─────┐ ┌─────▼──────┐ ┌─────▼──────┐
              │  Allow     │ │  Approval   │ │  Reject    │
              │  ↓ Execute │ │  ↓ Human    │ │  ↓ Respond │
              └─────┬──────┘ └─────┬───────┘ └─────┬──────┘
                    │              │                │
                    └──────────────┼────────────────┘
                                   │
                       ┌───────────▼───────────┐
                       │  Verification          │
                       │  (deterministic)        │
                       └───────────┬────────────┘
                                   │
                       ┌───────────▼───────────┐
                       │  Response Agent        │
                       │  (LLM)                 │
                       └────────────────────────┘
```

### Agent Details

#### 1. Triage Agent (LLM)
- **Input:** Raw ticket text, priority, channel
- **Output:** `TriageResult` — intent, urgency, confidence, summary, human triggers, downstream flags
- **Intents:** `refund_request`, `technical_issue`, `cancellation_request`, `product_inquiry`, `billing_inquiry`, `unknown`
- **Human triggers:** `frustration`, `security_concern`, `personal_data_change`, `high_value_transaction`
- **Guardrails:** Confidence below 0.60 → ticket is escalated immediately, never reaches downstream agents
- **Rules layer:** Deterministic `triage_rules.py` ensures transactional intents always flag `needs_customer_context` and `needs_policy_lookup`

#### 2. Context Agent (MCP tools)
- **Input:** Ticket `customer_id` and `order_id`
- **Output:** `CustomerContext` — customer profile, order, payment, shipment, refund history, replacement history, missing data flags
- **For dataset tickets:** Returns empty context (no backend lookup attempted) with empty `missing_data` — does not penalize the workflow
- **Tool calls:** `get_customer`, `get_order`, `get_payment`, `get_shipment`, `get_refund_history`, `get_replacement_history`

#### 3. Risk Agent (deterministic scoring)
- **Input:** Customer context from MCP tools
- **Output:** `RiskAssessment` — risk level (low/medium/high), score (0–1), signals, rationale
- **Scoring signals:** `critical_context_missing` (+0.35), `restricted_account` (+0.50), `customer_medium_risk` (+0.25), `customer_high_risk` (+0.50), `payment_issue` (+0.40), `high_value_order` (+0.15), `multiple_refund_history` (+0.20), `multiple_replacement_history` (+0.15)
- **Thresholds:** Score >= 0.70 → high, >= 0.35 → medium, else low
- **Dataset tickets:** Score is 0.0 (low) because missing backend data is expected, not a risk signal

#### 4. Knowledge Agent (RAG)
- **Input:** Triage intent, ticket text
- **Output:** `retrieved_policies` — ranked policy chunks relevant to the ticket
- **Pipeline:** Intent → category filter → OpenAI embedding → cosine similarity → top-k chunks
- **Sources:** Built-in Markdown policies (refund, cancellation, replacement, billing, risk, escalation) + uploaded PDF documents from the Knowledge Base

#### 5. Resolution Planner (LLM)
- **Input:** Ticket, triage, customer context, risk assessment, retrieved policies
- **Output:** `ResolutionPlan` — summary, proposed actions, policy basis, confidence, planner flags
- **Action types:** `refund`, `replacement`, `cancel_order`, `troubleshoot`, `provide_information`, `escalate`, `no_action`
- **Guardrails:** Validates that policy IDs exist, order IDs match, refund amounts don't exceed payment. Low confidence (<0.65) → flags `low_planner_confidence` and appends an `escalate` action
- **Dataset tickets:** Prefers `provide_information` from KB when no backend data exists; does not default to `escalate`

#### 6. Policy Gate (deterministic Python rules — no LLM)
- **Input:** Resolution plan, customer context, risk assessment
- **Output:** `PolicyGateResult` — decision (`allow`/`require_approval`/`reject`/`escalate`), per-action decisions, reasons
- **Checks:** Account restrictions, payment eligibility, refund/replacement windows, duplicate detection, amount limits, risk level, planner confidence, human triggers
- **Override rules:** Only `security_concern` and `personal_data_change` triggers mandate human review; `frustration` does not

#### 7. Response Agent (LLM)
- **Input:** Full workflow state — ticket, customer, triage, plan, gate decision, approval, tool results, verification
- **Output:** `FinalResponse` — customer-facing message, resolution status, action summary, follow-up flag, internal notes, agent handoff note
- **Personalization:** Addresses customer by first name, references specific product/order, states exact refund amounts, avoids placeholders
- **Agent handoff format:** Structured internal note — `Customer: [name] · [email] · [phone]` → `Issue:` → `Resolution:` → `Status:` → `Human action needed:`
- **KB awareness:** Cites company documents when knowledge source is `company_doc`; adds general-knowledge disclaimer when no specific policy matched

### How Agents Connect

1. **Triage** runs first and alone — its output gates everything downstream
2. **Context**, **Risk**, and **Knowledge** agents run in **parallel** (LangGraph fan-out) — they are independent spokes that never call each other
3. **Resolution Planner** runs after all three analysis agents complete (LangGraph fan-in)
4. **Policy Gate** evaluates the plan deterministically
5. Based on the gate decision:
   - `allow` → action execution → verification → response
   - `require_approval` / `escalate` → workflow pauses for human decision → resume → execution → verification → response
   - `reject` → response (no execution)
6. **Response Agent** always runs last and produces the customer-facing message and internal handoff

All agents communicate **only** through shared `SupportGraphState`. No agent calls another agent directly. The LangGraph Coordinator controls all routing.

---

## API Reference

| Method | Endpoint | Description |
|---|---|---|
| `GET` | `/` | Service info |
| `GET` | `/health` | Health check |
| `GET` | `/health/db` | Database health |
| `GET` | `/api/v1/tickets` | List tickets (paginated, filterable) |
| `GET` | `/api/v1/tickets/{id}` | Get ticket by ID |
| `GET` | `/api/v1/tickets/{id}/context` | Get ticket + customer/order/payment context |
| `POST` | `/api/v1/workflows/tickets/{id}` | Run workflow on a built-in ticket |
| `POST` | `/api/v1/workflows/datasets/{dataset_id}/tickets/{row_id}` | Run workflow on a dataset ticket |
| `GET` | `/api/v1/workflows/{id}` | Get workflow state |
| `GET` | `/api/v1/workflows/tickets/{id}/history` | List workflows for a ticket |
| `POST` | `/api/v1/approvals/{id}` | Record approval decision |
| `POST` | `/api/v1/approvals/{id}/resume` | Resume workflow after approval |
| `GET` | `/api/v1/audit/workflows/{id}` | Get audit event trail |
| `POST` | `/api/v1/datasets` | Upload a CSV dataset |
| `GET` | `/api/v1/datasets` | List datasets for a user |
| `POST` | `/api/v1/knowledge-base/upload` | Upload PDF documents |
| `GET` | `/api/v1/knowledge-base/documents` | List uploaded KB documents |
| `GET` | `/api/v1/cost-logs/by-workflow/{id}` | Get LLM cost breakdown |

Interactive API docs: `http://localhost:8000/docs`

---

## Technology Stack

| Layer | Technology |
|---|---|
| Orchestration | LangGraph (StateGraph with parallel fan-out/fan-in) |
| LLM | OpenAI API (Responses API, embeddings) |
| Backend | FastAPI + Uvicorn (2 workers) |
| Database | MongoDB 8 (PyMongo) |
| Tool execution | FastMCP (STDIO transport) |
| Containerization | Docker + Docker Compose |
| Frontend | Vanilla HTML / CSS / JavaScript (no build step) |
| Data processing | Pandas |

---

## Project Structure

```
support-commander/
  compose.yaml            # Docker Compose — Mongo + App
  Dockerfile              # Python 3.11 slim image
  .env.example            # Environment template
  frontend/
    index.html            # Dashboard shell
    app.js                # All UI logic
    styles.css            # All styling
  src/supportcommander/
    api/
      main.py             # FastAPI app, lifespan, router registration
      routes/             # Endpoints: tickets, workflows, approvals, datasets, KB, etc.
    agents/
      triage_agent.py     # Intent classification + human trigger detection
      context_agent.py    # MCP-based customer/order data retrieval
      risk_agent.py       # Deterministic risk scoring
      resolution_planner.py  # LLM-based action proposal
      response_agent.py   # Final customer response + agent handoff
      dataset_analyst.py  # CSV ingestion analysis
      *_rules.py          # Deterministic validation/rules for each agent
    graph/
      coordinator.py      # LangGraph StateGraph definition + wiring
      nodes.py            # LangGraph node functions (triage, parallel, plan, gate, approval, execute, verify, respond)
      routing.py          # Conditional edge functions
      models.py           # Pydantic models (TriageResult, ResolutionPlan, PolicyGateResult, etc.)
      state.py            # SupportGraphState TypedDict
      state_factory.py    # Initial state builder
      state_loader.py     # MongoDB ↔ state hydration
      escalation.py       # Escalation handling
      audit.py            # Audit event appender
    policy/
      policy_gate.py      # Deterministic policy evaluation
      gate_rules.py       # Per-action-type rule evaluators
      constants.py        # Financial thresholds and limits
    services/
      workflow_service.py    # Workflow state persistence (save/load)
      approval_service.py    # Approval decision recording
      resume_service.py      # Post-approval workflow continuation
      action_execution_service.py  # MCP tool execution with verification
      llm_service.py         # Shared OpenAI client
      dataset_service.py     # CSV upload + ingestion
      verification_service.py  # Post-execution state verification
      cost_tracker.py        # Per-call LLM cost accumulator
      cost_logger.py         # Cost log persistence
    mcp_client/
      client.py           # FastMCP client lifecycle
      support_client.py   # Typed wrappers for MCP tool calls
    mcp_server/
      server.py           # FastMCP server with read + write tools
    pipeline/
      ingestor.py         # CSV → MongoDB ingestion pipeline
  data/
    policies/             # Markdown policy documents (refund, cancellation, etc.)
  scripts/                # Setup, seeding, and validation scripts
  tests/                  # Evaluation tests
  cost_logs/              # Per-workflow LLM cost JSON files
```

---

## Roadmap — Production Hardening

### Performance & Scale

- [ ] **Async task queue** (Celery + Redis or arq) — move workflow execution off the API thread so hundreds of tickets can process in parallel
- [ ] **SSE / WebSocket push** — live stage-by-stage updates to the dashboard instead of polling
- [ ] **Batch ticket processing** — "Run All" button to process an entire dataset in one click with a progress dashboard
- [ ] **Fast-path for simple queries** — if triage says `product_inquiry` with high confidence and no transactional flags, skip risk/planning/gate and go straight to response agent (cut latency from ~15s to ~3s)

### Intelligence & Quality

- [ ] **Better RAG grounding** — chunk uploaded PDFs more intelligently, rank by relevance, and always inject the top KB snippets into the response agent's context
- [ ] **Company profile per dataset** — configurable support email, phone number, SLA promises, brand voice, escalation paths (so the agent sounds like it belongs to Delhivery, not a generic bot)
- [ ] **Response templates / tone control** — greeting style, sign-off, standardized SLA language
- [ ] **Multi-turn conversation** — customer can reply to the agent's response; the system continues the thread instead of treating every message as a one-shot
- [ ] **Feedback loop** — when a human modifies or rejects an agent's recommendation, store the correction as a learning signal for future prompt tuning

### Reliability

- [ ] **Test suite** — unit tests for policy gate rules, risk scoring, triage rules; integration tests for the full pipeline with mocked LLM responses
- [ ] **LLM retry with backoff** — if the LLM returns malformed JSON, retry once instead of failing the entire workflow permanently
- [ ] **Structured logging** (JSON) + log aggregation — replace `print()` with proper leveled logging
- [ ] **Alerting** — detect when workflows fail silently at scale, or when the auto-resolution rate drops below a threshold

### Operations

- [ ] **CI/CD pipeline** — automated build, test, deploy on push
- [ ] **Volume-mount source in dev** — eliminate the `docker cp` workflow; source changes take effect on container restart
- [ ] **Metrics dashboard** — auto-resolution rate, average handling time, human override rate, cost per ticket, resolution distribution by intent
- [ ] **Bulk export** — download resolved tickets as CSV with customer, issue, resolution, status columns
- [ ] **API authentication** — enforce the `APP_API_KEY` for production deployments

---

## License

Portfolio project. Not licensed for production use.
