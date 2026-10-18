"""Application package initialization for DocFoundry backend.

This module exposes helpers for creating and configuring the FastAPI
application instance. It is intentionally lightweight so it can be
imported by different entrypoints (HTTP API server, worker processes, etc.)
without side effects like starting servers.
"""

from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import FastAPI

from .database import init_db

logger = logging.getLogger(__name__)


def create_app() -> FastAPI:
    """Create and configure the main FastAPI application instance.

    Returns:
        FastAPI: Configured FastAPI application.
    """
    app = FastAPI(
        title="DocFoundry API",
        description=(
            "DocFoundry is an API-first multi-tenant SaaS for turning unstructured "
            "documents into clean, structured data with templates, webhooks, and "
            "usage-based billing."
        ),
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        redoc_url="/api/redoc",
    )

    register_event_handlers(app)
    register_routers(app)

    return app


def register_event_handlers(app: FastAPI) -> None:
    """Register global application event handlers such as startup/shutdown."""

    @app.on_event("startup")
    async def on_startup() -> None:
        """Application startup hook.

        Initializes the database and performs any other one-time startup tasks.
        """
        logger.info("Starting DocFoundry backend application")
        try:
            await init_db()
        except Exception:
            logger.exception("Failed to initialize database on startup")
            # In a real production setup you might choose to re-raise here
            # to fail fast; for now we log the error.
            # raise

    @app.on_event("shutdown")
    async def on_shutdown() -> None:
        """Application shutdown hook.

        Can be extended to close resources like connections, thread pools, etc.
        """
        logger.info("Shutting down DocFoundry backend application")


def register_routers(app: FastAPI) -> None:
    """Mount all API routers onto the application.

    Note:
        This function is intentionally a placeholder. As feature modules
        (auth, projects, templates, documents, etc.) are implemented,
        their routers should be imported and included here, for example:

        from .routers import auth, projects

        app.include_router(auth.router, prefix="/api/auth", tags=["auth"])
        app.include_router(projects.router, prefix="/api/projects", tags=["projects"])
    """
    # Placeholder for future router registrations to avoid cyclic imports
    # when routers in turn import `create_app`.
    pass


def get_app() -> FastAPI:
    """Return a singleton FastAPI application instance.

    This helper is useful for ASGI servers such as Uvicorn or Hypercorn
    which expect a module-level callable named `app`, while still allowing
    for testability and configuration via `create_app()`.

    Returns:
        FastAPI: Singleton FastAPI application.
    """
    return create_app()


# ASGI entrypoint expected by most servers: `uvicorn app:app`
app: FastAPI = get_app()


def __all_app_objects() -> Dict[str, Any]:
    """Internal helper exposing objects for introspection and tooling."""
    return {
        "app": app,
        "create_app": create_app,
        "get_app": get_app,
    }


__all__ = ["app", "create_app", "get_app"]