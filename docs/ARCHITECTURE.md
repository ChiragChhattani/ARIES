# ARIES Architecture

## System Overview

ARIES is a multi-agent AI system that automates candidate interviews. It uses Microsoft AutoGen for agent orchestration, FastAPI for the web API, and React for the frontend.

## Component Diagram

```mermaid
flowchart TD
    subgraph Frontend["React Frontend"]
        UI[Interview UI]
    end

    subgraph API["FastAPI Backend"]
        REST["REST API<br/>/api/v1/*"]
        WS["WebSocket<br/>/ws/interviews/{id}"]
        MW["Middleware<br/>CORS, Correlation ID"]
    end

    subgraph Core["Business Logic"]
        ORCH["Orchestrator<br/>Lifecycle management"]
        SM["State Machine<br/>CREATED → ... → REPORT_READY"]
        SVC["Services<br/>Interview, Evaluation"]
    end

    subgraph Agents["AI Agents (AutoGen)"]
        IA["Interviewer Agent<br/>Question generation"]
        CA["Candidate Simulator<br/>Testing only"]
        EA["Evaluation Agent<br/>Scoring & evidence"]
    end

    subgraph Data["Data Layer"]
        REPO["Repositories<br/>Data access"]
        DB["SQLite / PostgreSQL"]
    end

    subgraph Infra["Infrastructure"]
        LOG["Structured Logging"]
        CFG["Configuration<br/>Pydantic Settings"]
        OBS["Observability"]
    end

    UI -->|HTTP/WS| REST
    UI -->|WebSocket| WS
    REST --> MW --> ORCH
    WS --> ORCH
    ORCH --> SM
    ORCH --> IA
    ORCH --> CA
    ORCH --> EA
    ORCH --> SVC
    SVC --> REPO --> DB
    IA & EA -->|OpenAI API| LLM["GPT-4o"]
```

## Key Design Decisions

### 1. Explicit State Machine (not LLM-driven state)

The interview lifecycle is an explicit Python state machine with defined transitions. The LLM generates questions and evaluations, but it does NOT decide what state the interview is in. This makes the system predictable and debuggable.

### 2. Adapter Pattern for Agents

AutoGen agents are wrapped in thin adapter classes. If AutoGen's API changes, we update the adapter, not every call site. This also makes agents independently testable.

### 3. REST-First, WebSocket-Second

All state is persisted and retrievable via REST. WebSocket is a live notification overlay. If the WebSocket disconnects, no data is lost — the client can poll REST to catch up.

### 4. Deterministic Score Aggregation

The LLM evaluates each competency qualitatively and assigns per-competency scores. The final aggregate score is computed by a deterministic Python function (weighted average), not by the LLM. This makes scoring auditable and reproducible.

### 5. Separation of Request/Response/Internal Models

- **Request models**: What the API caller sends (no server-generated fields)
- **Internal models**: Full state representation (includes session_id, timestamps)
- **Response models**: What the API returns (may omit internal details)

## Data Flow: Creating an Interview

```mermaid
sequenceDiagram
    actor User
    participant API as FastAPI
    participant Orch as Orchestrator
    participant SM as State Machine
    participant DB as Database

    User->>API: POST /api/v1/interviews
    API->>API: Validate request (Pydantic)
    API->>Orch: create_session(request)
    Orch->>SM: transition(CREATED)
    Orch->>DB: persist session
    Orch-->>API: InterviewSession
    API-->>User: 201 Created + session_id
```

## Technology Stack

| Layer | Technology | Version |
|-------|-----------|---------|
| Language | Python | 3.13 |
| Web Framework | FastAPI | 0.115.x |
| Agent Framework | AutoGen (agentchat + ext) | 0.7.5 |
| LLM | OpenAI GPT-4o | Latest |
| Database | SQLAlchemy + aiosqlite | 2.0.x |
| Validation | Pydantic | 2.x |
| Frontend | React + Vite + Tailwind | Latest |
| Testing | pytest + pytest-asyncio | 8.x |

## Directory Responsibilities

| Directory | Responsibility |
|-----------|---------------|
| `app/core/` | Configuration, settings |
| `app/api/routes/` | HTTP endpoint handlers |
| `app/schemas/` | Pydantic models (data shapes) |
| `app/database/` | SQLAlchemy engine, models, migrations |
| `app/agents/` | AutoGen agent wrappers |
| `app/orchestration/` | Interview lifecycle, state machine |
| `app/services/` | Business logic |
| `app/repositories/` | Database access (CRUD) |
| `app/observability/` | Logging, tracing |
| `app/prompts/` | LLM prompt templates |
| `app/memory/` | Session memory, Mem0 integration |
| `tests/` | All test files |
