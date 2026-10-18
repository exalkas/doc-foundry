"""Router package initialization for DocFoundry backend.

This module exposes routers for direct import by main.py.
"""

from __future__ import annotations

# Import routers for direct access by main.py
# Use try/except to handle missing routers gracefully during development
import logging

logger = logging.getLogger(__name__)

# Initialize all routers as None first to avoid circular import issues
auth = None
projects = None
templates = None
documents = None
api_keys = None
webhooks = None
usage = None
notifications = None
audit = None
admin = None
admin_affiliates = None
public_api = None
workspace = None
billing = None
affiliates = None
redirect = None
template_library = None
exports = None

# Now try to import each router module
# Import the router directly first to catch any import errors
try:
    from .auth import router as auth_router
    # If that works, import the module
    from . import auth as _auth_module
    auth = _auth_module
    # Ensure router is set (in case module import was partial)
    if not hasattr(auth, 'router'):
        auth.router = auth_router
    logger.info("Auth router imported successfully")
except ImportError as e:
    logger.error("ImportError importing auth router: %s", e, exc_info=True)
except SyntaxError as e:
    logger.error("SyntaxError in auth router: %s", e, exc_info=True)
except Exception as e:
    logger.error("Unexpected error importing auth router: %s", e, exc_info=True)
    import traceback
    logger.error("Full traceback:\n%s", traceback.format_exc())

try:
    # Import the router directly first to catch any import errors
    from .projects import router as projects_router
    # If that succeeds, import the module
    from . import projects as _projects_module
    projects = _projects_module
    # Verify router exists
    if not hasattr(projects, 'router') or getattr(projects, 'router', None) is None:
        logger.error("Projects module imported but router attribute is missing or None")
        projects = None
    else:
        logger.info("Projects router imported successfully")
except ImportError as e:
    logger.error("ImportError importing projects router: %s", e, exc_info=True)
    projects = None
except SyntaxError as e:
    logger.error("SyntaxError in projects router: %s", e, exc_info=True)
    projects = None
except AttributeError as e:
    logger.error("AttributeError importing projects router (router not found): %s", e, exc_info=True)
    projects = None
except Exception as e:
    logger.error("Unexpected error importing projects router: %s", e, exc_info=True)
    import traceback
    logger.error("Full traceback:\n%s", traceback.format_exc())
    projects = None

try:
    # Import the router directly first to catch any import errors
    from .templates import router as templates_router
    # If that succeeds, import the module
    from . import templates as _templates_module
    templates = _templates_module
    # Verify router exists
    if not hasattr(templates, 'router') or getattr(templates, 'router', None) is None:
        logger.error("Templates module imported but router attribute is missing or None")
        templates = None
    else:
        logger.info("Templates router imported successfully")
except ImportError as e:
    logger.error("ImportError importing templates router: %s", e, exc_info=True)
    templates = None
except SyntaxError as e:
    logger.error("SyntaxError in templates router: %s", e, exc_info=True)
    templates = None
except AttributeError as e:
    logger.error("AttributeError importing templates router (router not found): %s", e, exc_info=True)
    templates = None
except Exception as e:
    logger.error("Unexpected error importing templates router: %s", e, exc_info=True)
    import traceback
    logger.error("Full traceback:\n%s", traceback.format_exc())
    templates = None

try:
    # Import the router directly first to catch any import errors
    from .documents import router as documents_router
    # If that succeeds, import the module
    from . import documents as _documents_module
    documents = _documents_module
    # Verify router exists
    if not hasattr(documents, 'router') or getattr(documents, 'router', None) is None:
        logger.error("Documents module imported but router attribute is missing or None")
        documents = None
    else:
        logger.info("Documents router imported successfully")
except ImportError as e:
    logger.error("ImportError importing documents router: %s", e, exc_info=True)
    documents = None
except SyntaxError as e:
    logger.error("SyntaxError in documents router: %s", e, exc_info=True)
    documents = None
except AttributeError as e:
    logger.error("AttributeError importing documents router (router not found): %s", e, exc_info=True)
    documents = None
except Exception as e:
    logger.error("Unexpected error importing documents router: %s", e, exc_info=True)
    import traceback
    logger.error("Full traceback:\n%s", traceback.format_exc())
    documents = None

try:
    # Import the router directly first to catch any import errors
    from .api_keys import router as api_keys_router
    # If that succeeds, import the module
    from . import api_keys as _api_keys_module
    api_keys = _api_keys_module
    # Verify router exists
    if not hasattr(api_keys, 'router') or getattr(api_keys, 'router', None) is None:
        logger.error("API keys module imported but router attribute is missing or None")
        api_keys = None
    else:
        logger.info("API keys router imported successfully")
except ImportError as e:
    logger.error("ImportError importing api_keys router: %s", e, exc_info=True)
    api_keys = None
except SyntaxError as e:
    logger.error("SyntaxError in api_keys router: %s", e, exc_info=True)
    api_keys = None
except AttributeError as e:
    logger.error("AttributeError importing api_keys router (router not found): %s", e, exc_info=True)
    api_keys = None
except Exception as e:
    logger.error("Unexpected error importing api_keys router: %s", e, exc_info=True)
    import traceback
    logger.error("Full traceback:\n%s", traceback.format_exc())
    api_keys = None

try:
    # Import the router directly first to catch any import errors
    from .webhooks import router as webhooks_router
    # If that succeeds, import the module
    from . import webhooks as _webhooks_module
    webhooks = _webhooks_module
    # Verify router exists
    if not hasattr(webhooks, 'router') or getattr(webhooks, 'router', None) is None:
        logger.error("Webhooks module imported but router attribute is missing or None")
        webhooks = None
    else:
        logger.info("Webhooks router imported successfully")
except ImportError as e:
    logger.error("ImportError importing webhooks router: %s", e, exc_info=True)
    webhooks = None
except SyntaxError as e:
    logger.error("SyntaxError in webhooks router: %s", e, exc_info=True)
    webhooks = None
except AttributeError as e:
    logger.error("AttributeError importing webhooks router (router not found): %s", e, exc_info=True)
    webhooks = None
except Exception as e:
    logger.error("Unexpected error importing webhooks router: %s", e, exc_info=True)
    import traceback
    logger.error("Full traceback:\n%s", traceback.format_exc())
    webhooks = None

try:
    # Import the router directly first to catch any import errors
    from .usage import router as usage_router
    # If that succeeds, import the module
    from . import usage as _usage_module
    usage = _usage_module
    # Verify router exists
    if not hasattr(usage, 'router') or getattr(usage, 'router', None) is None:
        logger.error("Usage module imported but router attribute is missing or None")
        usage = None
    else:
        logger.info("Usage router imported successfully")
except ImportError as e:
    logger.error("ImportError importing usage router: %s", e, exc_info=True)
    usage = None
except SyntaxError as e:
    logger.error("SyntaxError in usage router: %s", e, exc_info=True)
    usage = None
except AttributeError as e:
    logger.error("AttributeError importing usage router (router not found): %s", e, exc_info=True)
    usage = None
except Exception as e:
    logger.error("Unexpected error importing usage router: %s", e, exc_info=True)
    import traceback
    logger.error("Full traceback:\n%s", traceback.format_exc())
    usage = None

try:
    # Import the router directly first to catch any import errors
    from .notifications import router as notifications_router
    # If that succeeds, import the module
    from . import notifications as _notifications_module
    notifications = _notifications_module
    # Verify router exists
    if not hasattr(notifications, 'router') or getattr(notifications, 'router', None) is None:
        logger.error("Notifications module imported but router attribute is missing or None")
        notifications = None
    else:
        logger.info("Notifications router imported successfully")
except ImportError as e:
    logger.error("ImportError importing notifications router: %s", e, exc_info=True)
    notifications = None
except SyntaxError as e:
    logger.error("SyntaxError in notifications router: %s", e, exc_info=True)
    notifications = None
except AttributeError as e:
    logger.error("AttributeError importing notifications router (router not found): %s", e, exc_info=True)
    notifications = None
except Exception as e:
    logger.error("Unexpected error importing notifications router: %s", e, exc_info=True)
    import traceback
    logger.error("Full traceback:\n%s", traceback.format_exc())
    notifications = None

try:
    # Import the router directly first to catch any import errors
    from .audit import router as audit_router
    # If that succeeds, import the module
    from . import audit as _audit_module
    audit = _audit_module
    # Verify router exists
    if not hasattr(audit, 'router') or getattr(audit, 'router', None) is None:
        logger.error("Audit module imported but router attribute is missing or None")
        audit = None
    else:
        logger.info("Audit router imported successfully")
except ImportError as e:
    logger.error("ImportError importing audit router: %s", e, exc_info=True)
    audit = None
except SyntaxError as e:
    logger.error("SyntaxError in audit router: %s", e, exc_info=True)
    audit = None
except AttributeError as e:
    logger.error("AttributeError importing audit router (router not found): %s", e, exc_info=True)
    audit = None
except Exception as e:
    logger.error("Unexpected error importing audit router: %s", e, exc_info=True)
    import traceback
    logger.error("Full traceback:\n%s", traceback.format_exc())
    audit = None

try:
    # Import the router directly first to catch any import errors
    from .admin import router as admin_router
    # If that succeeds, import the module
    from . import admin as _admin_module
    admin = _admin_module
    # Verify router exists
    if not hasattr(admin, 'router') or getattr(admin, 'router', None) is None:
        logger.error("Admin module imported but router attribute is missing or None")
        admin = None
    else:
        logger.info("Admin router imported successfully")
except ImportError as e:
    logger.error("ImportError importing admin router: %s", e, exc_info=True)
    admin = None
except SyntaxError as e:
    logger.error("SyntaxError in admin router: %s", e, exc_info=True)
    admin = None
except AttributeError as e:
    logger.error("AttributeError importing admin router (router not found): %s", e, exc_info=True)
    admin = None
except Exception as e:
    logger.error("Unexpected error importing admin router: %s", e, exc_info=True)
    import traceback
    logger.error("Full traceback:\n%s", traceback.format_exc())
    admin = None

try:
    # Import the router directly first to catch any import errors
    from .public_api import router as public_api_router
    # If that succeeds, import the module
    from . import public_api as _public_api_module
    public_api = _public_api_module
    # Verify router exists
    if not hasattr(public_api, 'router') or getattr(public_api, 'router', None) is None:
        logger.error("Public API module imported but router attribute is missing or None")
        public_api = None
    else:
        logger.info("Public API router imported successfully")
except ImportError as e:
    logger.error("ImportError importing public_api router: %s", e, exc_info=True)
    public_api = None
except SyntaxError as e:
    logger.error("SyntaxError in public_api router: %s", e, exc_info=True)
    public_api = None
except AttributeError as e:
    logger.error("AttributeError importing public_api router (router not found): %s", e, exc_info=True)
    public_api = None
except Exception as e:
    logger.error("Unexpected error importing public_api router: %s", e, exc_info=True)
    import traceback
    logger.error("Full traceback:\n%s", traceback.format_exc())
    public_api = None

try:
    # Import the router directly first to catch any import errors
    from .workspace import router as workspace_router
    # If that succeeds, import the module
    from . import workspace as _workspace_module
    workspace = _workspace_module
    # Verify router exists
    if not hasattr(workspace, 'router') or getattr(workspace, 'router', None) is None:
        logger.error("Workspace module imported but router attribute is missing or None")
        workspace = None
    else:
        logger.info("Workspace router imported successfully")
except ImportError as e:
    logger.error("ImportError importing workspace router: %s", e, exc_info=True)
    workspace = None
except SyntaxError as e:
    logger.error("SyntaxError in workspace router: %s", e, exc_info=True)
    workspace = None
except AttributeError as e:
    logger.error("AttributeError importing workspace router (router not found): %s", e, exc_info=True)
    workspace = None
except Exception as e:
    logger.error("Unexpected error importing workspace router: %s", e, exc_info=True)
    import traceback
    logger.error("Full traceback:\n%s", traceback.format_exc())
    workspace = None

# Import billing router
try:
    from .billing import router as billing_router
    from . import billing as _billing_module
    billing = _billing_module
    if not hasattr(billing, 'router') or getattr(billing, 'router', None) is None:
        billing.router = billing_router
    logger.info("Billing router imported successfully")
except Exception as e:
    logger.error("Error importing billing router: %s", e, exc_info=True)
    billing = None

# Import affiliates router
try:
    from .affiliates import router as affiliates_router
    from . import affiliates as _affiliates_module
    affiliates = _affiliates_module
    if not hasattr(affiliates, 'router') or getattr(affiliates, 'router', None) is None:
        affiliates.router = affiliates_router
    logger.info("Affiliates router imported successfully")
except Exception as e:
    logger.error("Error importing affiliates router: %s", e, exc_info=True)
    affiliates = None

# Import admin_affiliates router
try:
    from .admin_affiliates import router as admin_affiliates_router
    from . import admin_affiliates as _admin_affiliates_module
    admin_affiliates = _admin_affiliates_module
    if not hasattr(admin_affiliates, 'router') or getattr(admin_affiliates, 'router', None) is None:
        admin_affiliates.router = admin_affiliates_router
    logger.info("Admin affiliates router imported successfully")
except Exception as e:
    logger.error("Error importing admin_affiliates router: %s", e, exc_info=True)
    admin_affiliates = None

# Import admin_coupons router
try:
    from .admin_coupons import router as admin_coupons_router
    from . import admin_coupons as _admin_coupons_module
    admin_coupons = _admin_coupons_module
    if not hasattr(admin_coupons, 'router') or getattr(admin_coupons, 'router', None) is None:
        admin_coupons.router = admin_coupons_router
    logger.info("Admin coupons router imported successfully")
except Exception as e:
    logger.error("Error importing admin_coupons router: %s", e, exc_info=True)
    admin_coupons = None

# Import redirect router
try:
    from .redirect import router as redirect_router
    from . import redirect as _redirect_module
    redirect = _redirect_module
    if not hasattr(redirect, 'router') or getattr(redirect, 'router', None) is None:
        redirect.router = redirect_router
    logger.info("Redirect router imported successfully")
except Exception as e:
    logger.error("Error importing redirect router: %s", e, exc_info=True)
    redirect = None

# Import template_library router
try:
    from .template_library import router as template_library_router
    from . import template_library as _template_library_module
    template_library = _template_library_module
    if not hasattr(template_library, 'router') or getattr(template_library, 'router', None) is None:
        template_library.router = template_library_router
    logger.info("Template library router imported successfully")
except Exception as e:
    logger.error("Error importing template_library router: %s", e, exc_info=True)
    template_library = None

# Import exports router
try:
    from .exports import router as exports_router
    from . import exports as _exports_module
    exports = _exports_module
    if not hasattr(exports, 'router') or getattr(exports, 'router', None) is None:
        exports.router = exports_router
    logger.info("Exports router imported successfully")
except Exception as e:
    logger.error("Error importing exports router: %s", e, exc_info=True)
    exports = None

__all__ = [
    "auth",
    "projects",
    "templates",
    "documents",
    "api_keys",
    "webhooks",
    "usage",
    "notifications",
    "audit",
    "admin",
    "admin_affiliates",
    "admin_coupons",
    "public_api",
    "workspace",
    "billing",
    "affiliates",
    "redirect",
    "template_library",
    "exports",
]
