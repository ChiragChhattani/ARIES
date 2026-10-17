"""
FastAPI application entry point.

This is the top-level file that creates and configures the FastAPI app.
It wires together all the components: routes, CORS, logging, database.

KEY CONCEPT: LIFESPAN
---------------------
FastAPI's `lifespan` context manager replaces the old @app.on_event("startup")
and @app.on_event("shutdown") patterns. The code before `yield` runs on
startup; the code after `yield` runs on shutdown. This is more Pythonic
and ensures cleanup always happens (like a try/finally).

KEY CONCEPT: CORS
-----------------
Cross-Origin Resource Sharing (CORS) controls which domains can call your API.
Without CORS configuration, a React app at localhost:5173 cannot call a FastAPI
server at localhost:8000 — the browser blocks the request for security.

We configure allowed origins from environment variables, so production
can restrict to only the real frontend domain.
"""

import uuid
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request, Response
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.database.engine import init_database, close_database
from app.observability.logging import (
    setup_logging,
    get_logger,
    correlation_id_var,
)
from app.api.routes.health import router as health_router

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Application lifespan manager.

    Startup: Initialize logging, database, verify configuration.
    Shutdown: Close database connections, clean up resources.
    """
    settings = get_settings()

    # --- STARTUP ---
    setup_logging(
        log_level=settings.log_level,
        json_output=not settings.is_development,  # Human-readable in dev
    )

    logger.info(
        "Starting ARIES",
        extra={
            "version": settings.app_version,
            "environment": settings.env,
            "llm_provider": settings.llm_provider,
            "model": settings.groq_model if settings.llm_provider == "groq" else settings.openai_model,
        },
    )

    # Check that the required LLM API key is configured (never log the actual key!)
    if settings.llm_provider == "groq":
        if not settings.groq_api_key:
            logger.warning(
                "GROQ_API_KEY is not set while ARIES_LLM_PROVIDER=groq. "
                "LLM features will not work. Set GROQ_API_KEY in environment."
            )
    else:
        if not settings.openai_api_key:
            logger.warning(
                "OPENAI_API_KEY is not set. LLM features will not work. "
                "Set OPENAI_API_KEY in environment."
            )

    # Initialize database
    await init_database()

    logger.info("ARIES startup complete")

    yield  # Application runs here

    # --- SHUTDOWN ---
    logger.info("Shutting down ARIES")
    await close_database()
    logger.info("ARIES shutdown complete")


def create_app() -> FastAPI:
    """
    Application factory function.

    WHY A FACTORY?
    - Tests can create fresh app instances with different configs
    - Multiple configurations (dev/test/prod) are easy to manage
    - Avoids import-time side effects
    """
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        description="Automated Candidate Interview & Evaluation System",
        version=settings.app_version,
        lifespan=lifespan,
        # Don't show docs in production
        docs_url="/docs" if settings.is_development else None,
        redoc_url="/redoc" if settings.is_development else None,
    )

    # --- CORS Middleware ---
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # --- Correlation ID Middleware ---
    @app.middleware("http")
    async def add_correlation_id(request: Request, call_next) -> Response:
        """
        Assigns a unique correlation ID to every request.

        If the client sends X-Correlation-ID, we use it (for tracing
        across services). Otherwise, we generate a new UUID.

        The correlation ID is stored in a ContextVar, which means
        every async function in the request chain can access it
        without passing it as a parameter.
        """
        corr_id = request.headers.get("X-Correlation-ID", str(uuid.uuid4()))
        correlation_id_var.set(corr_id)

        response = await call_next(request)
        response.headers["X-Correlation-ID"] = corr_id

        return response

    # --- Global Exception Handlers ---
    from fastapi.responses import JSONResponse
    from app.orchestration.state_machine import StateMachineError
    from app.orchestration.orchestrator import OrchestratorError

    @app.exception_handler(StateMachineError)
    async def state_machine_exception_handler(request, exc: StateMachineError):
        logger.warning(f"State machine violation: {exc}")
        return JSONResponse(status_code=400, content={"error": "Invalid State", "detail": str(exc)})

    @app.exception_handler(OrchestratorError)
    async def orchestrator_exception_handler(request, exc: OrchestratorError):
        logger.warning(f"Orchestration error: {exc}")
        return JSONResponse(status_code=404, content={"error": "Not Found", "detail": str(exc)})

    # --- Register Routes ---
    app.include_router(health_router)
    
    from app.api.routes.interviews import router as interviews_router
    app.include_router(interviews_router)

    return app


# The app instance used by uvicorn: `uvicorn app.main:app`
app = create_app()
