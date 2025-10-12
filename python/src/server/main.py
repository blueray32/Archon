"""
FastAPI Backend for Archon Knowledge Engine

This is the main entry point for the Archon backend API.
It uses a modular approach with separate API modules for different functionality.

Modules:
- settings_api: Settings and credentials management
- mcp_api: MCP server management and tool execution
- knowledge_api: Knowledge base, crawling, and RAG operations
- projects_api: Project and task management with streaming
"""

import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from .api_routes.agent_chat_api import router as agent_chat_router
from .api_routes.chatkit_api import router as chatkit_router
from .api_routes.bug_report_api import router as bug_report_router
from .api_routes.internal_api import router as internal_router
from .api_routes.knowledge_api import router as knowledge_router
from .api_routes.mcp_api import router as mcp_router
from .api_routes.embeddings_api import router as embeddings_router
from .api_routes.obsidian_api import router as obsidian_router
from .api_routes.progress_api import router as progress_router
from .api_routes.projects_api import router as projects_router
from .api_routes.tagging_api import router as tagging_router

# Import modular API routers
from .api_routes.settings_api import router as settings_router

# Import Logfire configuration
from .config.logfire_config import api_logger, setup_logfire
from .services.background_task_manager import cleanup_task_manager
from .services.crawler_manager import cleanup_crawler, initialize_crawler

# Import utilities and core classes
from .services.credential_service import initialize_credentials
from .services.embeddings.embeddings_maintenance_service import run_embeddings_health_monitor

# Import missing dependencies that the modular APIs need
try:
    from crawl4ai import AsyncWebCrawler, BrowserConfig
except ImportError:
    # These are optional dependencies for full functionality
    AsyncWebCrawler = None
    BrowserConfig = None

# Load environment variables from project root .env (for local runs)
try:
    from dotenv import load_dotenv  # type: ignore
    from pathlib import Path

    # Project root is three levels up from this file: python/src/server/main.py -> repo root
    _repo_root = Path(__file__).resolve().parents[3]
    _env_file = _repo_root / ".env"
    if _env_file.exists():
        load_dotenv(dotenv_path=_env_file, override=False)
except Exception:
    # Dotenv is optional; ignore if unavailable
    pass

# Logger will be initialized after credentials are loaded
logger = logging.getLogger(__name__)

# Set up logging configuration to reduce noise

# Override uvicorn's access log format to be less verbose
uvicorn_logger = logging.getLogger("uvicorn.access")
uvicorn_logger.setLevel(logging.WARNING)  # Only log warnings and errors, not every request

# CrawlingContext has been replaced by CrawlerManager in services/crawler_manager.py

# Global flag to track if initialization is complete
_initialization_complete = False

_CSP_DIRECTIVES: dict[str, list[str]] = {
    "default-src": [
        "'self'",
        "https://api.supabase.com",
        "http://localhost:8000",
        "https://auth.supabase.io",
        "ws://localhost:8000",
        "wss://localhost:8000",
        "https://*.supabase.co",
        "wss://*.supabase.co",
        "https://*.hcaptcha.com",
        "https://cdn-global.configcat.com",
        "https://configcat.supabase.com",
        "https://*.stripe.com",
        "https://*.stripe.network",
        "https://www.cloudflare.com",
        "https://cdnjs.cloudflare.com",
        "https://*.vercel-insights.com",
        "https://api.github.com",
        "https://raw.githubusercontent.com",
        "https://frontend-assets.supabase.com",
        "https://*.usercentrics.eu",
        "https://ss.supabase.com",
        "https://maps.googleapis.com",
        "https://ph.supabase.com",
        "wss://*.pusher.com",
        "https://*.ingest.sentry.io",
        "https://*.ingest.us.sentry.io",
        "https://*.ingest.de.sentry.io",
    ],
    "connect-src": [
        "'self'",
        "data:",
        "blob:",
        "https://api.supabase.com",
        "http://localhost:8000",
        "https://auth.supabase.io",
        "ws://localhost:8000",
        "wss://localhost:8000",
        "https://*.supabase.co",
        "wss://*.supabase.co",
        "https://cdn-global.configcat.com",
        "https://configcat.supabase.com",
        "https://*.stripe.com",
        "https://*.stripe.network",
        "https://*.vercel-insights.com",
        "https://api.github.com",
        "https://raw.githubusercontent.com",
        "https://frontend-assets.supabase.com",
        "https://*.usercentrics.eu",
        "https://ss.supabase.com",
        "https://maps.googleapis.com",
        "https://ph.supabase.com",
        "wss://*.pusher.com",
        "https://*.ingest.sentry.io",
        "https://*.ingest.us.sentry.io",
        "https://*.ingest.de.sentry.io",
        "https://cdnjs.cloudflare.com",
    ],
    "script-src": [
        "'self'",
        "'unsafe-inline'",
        "'unsafe-eval'",
        "https://cdn.jsdelivr.net",
        "https://cdnjs.cloudflare.com",
    ],
    "style-src": [
        "'self'",
        "'unsafe-inline'",
        "https://fonts.googleapis.com",
        "https://cdnjs.cloudflare.com",
    ],
    "img-src": [
        "'self'",
        "data:",
        "blob:",
        "https://*.supabase.co",
        "https://*.stripe.com",
        "https://www.gstatic.com",
        "https://maps.googleapis.com",
    ],
    "font-src": [
        "'self'",
        "data:",
        "https://fonts.gstatic.com",
    ],
    "frame-src": [
        "'self'",
        "https://*.stripe.com",
    ],
    "worker-src": [
        "'self'",
        "blob:",
    ],
    "object-src": [
        "'none'",
    ],
}


def _build_csp_policy() -> str:
    directives = []
    for directive, sources in _CSP_DIRECTIVES.items():
        unique_sources: list[str] = []
        for source in sources:
            if source not in unique_sources:
                unique_sources.append(source)
        directives.append(f"{directive} {' '.join(unique_sources)}")
    return "; ".join(directives)


_CSP_POLICY = _build_csp_policy()


async def _validate_prp_startup():
    """Fail-fast validation for PRP system when enabled.

    - Requires OPENAI_API_KEY
    - Requires PRP tables available (prp_docs, prp_messages, prp_personas)
    - Validates vector/RPC availability for PRP similarity search
    """
    enabled = os.getenv("PRP_ENABLED", "true").lower() in ("true", "1", "yes", "on")
    if not enabled:
        return

    # Check OPENAI_API_KEY
    if not os.getenv("OPENAI_API_KEY"):
        raise RuntimeError(
            "PRP system is enabled but OPENAI_API_KEY is missing. Set it in .env or disable PRP_ENABLED."
        )

    # Verify tables exist via Supabase service client
    try:
        from .services.client_manager import get_supabase_client

        client = get_supabase_client()
        # Probe tables
        client.table("prp_docs").select("id").limit(1).execute()
        client.table("prp_messages").select("id").limit(1).execute()
        client.table("prp_personas").select("id").limit(1).execute()
    except Exception as e:  # noqa: BLE001
        raise RuntimeError(
            f"PRP system not ready (tables). Apply migration/prp_system.sql. Details: {e}"
        ) from e

    # Validate search RPCs and pgvector
    strict = os.getenv("PRP_STRICT", "false").lower() in ("true", "1", "yes", "on")
    try:
        probe = [0.0] * 1536
        client.rpc(
            "search_prp_docs",
            {"query_embedding": probe, "kind_filter": "prp", "match_count": 1, "similarity_threshold": 0.9},
        ).execute()
        client.rpc(
            "search_prp_messages",
            {"query_embedding": probe, "session_filter": None, "match_count": 1, "similarity_threshold": 0.9},
        ).execute()
    except Exception as e:  # noqa: BLE001
        msg = str(e)
        if strict:
            raise RuntimeError(
                "PRP search functions not available or vector extension missing. "
                "Run migration/prp_system.sql. Details: " + msg
            ) from e
        else:
            api_logger.error(
                "PRP search functions not available or vector extension missing. "
                "Server will continue (PRP_STRICT is false). Details: %s",
                msg,
            )


def _validate_core_env():
    """Fail-fast for core environment configuration before hitting the DB.

    Must have SUPABASE_URL and SUPABASE_SERVICE_KEY to initialize credentials.
    """
    supabase_url = os.getenv("SUPABASE_URL")
    supabase_service_key = os.getenv("SUPABASE_SERVICE_KEY")
    missing = []
    if not supabase_url:
        missing.append("SUPABASE_URL")
    if not supabase_service_key:
        missing.append("SUPABASE_SERVICE_KEY")
    if missing:
        raise RuntimeError(
            "Missing required environment variables: "
            + ", ".join(missing)
            + ". Set them in your .env before starting Archon."
        )

    # _validate_core_env only checks core env presence; PRP readiness is handled above


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan manager for startup and shutdown tasks."""
    global _initialization_complete
    _initialization_complete = False

    # Startup
    logger.info("🚀 Starting Archon backend...")

    try:
        # Validate configuration FIRST - check for anon vs service key
        from .config.config import get_config

        get_config()  # This will raise ConfigurationError if anon key detected

        # Fail fast on core env
        _validate_core_env()

        # Initialize credentials from database FIRST - this is the foundation for everything else
        await initialize_credentials()

        # Now that credentials are loaded, we can properly initialize logging
        # This must happen AFTER credentials so LOGFIRE_ENABLED is set from database
        setup_logfire(service_name="archon-backend")

        # Now we can safely use the logger
        logger.info("✅ Credentials initialized")
        api_logger.info("🔥 Logfire initialized for backend")

        # Initialize crawling context
        try:
            await initialize_crawler()
        except Exception as e:
            api_logger.warning(f"Could not fully initialize crawling context: {str(e)}")

        # Make crawling context available to modules
        # Crawler is now managed by CrawlerManager

        api_logger.info("✅ Using polling for real-time updates")

        # Fail-fast for PRP when enabled (critical dependency)
        try:
            await _validate_prp_startup()
            api_logger.info("✅ PRP system validation passed")
        except Exception as prp_err:
            api_logger.error(f"❌ PRP startup validation failed: {prp_err}")
            raise

        # Initialize prompt service
        try:
            from .services.prompt_service import prompt_service

            await prompt_service.load_prompts()
            api_logger.info("✅ Prompt service initialized")
        except Exception as e:
            api_logger.warning(f"Could not initialize prompt service: {e}")

        # Set the main event loop for background tasks
        try:
            from .services.background_task_manager import get_task_manager

            task_manager = get_task_manager()
            current_loop = asyncio.get_running_loop()
            task_manager.set_main_loop(current_loop)
            api_logger.info("✅ Main event loop set for background tasks")
        except Exception as e:
            api_logger.warning(f"Could not set main event loop: {e}")

        # Start embeddings health monitor (periodic logging only)
        try:
            from .services.background_task_manager import get_task_manager as _get_tm

            tm = _get_tm()
            await tm.submit_task(run_embeddings_health_monitor, task_args=())
            api_logger.info("✅ Embeddings health monitor started")
        except Exception as e:
            api_logger.warning(f"Could not start embeddings health monitor: {e}")

        # Optionally start embeddings backfill scheduler (disabled by default)
        try:
            enabled = os.getenv("EMBEDDINGS_AUTOBACKFILL_ENABLED", "false").lower() in ("true", "1", "yes", "on")
            if enabled:
                from .services.embeddings.embeddings_maintenance_service import run_embeddings_backfill_scheduler

                await tm.submit_task(run_embeddings_backfill_scheduler, task_args=())
                api_logger.info("✅ Embeddings backfill scheduler started")
            else:
                api_logger.info("ℹ️ Embeddings backfill scheduler disabled (set EMBEDDINGS_AUTOBACKFILL_ENABLED=true to enable)")
        except Exception as e:
            api_logger.warning(f"Could not start embeddings backfill scheduler: {e}")

        # MCP Client functionality removed from architecture
        # Agents now use MCP tools directly

        # Mark initialization as complete
        _initialization_complete = True
        api_logger.info("🎉 Archon backend started successfully!")

    except Exception as e:
        api_logger.error(f"❌ Failed to start backend: {str(e)}")
        raise

    yield

    # Shutdown
    _initialization_complete = False
    api_logger.info("🛑 Shutting down Archon backend...")

    try:
        # MCP Client cleanup not needed

        # Cleanup crawling context
        try:
            await cleanup_crawler()
        except Exception as e:
            api_logger.warning("Could not cleanup crawling context", error=str(e))

        # Cleanup background task manager
        try:
            await cleanup_task_manager()
            api_logger.info("Background task manager cleaned up")
        except Exception as e:
            api_logger.warning("Could not cleanup background task manager", error=str(e))

        api_logger.info("✅ Cleanup completed")

    except Exception as e:
        api_logger.error(f"❌ Error during shutdown: {str(e)}")


# Create FastAPI application
app = FastAPI(
    title="Archon Knowledge Engine API",
    description="Backend API for the Archon knowledge management and project automation platform",
    version="1.0.0",
    lifespan=lifespan,
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Allow all origins for development
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# Add middleware to skip logging for health checks
@app.middleware("http")
async def skip_health_check_logs(request, call_next):
    # Skip logging for health check endpoints
    if request.url.path in ["/health", "/api/health"]:
        # Temporarily suppress the log
        import logging

        logger = logging.getLogger("uvicorn.access")
        old_level = logger.level
        logger.setLevel(logging.ERROR)
        response = await call_next(request)
        logger.setLevel(old_level)
        return response
    return await call_next(request)


@app.middleware("http")
async def apply_security_headers(request: Request, call_next):
    response = await call_next(request)
    response.headers["Content-Security-Policy"] = _CSP_POLICY
    response.headers.setdefault("Referrer-Policy", "strict-origin-when-cross-origin")
    return response


# Include API routers
app.include_router(settings_router)
app.include_router(mcp_router)
# app.include_router(mcp_client_router)  # Removed - not part of new architecture
app.include_router(knowledge_router)
app.include_router(obsidian_router)
app.include_router(projects_router)
app.include_router(progress_router)
app.include_router(agent_chat_router)
app.include_router(chatkit_router)
app.include_router(internal_router)
app.include_router(bug_report_router)
app.include_router(embeddings_router)
app.include_router(tagging_router)


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint returning API information."""
    return {
        "name": "Archon Knowledge Engine API",
        "version": "1.0.0",
        "description": "Backend API for knowledge management and project automation",
        "status": "healthy",
        "modules": ["settings", "mcp", "mcp-clients", "knowledge", "projects"],
    }


# Health check endpoint
@app.get("/health")
async def health_check():
    """Health check endpoint that indicates true readiness including credential loading."""
    from datetime import datetime

    # Check if initialization is complete
    if not _initialization_complete:
        return {
            "status": "initializing",
            "service": "archon-backend",
            "timestamp": datetime.now().isoformat(),
            "message": "Backend is starting up, credentials loading...",
            "ready": False,
        }

    # Check for required database schema
    schema_status = await _check_database_schema()
    if not schema_status["valid"]:
        return {
            "status": "migration_required",
            "service": "archon-backend",
            "timestamp": datetime.now().isoformat(),
            "ready": False,
            "migration_required": True,
            "message": schema_status["message"],
            "migration_instructions": "Open Supabase Dashboard → SQL Editor → Run: migration/add_source_url_display_name.sql",
            "schema_valid": False
        }

    # Check hybrid search function signatures (detect common 42804 mismatch)
    search_schema_status = await _check_search_schema()
    if not search_schema_status["valid"]:
        return {
            "status": "migration_required",
            "service": "archon-backend",
            "timestamp": datetime.now().isoformat(),
            "ready": False,
            "migration_required": True,
            "message": search_schema_status["message"],
            "migration_instructions": "Open Supabase Dashboard → SQL Editor → Run: migration/fix_hybrid_search_types.sql",
            "schema_valid": True,
            "search_schema_valid": False,
        }

    return {
        "status": "healthy",
        "service": "archon-backend",
        "timestamp": datetime.now().isoformat(),
        "ready": True,
        "credentials_loaded": True,
        "schema_valid": True,
        "search_schema_valid": True,
    }


# API health check endpoint (alias for /health at /api/health)
@app.get("/api/health")
async def api_health_check():
    """API health check endpoint - alias for /health."""
    return await health_check()


# Cache schema check result to avoid repeated database queries
_schema_check_cache = {"valid": None, "checked_at": 0}

async def _check_database_schema():
    """Check if required database schema exists - only for existing users who need migration."""
    import time

    # If we've already confirmed schema is valid, don't check again
    if _schema_check_cache["valid"] is True:
        return {"valid": True, "message": "Schema is up to date (cached)"}

    # If we recently failed, don't spam the database (wait at least 30 seconds)
    current_time = time.time()
    if (_schema_check_cache["valid"] is False and
        current_time - _schema_check_cache["checked_at"] < 30):
        return _schema_check_cache["result"]

    try:
        from .services.client_manager import get_supabase_client

        client = get_supabase_client()

        # Try to query the new columns directly - if they exist, schema is up to date
        test_query = client.table('archon_sources').select('source_url, source_display_name').limit(1).execute()

        # Cache successful result permanently
        _schema_check_cache["valid"] = True
        _schema_check_cache["checked_at"] = current_time

        return {"valid": True, "message": "Schema is up to date"}

    except Exception as e:
        error_msg = str(e).lower()

        # Log schema check error for debugging
        api_logger.debug(f"Schema check error: {type(e).__name__}: {str(e)}")

        # Check for specific error types based on PostgreSQL error codes and messages

        # Check for missing columns first (more specific than table check)
        missing_source_url = 'source_url' in error_msg and ('column' in error_msg or 'does not exist' in error_msg)
        missing_source_display = 'source_display_name' in error_msg and ('column' in error_msg or 'does not exist' in error_msg)

        # Also check for PostgreSQL error code 42703 (undefined column)
        is_column_error = '42703' in error_msg or 'column' in error_msg

        if (missing_source_url or missing_source_display) and is_column_error:
            result = {
                "valid": False,
                "message": "Database schema outdated - missing required columns from recent updates"
            }
            # Cache failed result with timestamp
            _schema_check_cache["valid"] = False
            _schema_check_cache["checked_at"] = current_time
            _schema_check_cache["result"] = result
            return result

        # Check for table doesn't exist (less specific, only if column check didn't match)
        # Look for relation/table errors specifically
        if ('relation' in error_msg and 'does not exist' in error_msg) or ('table' in error_msg and 'does not exist' in error_msg):
            # Table doesn't exist - not a migration issue, it's a setup issue
            return {"valid": True, "message": "Table doesn't exist - handled by startup error"}

        # Other errors don't necessarily mean migration needed
        result = {"valid": True, "message": f"Schema check inconclusive: {str(e)}"}
        # Don't cache inconclusive results - allow retry
        return result


# Additional search schema check for hybrid function signature/type issues
async def _check_search_schema():
    """Validate hybrid search functions are callable and not suffering type mismatch.

    Detects the common PostgreSQL 42804 error: structure of query does not match function result type
    caused by url declared as VARCHAR in RETURNS TABLE while underlying data is TEXT.
    """
    try:
        from .services.client_manager import get_supabase_client

        client = get_supabase_client()

        # Minimal, read-only probe parameters
        probe_embedding = [0.0] * 1536  # Does not persist; safe for health check
        rpc_params = {
            "query_embedding": probe_embedding,
            "query_text": "health_check",
            "match_count": 1,
            "filter": {},
            "source_filter": None,
        }

        # Call both hybrid functions. Empty result is OK; exceptions indicate schema issues.
        # Check hybrid functions (already present)
        try:
            client.rpc("hybrid_search_archon_crawled_pages", rpc_params).execute()
        except Exception as e:
            msg = str(e)
            lower = msg.lower()
            # 42804: structure mismatch; 42883: function does not exist
            if "42804" in lower or "does not match function result type" in lower:
                return {
                    "valid": False,
                    "message": (
                        "Hybrid search function type mismatch detected (crawled pages). "
                        "Apply migration/fix_hybrid_search_types.sql to set url as TEXT."
                    ),
                }
            if "42883" in lower or "function" in lower and "does not exist" in lower:
                return {
                    "valid": False,
                    "message": (
                        "Hybrid search function missing (crawled pages). Run migrations to create it."
                    ),
                }
            # Other errors don't necessarily indicate migration; surface as inconclusive
            api_logger.debug(f"Hybrid search check (crawled) inconclusive: {msg}")

        try:
            client.rpc("hybrid_search_archon_code_examples", rpc_params).execute()
        except Exception as e:
            msg = str(e)
            lower = msg.lower()
            if "42804" in lower or "does not match function result type" in lower:
                return {
                    "valid": False,
                    "message": (
                        "Hybrid code search function type mismatch detected. "
                        "Apply migration/fix_hybrid_search_types.sql to set url as TEXT."
                    ),
                }
            if "42883" in lower or "function" in lower and "does not exist" in lower:
                return {
                    "valid": False,
                    "message": (
                        "Hybrid code search function missing. Run migrations to create it."
                    ),
                }
            api_logger.debug(f"Hybrid search check (code) inconclusive: {msg}")

        # Check match functions as well for url type mismatches
        try:
            client.rpc("match_archon_crawled_pages", {
                "query_embedding": probe_embedding,
                "match_count": 1,
                "filter": {},
                "source_filter": None,
            }).execute()
        except Exception as e:
            msg = str(e)
            lower = msg.lower()
            if "42804" in lower or "does not match function result type" in lower:
                return {
                    "valid": False,
                    "message": (
                        "Match search function type mismatch detected (crawled pages). "
                        "Apply migration/fix_match_search_types.sql to set url as TEXT."
                    ),
                }
            if "42883" in lower or ("function" in lower and "does not exist" in lower):
                return {
                    "valid": False,
                    "message": (
                        "Match search function missing (crawled pages). Run migrations to create it."
                    ),
                }

        try:
            client.rpc("match_archon_code_examples", {
                "query_embedding": probe_embedding,
                "match_count": 1,
                "filter": {},
                "source_filter": None,
            }).execute()
        except Exception as e:
            msg = str(e)
            lower = msg.lower()
            if "42804" in lower or "does not match function result type" in lower:
                return {
                    "valid": False,
                    "message": (
                        "Match search function type mismatch detected (code examples). "
                        "Apply migration/fix_match_search_types.sql to set url as TEXT."
                    ),
                }
            if "42883" in lower or ("function" in lower and "does not exist" in lower):
                return {
                    "valid": False,
                    "message": (
                        "Match search function missing (code examples). Run migrations to create it."
                    ),
                }

        return {"valid": True, "message": "Hybrid and match search functions healthy"}

    except Exception as e:
        # If any unexpected error, don't falsely block startup; report inconclusive
        api_logger.debug(f"Search schema check error: {type(e).__name__}: {str(e)}")
        return {"valid": True, "message": f"Search schema check inconclusive: {str(e)}"}


# Export the app directly for uvicorn to use


def main():
    """Main entry point for running the server."""
    import uvicorn

    # Require ARCHON_SERVER_PORT to be set
    server_port = os.getenv("ARCHON_SERVER_PORT")
    if not server_port:
        raise ValueError(
            "ARCHON_SERVER_PORT environment variable is required. "
            "Please set it in your .env file or environment. "
            "Default value: 8181"
        )

    uvicorn.run(
        "src.server.main:app",
        host="0.0.0.0",
        port=int(server_port),
        reload=True,
        log_level="info",
    )


if __name__ == "__main__":
    main()
