# ARIES — Automated Candidate Interview & Evaluation System

A multi-agent AI application that automates the initial stages of candidate interviews for recruitment.

> **⚠️ Important**: ARIES generates decision-support reports for human reviewers. It does NOT make hiring decisions automatically.

## Quick Start

### Prerequisites
- Python 3.11+ (tested with 3.13)
- Node.js 18+ (for frontend, Phase 4)
- A Groq API key (or OpenAI API key)

### Setup

```bash
# Clone the repository
cd aries

# Create and activate virtual environment
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate  # macOS/Linux

# Install dependencies
pip install -r backend/requirements.txt

# Configure environment
cp backend/.env.example backend/.env
# Edit backend/.env and add your GROQ_API_KEY

# Run the server
cd backend
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

### Verify

```bash
# Health check
curl http://localhost:8000/health

# API docs (development only)
# Open http://localhost:8000/docs in your browser
```

### Run Tests

```bash
cd backend
python -m pytest tests/ -v
```

## Project Structure

```
aries/
├── backend/
│   ├── app/
│   │   ├── main.py              # FastAPI application entry point
│   │   ├── core/config.py       # Environment-based configuration
│   │   ├── api/routes/           # HTTP endpoints
│   │   ├── schemas/              # Pydantic data models
│   │   ├── database/             # SQLAlchemy engine & models
│   │   ├── agents/               # AutoGen AI agents (Phase 2)
│   │   ├── orchestration/        # Interview lifecycle management (Phase 3)
│   │   ├── observability/        # Structured logging
│   │   └── ...
│   ├── tests/                    # pytest test suite
│   ├── requirements.txt          # Pinned Python dependencies
│   └── .env.example              # Environment variable template
├── frontend/                     # React application (Phase 4)
├── docs/                         # Architecture and design documents
└── README.md
```

## Environment Variables

| Variable | Required | Default | Description |
|----------|----------|---------|-------------|
| `ARIES_LLM_PROVIDER` | No | `groq` | Choose `openai` or `groq` |
| `GROQ_API_KEY` | Yes* | — | Groq API key (*if provider is groq) |
| `ARIES_GROQ_MODEL` | No | `llama-3.3-70b-versatile` | Groq model to use |
| `OPENAI_API_KEY` | Yes* | — | OpenAI API key (*if provider is openai) |
| `ARIES_OPENAI_MODEL` | No | `gpt-4o` | OpenAI model to use |
| `ARIES_ENV` | No | `development` | Environment mode |
| `ARIES_LOG_LEVEL` | No | `INFO` | Logging verbosity |
| `ARIES_DATABASE_URL` | No | `sqlite+aiosqlite:///./aries.db` | Database connection |
| `ARIES_CORS_ORIGINS` | No | `http://localhost:5173` | Allowed frontend origins |

## Architecture

See [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) for the full system design.

## Implementation Phases

- **Phase 1** ✅ Foundations & Configuration
- **Phase 2** 🔲 Agent Implementation
- **Phase 3** 🔲 Integration & Testing
- **Phase 4** 🔲 Interface & Deployment
- **Phase 5** 🔲 Utility Module

## License

Private — not for redistribution.
