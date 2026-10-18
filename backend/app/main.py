import logging
import os
from typing import Any, Dict, List, Set

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.middleware.sessions import SessionMiddleware
from starlette.status import HTTP_422_UNPROCESSABLE_ENTITY, HTTP_429_TOO_MANY_REQUESTS, HTTP_500_INTERNAL_SERVER_ERROR

from .config import settings
from .database import engine
from .middleware.security_headers_middleware import SecurityHeadersMiddleware
from .middleware.request_size_middleware import RequestSizeMiddleware
from .services.rate_limit_service import get_limiter

logger = logging.getLogger("docfoundry")
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO"),
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
)

# Default browser origins for local development (user app, admin app, Astro marketing).
_DEFAULT_DEV_CORS_ORIGINS: List[str] = [
    "http://localhost:3000",
    "http://localhost:3001",
    "http://localhost:4321",
]


def _parse_configured_cors_origins(raw_origins: List[Any]) -> List[str]:
    """Turn settings (str or pydantic AnyHttpUrl) into plain origin strings."""
    valid: List[str] = []
    for origin in raw_origins:
        s = str(origin).strip()
        if not s:
            continue
        if s == "*":
            valid.append("*")
        elif s.startswith(("http://", "https://")):
            valid.append(s.rstrip("/"))
        else:
            logger.warning("Invalid CORS origin format (ignored): %s", origin)
    return valid


def _dedupe_cors_origins(origins: List[str]) -> List[str]:
    """Strip trailing slashes (pydantic URLs may add '/') and dedupe; keep order."""
    out: List[str] = []
    seen: Set[str] = set()
    for o in origins:
        o = o.strip()
        if not o:
            continue
        key = "*" if o == "*" else o.rstrip("/")
        if key not in seen:
            seen.add(key)
            out.append(key)
    return out


def create_app() -> FastAPI:
    """
    Application factory for the DocFoundry.app backend.

    This is the main FastAPI instance used by the ASGI server.
    Routers are mounted here and global middleware is configured.
    """
    app = FastAPI(
        title="DocFoundry.app API",
        description="Forge any document into clean, usable data.",
        version=os.getenv("APP_VERSION", "0.1.0"),
        openapi_url="/api/openapi.json",
        docs_url="/api/docs",
        redoc_url="/api/redoc",
    )

    # CORS: never use allow_origins=["*"] with allow_credentials=True (browsers reject it).
    cors_origins: List[str]
    raw = settings.CORS_ALLOW_ORIGINS

    if not raw:
        if settings.ENVIRONMENT == "production":
            logger.error(
                "CORS_ALLOW_ORIGINS is empty in production. "
                "Set explicit origins (browsers cannot use cookie credentials with wildcard CORS)."
            )
            cors_origins = []
        else:
            cors_origins = list(_DEFAULT_DEV_CORS_ORIGINS)
            logger.info(
                "CORS: Using default development origins: %s",
                ", ".join(cors_origins),
            )
    else:
        cors_origins = _parse_configured_cors_origins(list(raw))
        if settings.ENVIRONMENT != "production" and "*" not in cors_origins:
            for dev_origin in _DEFAULT_DEV_CORS_ORIGINS:
                if dev_origin not in cors_origins:
                    cors_origins.append(dev_origin)
                    logger.info("CORS: Added development origin: %s", dev_origin)
        if not cors_origins:
            if settings.ENVIRONMENT == "production":
                logger.error(
                    "CORS_ALLOW_ORIGINS had no valid entries. "
                    "Configure explicit http(s) origins for credentialed API access."
                )
            else:
                cors_origins = list(_DEFAULT_DEV_CORS_ORIGINS)
                logger.warning(
                    "CORS: No valid configured origins; falling back to default development list."
                )

    if settings.CORS_ALLOW_CREDENTIALS and "*" in cors_origins:
        logger.warning(
            "CORS wildcard '*' is incompatible with CORS_ALLOW_CREDENTIALS=true; "
            "removing wildcard from allowed origins."
        )
        cors_origins = [o for o in cors_origins if o != "*"]
        if not cors_origins:
            if settings.ENVIRONMENT == "production":
                logger.error(
                    "No CORS origins left after removing wildcard. Set CORS_ALLOW_ORIGINS explicitly."
                )
            else:
                cors_origins = list(_DEFAULT_DEV_CORS_ORIGINS)
                logger.info("CORS: Using default development origins after wildcard strip.")

    cors_origins = _dedupe_cors_origins(cors_origins)
    logger.info("CORS allow_origins: %s", cors_origins if cors_origins else "(none — cross-origin browser calls blocked)")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=cors_origins,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=settings.CORS_ALLOW_METHODS if settings.CORS_ALLOW_METHODS != ["*"] else ["*"],
        allow_headers=settings.CORS_ALLOW_HEADERS if settings.CORS_ALLOW_HEADERS != ["*"] else ["*"],
        max_age=3600,  # Cache preflight requests for 1 hour
    )

    # Session middleware (used for CSRF / potential future cookie helpers)
    session_secret = os.getenv("SESSION_SECRET", "dev-secret-change-me")
    app.add_middleware(SessionMiddleware, secret_key=session_secret)

    # Request size limiting middleware (should be early in the stack)
    app.add_middleware(RequestSizeMiddleware)
    
    # Security headers middleware (must be after CORS to override headers)
    app.add_middleware(SecurityHeadersMiddleware)

    # Rate limiting
    limiter = get_limiter()
    if limiter:
        app.state.limiter = limiter
        # Add rate limit exception handler
        try:
            from slowapi.errors import RateLimitExceeded
            @app.exception_handler(RateLimitExceeded)
            async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
                """Handle rate limit exceeded errors."""
                response = JSONResponse(
                    status_code=HTTP_429_TOO_MANY_REQUESTS,
                    content={
                        "detail": "Rate limit exceeded. Please try again later.",
                        "retry_after": exc.retry_after if hasattr(exc, 'retry_after') else None,
                    },
                )
                if hasattr(exc, 'retry_after') and exc.retry_after:
                    response.headers["Retry-After"] = str(exc.retry_after)
                return response
        except ImportError:
            logger.warning("slowapi not available, rate limiting disabled")

    register_event_handlers(app)
    register_exception_handlers(app)
    register_routers(app)

    return app


def register_event_handlers(app: FastAPI) -> None:
    """Register startup and shutdown event handlers."""

    @app.on_event("startup")
    async def on_startup() -> None:
        """
        Startup hook for the application.

        This is a good place to run database connectivity checks,
        initialize external clients, or warm any caches.
        """
        try:
            # Simple DB connectivity check (async)
            from sqlalchemy import text
            async with engine.begin() as conn:
                await conn.execute(text("SELECT 1"))
            logger.info("Database connection established successfully on startup.")
            
            # Check if tables have been created by checking for core tables
            try:
                async with engine.begin() as conn:
                    # Check if users table exists (core table for most apps)
                    result = await conn.execute(
                        text("""
                            SELECT EXISTS (
                                SELECT FROM information_schema.tables 
                                WHERE table_schema = 'public' 
                                AND table_name = 'users'
                            )
                        """)
                    )
                    table_exists = result.scalar()
                    
                    if not table_exists:
                        logger.warning(
                            "Database tables not found. Tables may not have been created. "
                            "Run: python scripts/create_tables.py"
                        )
                        # In development mode, optionally auto-create tables
                        if os.getenv("ENVIRONMENT", "development").lower() == "development":
                            auto_create = os.getenv("AUTO_CREATE_TABLES", "false").lower() == "true"
                            if auto_create:
                                logger.info("Attempting to auto-create tables...")
                                try:
                                    import subprocess
                                    import sys
                                    from pathlib import Path
                                    backend_dir = Path(__file__).parent.parent.parent
                                    result = subprocess.run(
                                        [sys.executable, str(backend_dir / "scripts" / "create_tables.py")],
                                        cwd=str(backend_dir),
                                        capture_output=True,
                                        text=True,
                                        timeout=60
                                    )
                                    if result.returncode == 0:
                                        logger.info("Tables created successfully")
                                    else:
                                        logger.error(f"Failed to create tables: {result.stderr}")
                                except Exception as create_exc:
                                    logger.exception("Error auto-creating tables: %s", create_exc)
                    else:
                        logger.info("Database tables found - tables appear to be created")
            except Exception as check_exc:
                logger.warning("Could not check database table status: %s", check_exc)
                # Don't fail startup if check fails, but log the warning
                
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Error connecting to database on startup: %s", exc)
            # Do not re-raise here to avoid crashing container; rely on liveness probes.

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        """
        Shutdown hook for the application.

        Ensures DB engine is disposed and external resources are cleaned up.
        """
        try:
            await engine.dispose()
            logger.info("Database engine disposed on shutdown.")
        except Exception as exc:  # pragma: no cover - defensive
            logger.exception("Error disposing database engine on shutdown: %s", exc)


def register_exception_handlers(app: FastAPI) -> None:
    """Attach global exception handlers for consistent error responses."""

    @app.exception_handler(RequestValidationError)
    async def validation_exception_handler(
        request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        logger.warning(
            "Validation error on %s %s: %s",
            request.method,
            request.url.path,
            exc.errors(),
        )
        return JSONResponse(
            status_code=HTTP_422_UNPROCESSABLE_ENTITY,
            content={
                "detail": "Invalid request.",
                "errors": exc.errors(),
            },
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(request: Request, exc: Exception) -> JSONResponse:
        logger.exception("Unhandled error on %s %s: %s", request.method, request.url.path, exc)
        return JSONResponse(
            status_code=HTTP_500_INTERNAL_SERVER_ERROR,
            content={"detail": "Internal server error."},
        )


def register_routers(app: FastAPI) -> None:
    """
    Include all API routers under the `/api` namespace.

    Routers for individual modules (auth, projects, templates, etc.)
    should be defined in their respective `routers` packages.
    """
    # Import lazily to avoid circular imports at module load time.
    try:
        from .routers import (
            auth,
            projects,
            templates,
            template_library,
            documents,
            exports,
            api_keys,
            webhooks,
            usage,
            notifications,
            audit,
            admin,
            admin_auth,
            admin_affiliates,
            admin_coupons,
            public_api,
            workspace,
            billing,
            affiliates,
            redirect,
        )
    except ImportError as exc:  # pragma: no cover - during early scaffolding
        logger.error("Critical: Some routers could not be imported: %s", exc, exc_info=True)
        raise RuntimeError(f"Failed to import routers: {exc}") from exc

    # Helper function to safely register a router
    def register_router(router_module, prefix: str, tags: list[str], router_name: str) -> bool:
        """Register a router if it exists and has a router attribute."""
        if router_module is None:
            logger.error("Router module '%s' is None - registration skipped!", router_name)
            return False
        
        if not hasattr(router_module, 'router'):
            logger.error("Router module '%s' does not have 'router' attribute - registration skipped!", router_name)
            return False
        
        router = getattr(router_module, 'router')
        if router is None:
            logger.error("Router '%s' is None - registration skipped!", router_name)
            return False
        
        try:
            app.include_router(router, prefix=prefix, tags=tags)
            logger.info("Router '%s' registered successfully at prefix '%s'", router_name, prefix)
            return True
        except Exception as e:
            logger.exception("Failed to register router '%s': %s", router_name, e)
            return False

    # Auth and user/session management
    register_router(auth, "/api/auth", ["auth"], "auth")

    # Workspace branding / current workspace
    register_router(workspace, "/api/workspaces", ["workspace"], "workspace")

    # Core resources - these are critical for the app to function
    projects_registered = register_router(projects, "/api/projects", ["projects"], "projects")
    if not projects_registered:
        logger.error("CRITICAL: Projects router failed to register - /api/projects will return 404!")
    
    register_router(templates, "/api/templates", ["templates"], "templates")
    register_router(template_library, "/api/template-library", ["template-library"], "template_library")
    
    documents_registered = register_router(documents, "/api/documents", ["documents"], "documents")
    if not documents_registered:
        logger.error("CRITICAL: Documents router failed to register - /api/documents will return 404!")
    
    # Exports download endpoint
    register_router(exports, "/api/exports", ["exports"], "exports")

    # API keys & public programmatic API
    register_router(api_keys, "/api/api-keys", ["api-keys"], "api_keys")
    register_router(public_api, "/api/v1", ["public-api"], "public_api")

    # Webhooks
    register_router(webhooks, "/api", ["webhooks"], "webhooks")

    # Usage and billing-related (usage only here; Stripe webhooks etc. live elsewhere)
    usage_registered = register_router(usage, "/api/usage", ["usage"], "usage")
    if not usage_registered:
        logger.error("CRITICAL: Usage router failed to register - /api/usage/* will return 404!")
    
    # Billing and Stripe integration
    register_router(billing, "/api/billing", ["billing"], "billing")

    # Notifications & audit logs
    register_router(notifications, "/api/notifications", ["notifications"], "notifications")
    register_router(audit, "/api/audit-logs", ["audit-logs"], "audit")

    # Admin-only endpoints
    register_router(admin_auth, "/api", ["admin-auth"], "admin_auth")  # /api/admin/auth/*
    register_router(admin, "/api/admin", ["admin"], "admin")
    register_router(admin_affiliates, "/api/admin/affiliates", ["admin", "affiliates"], "admin_affiliates")
    register_router(admin_coupons, "/api/admin/coupons", ["admin", "coupons"], "admin_coupons")
    
    # Affiliate portal endpoints
    register_router(affiliates, "/api/affiliates", ["affiliates"], "affiliates")
    
    # Public redirect endpoint (no /api prefix)
    register_router(redirect, "", ["redirect"], "redirect")
    
    logger.info("Router registration completed")


app = create_app()


@app.get("/health", tags=["health"])
async def healthcheck() -> Dict[str, Any]:
    """
    Lightweight health endpoint for liveness checks.

    This does not hit the database; use a different readiness probe
    if you need deeper dependency checks.
    """
    return {"status": "ok"}