# ARIES Learning Guide

This guide documents the core engineering concepts, architecture decisions, and debugging techniques learned during the development of ARIES.

## Phase 1: Foundations & Configuration

### Concepts Learned

1. **Explicit State Machines vs. LLM State**
   - *Concept*: LLMs are non-deterministic and can easily lose track of where they are in a long process.
   - *Implementation*: We use an explicit Python Enum (`InterviewStatus` and `InterviewStage`) to track the interview lifecycle. The backend is the authoritative source of truth for the session state, not the LLM's conversation history.

2. **Pydantic Validation at Boundaries**
   - *Concept*: Fail fast and loud when invalid data enters the system.
   - *Implementation*: Our schemas (`app/schemas/`) enforce constraints (e.g., `max_length`, `ge` for numeric bounds, uniqueness for rubric scales) before any data reaches the database or the LLM.

3. **Structured Logging and Correlation IDs**
   - *Concept*: Logs must be searchable across distributed async components.
   - *Implementation*: We output JSON logs containing a `correlation_id` (via `ContextVar`). If a single API request triggers 3 agent actions and 5 database writes, all logs for that request share the same `correlation_id`, making debugging trivial.

4. **FastAPI Lifespan and Async SQLAlchemy**
   - *Concept*: Modern async Python apps need reliable resource initialization and cleanup.
   - *Implementation*: We use FastAPI's `@asynccontextmanager` `lifespan` to connect to the database (async SQLite) on startup and cleanly dispose of the engine on shutdown.

5. **Configuration via Environment Variables**
   - *Concept*: 12-Factor App methodology dictates that configuration (especially secrets) lives in the environment.
   - *Implementation*: Pydantic `BaseSettings` automatically maps `ARIES_LOG_LEVEL` to the `log_level` field, handling type casting and validation at startup.

### Important Files

- `app/core/config.py`: The `Settings` class that parses and validates environment variables.
- `app/main.py`: The FastAPI application factory, CORS setup, and lifespan manager.
- `app/schemas/interview.py`: Defines the strict separation between what the API receives (`InterviewCreateRequest`), what it returns (`InterviewResponse`), and the internal state (`InterviewSession`).
- `app/observability/logging.py`: The JSON log formatter and `ContextVar` logic for tracing.

### Common Errors and Debugging

- **Pydantic `ValidationError`**: If the server crashes with a `ValidationError` on startup, it means an environment variable is missing or formatted incorrectly. Check `.env`.
- **"Database not initialized"**: If you see a `RuntimeError` when trying to use the database in tests, ensure the test uses the `test_client` fixture which triggers the FastAPI lifespan event.
- **Port already in use**: When running `uvicorn`, if port 8000 is taken, kill the existing process or use `--port 8001`.

### Self-Check Questions

1. Why do we define the interview state as a Python Enum rather than asking the LLM "What stage are we in?"
2. What is a `ContextVar`, and why is it necessary for the `correlation_id` in an async FastAPI application?
3. Why do we separate `InterviewCreateRequest` and `InterviewSession` into two different Pydantic models?

## Phase 2: Agent Implementation

### Concepts Learned

1. **The Adapter Pattern for AI Agents**
   - *Concept*: Instead of giving an AI Agent free reign to do whatever it wants in an open-ended loop, we wrap it in a strict Python class (the Adapter).
   - *Implementation*: `InterviewerAgentAdapter` manages the AutoGen `AssistantAgent`. It takes strict domain models (`JobDescription`, `TranscriptEntry` list) as inputs, builds the prompt safely, calls the LLM, and forces the output into a Pydantic model (`NextQuestion`). 

2. **Structured Outputs (Bridging AI and Code)**
   - *Concept*: Orchestration logic in Python requires predictable data shapes (JSON), not conversational text. 
   - *Implementation*: By passing our Pydantic schema (like `NextQuestion`) to the `response_format` parameter of the `OpenAIChatCompletionClient`, we leverage OpenAI's native structured outputs. We added a fallback `parse_json_safely` helper to strip out markdown blocks (` ```json `) just in case the LLM tries to be helpful.

3. **Dynamic Prompt Injections**
   - *Concept*: Prompts should be templates populated securely by the application state.
   - *Implementation*: `app/prompts/interviewer.py` contains functions like `get_interviewer_task_prompt(transcript, questions_remaining)`. This ensures no prompt injection from candidate answers can accidentally override the base system instructions.

4. **Testing AI Agents (Mocking LLM Calls)**
   - *Concept*: You shouldn't pay OpenAI every time you run `pytest`. Tests need to be fast, deterministic, and free.
   - *Implementation*: We used `unittest.mock.patch` to intercept the `agent.run()` command in `test_agents.py`. We fed our adapters a fake JSON string to ensure they could parse it into Pydantic models correctly.

### Important Files
- `app/agents/base.py`: Contains the `create_model_client` factory to standardize model setup across all agents.
- `app/schemas/agent_outputs.py`: The Pydantic definitions of what the LLMs must output.
- `app/prompts/`: Separates prompt engineering from business logic.
- `app/agents/interviewer.py` & `app/agents/evaluator.py`: The actual Adapters wrapping AutoGen.

### Common Errors and Debugging
- **"Agent output could not be parsed"**: Sometimes LLMs wrap JSON in markdown. Our `parse_json_safely` function strips this automatically.
- **Fixture Validation Error**: If your test mock data is too short, Pydantic will crash the test (which happened in development!). This proves the boundary validation from Phase 1 is working perfectly.

### Self-Check Questions
1. Why do we define agent outputs as Pydantic models (like `NextQuestion`) instead of just asking the LLM for a string?
2. What is the benefit of wrapping AutoGen's `AssistantAgent` in an Adapter class instead of calling it directly from an API endpoint?
3. Why do we mock the `agent.run()` call in `pytest`?

## Phase 3: Integration & Orchestration

### Concepts Learned

1. **The Repository Pattern**
   - *Concept*: Business logic should not be mixed with database queries.
   - *Implementation*: `InterviewRepository` handles all the logic of converting our rich Pydantic domain models (`InterviewSession`) into SQLAlchemy models (`InterviewRecord`). The `InterviewOrchestrator` never sees SQL, it just calls `await repo.save(session)`.

2. **The State Machine (Rules Engine)**
   - *Concept*: Complex workflows need strict enforcement of transitions to prevent invalid states (e.g., trying to submit a candidate answer after the interview is already complete).
   - *Implementation*: `InterviewStateMachine` defines exactly which transitions are allowed (`VALID_TRANSITIONS` dictionary) and throws a `StateMachineError` if an invalid path is taken.

3. **Hybrid SQL/JSON Database Design**
   - *Concept*: Creating 7+ relational tables for heavily nested data (like rubrics and transcripts) is overkill for an MVP and hurts read performance.
   - *Implementation*: We used standard indexed SQL columns for things we need to query (`session_id`, `status`), but we stored the deeply nested Pydantic objects (like the list of `TranscriptEntry`) as JSON columns using SQLAlchemy's `JSON` type.

4. **Integration Testing with Mocked Boundaries**
   - *Concept*: You need to test that the Orchestrator glues everything together, but you don't want to hit the real OpenAI API or a real production database.
   - *Implementation*: In `test_orchestrator.py`, we used an in-memory SQLite database (`sqlite+aiosqlite:///:memory:`) so DB tests run instantly. We also mocked the `InterviewerAgentAdapter` so we could verify the loop logic (answering questions until `max_questions` is reached) ran exactly as expected.

### Important Files
- `app/database/models.py`: SQLAlchemy setup with JSON columns.
- `app/repositories/interview.py`: The bridge between Pydantic and SQLAlchemy.
- `app/orchestration/state_machine.py`: The rules engine governing the interview lifecycle.
- `app/orchestration/orchestrator.py`: The central service layer that processes all actions.

### Common Errors and Debugging
- **"Invalid state transition"**: If the Orchestrator throws this, you are trying to do something out of order. For example, you cannot call `handle_candidate_answer` if the status is `CREATED`. You must call `start_interview` first.
- **Fixture Validation Error (Again)**: We encountered another validation error when trying to set `max_questions=2` in our test fixture. Because we defined `ge=3` in Phase 1, Pydantic blocked it, proving that our constraints remain active across the entire system.

### Self-Check Questions
1. If we decide to switch from SQLite to PostgreSQL in the future, which file(s) would we need to change in Phase 3?
2. Why is the `transcript` stored as a JSON column in `InterviewRecord` instead of creating a separate `transcript_entries` table with a Foreign Key?
3. What is the purpose of the `InterviewOrchestrator`? Why didn't we just put that logic inside the API route handlers (e.g., inside `POST /interviews`)?

## Phase 4: Interface & Deployment

### Concepts Learned

1. **REST + WebSocket Architecture**
   - *Concept*: Combining the stateless reliability of REST for CRUD operations with the low-latency real-time capabilities of WebSockets for live chat.
   - *Implementation*: `app/api/routes/interviews.py` contains standard `POST /interviews` routes for creating sessions. However, the actual interview happens over `ws://.../ws/{session_id}`. When the candidate submits an answer over the socket, the Orchestrator processes it, and the backend broadcasts a `question_generated` JSON payload back down the pipe.

2. **Manual DB Commits in WebSockets**
   - *Concept*: FastAPI's dependency injection (`Depends(get_db_session)`) normally handles database commits automatically when an HTTP request finishes successfully. WebSockets don't "finish" until the user closes the tab.
   - *Implementation*: In the WebSocket loop, we explicitly call `await db.commit()` after processing a candidate's answer so the database updates immediately while the connection remains open.

3. **Optimistic UI Updates in React**
   - *Concept*: A user shouldn't have to wait 5 seconds for the LLM to process before seeing their own message appear in the chat.
   - *Implementation*: In `LiveInterview.jsx`, when the user clicks "Send", we immediately append their answer to the `transcript` state (optimistic update), set `isProcessing=true`, and then wait for the WebSocket to push the AI's response.

4. **Ephemeral Cloud Storage vs Persistent Disks**
   - *Concept*: Platforms like Render and Heroku wipe their server hard drives every time they deploy or restart. 
   - *Implementation*: Because we are using SQLite (a file-based database) instead of a managed Postgres instance, we configured `render.yaml` to mount a persistent disk (`/data`). We then pointed our `ARIES_DATABASE_URL` to `sqlite+aiosqlite:////data/aries.db` so our interviews survive restarts.

### Important Files
- `app/api/websocket.py`: The connection manager tracking active users and broadcasting events.
- `app/api/routes/interviews.py`: The API controllers mapping HTTP/WS requests to the Orchestrator.
- `frontend/src/services/socket.js`: The frontend WebSocket client.
- `render.yaml`: Infrastructure as Code defining how to build and host the app on Render.

### Common Errors and Debugging
- **"WebSocket connection closed unexpectedly"**: This usually happens if the backend crashes while processing a message (e.g., the LLM API key is invalid). Check the backend server logs.
- **Data disappearing after a cloud deployment**: You forgot to configure a persistent disk for SQLite, so the database file was deleted when the container restarted.

### Self-Check Questions
1. Why do we have to manually call `await db.commit()` inside the WebSocket loop, but not inside the `POST /interviews` route?
2. If we lose our internet connection for 3 seconds during the interview and the WebSocket disconnects, do we lose the interview data? Why or why not?
3. Why did we need to add a "rewrite rule" in the `render.yaml` configuration for the frontend static site? (Hint: React Router)
