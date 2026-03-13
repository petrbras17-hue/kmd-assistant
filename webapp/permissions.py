"""
Roles & Permissions system for KMD (S13-3).

Defines role-based access control with:
- Role enum (admin, engineer, viewer)
- Permission constants and role-to-permission mapping
- FastAPI dependencies for route protection
- Middleware for URL-pattern-based permission checks
- Utility helpers for resolving user permissions
"""

from __future__ import annotations

import enum
import logging
import re
from functools import wraps
from typing import TYPE_CHECKING, Any, Callable, Optional, Sequence, Set

from fastapi import Depends, HTTPException, Request, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.responses import Response

from webapp.database import get_db

if TYPE_CHECKING:
    from webapp.models import User

from webapp.auth import get_current_user
from webapp.models import WorkspaceMember

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Role enum
# ---------------------------------------------------------------------------


class Role(str, enum.Enum):
    """User roles ordered by privilege level."""

    ADMIN = "admin"
    ENGINEER = "engineer"
    VIEWER = "viewer"


# ---------------------------------------------------------------------------
# Permission constants
# ---------------------------------------------------------------------------


class Permission(str, enum.Enum):
    """Granular permission constants."""

    UPLOAD = "upload"
    VALIDATE = "validate"
    GENERATE = "generate"
    COMPARE = "compare"
    VIEW_RESULTS = "view_results"
    DOWNLOAD = "download"
    MANAGE_USERS = "manage_users"
    MANAGE_WORKSPACE = "manage_workspace"
    MANAGE_API_KEYS = "manage_api_keys"


# ---------------------------------------------------------------------------
# Role -> Permission mapping
# ---------------------------------------------------------------------------

ROLE_PERMISSIONS: dict[Role, frozenset[Permission]] = {
    Role.ADMIN: frozenset(Permission),  # all permissions
    Role.ENGINEER: frozenset(
        {
            Permission.UPLOAD,
            Permission.VALIDATE,
            Permission.GENERATE,
            Permission.COMPARE,
            Permission.VIEW_RESULTS,
            Permission.DOWNLOAD,
        }
    ),
    Role.VIEWER: frozenset(
        {
            Permission.VIEW_RESULTS,
            Permission.DOWNLOAD,
        }
    ),
}


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------


class RoleSchema(BaseModel):
    """Schema for role information."""

    role: Role
    permissions: list[Permission]


class PermissionCheckResult(BaseModel):
    """Result of a permission check."""

    allowed: bool
    role: Role
    required_permission: Optional[Permission] = None
    message: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _resolve_role(user: Any) -> Role:
    """Extract the Role from a user object, with safe fallback."""
    raw = getattr(user, "role", None)
    if raw is None:
        return Role.VIEWER  # safest default
    if isinstance(raw, Role):
        return raw
    try:
        return Role(raw)
    except ValueError:
        logger.warning("Unknown role %r for user %s — defaulting to viewer", raw, getattr(user, "id", "?"))
        return Role.VIEWER


async def get_user_permissions(
    user: Any,
    workspace_id: Optional[int] = None,
    db: Optional[AsyncSession] = None,
) -> Set[Permission]:
    """Resolve the full set of permissions for *user*.

    When *workspace_id* is supplied (and *db* is available), the workspace-
    level role from ``WorkspaceMember`` takes precedence over the global user
    role.  This enables per-workspace permission overrides.

    Returns a set of ``Permission`` values.
    """
    # Start with the global role.
    role = _resolve_role(user)

    # If a workspace context is given, try to look up a workspace-specific role.
    if workspace_id is not None and db is not None:
        ws_role = await _get_workspace_role(user, workspace_id, db)
        if ws_role is not None:
            role = ws_role

    return set(ROLE_PERMISSIONS.get(role, ROLE_PERMISSIONS[Role.VIEWER]))


async def _get_workspace_role(
    user: Any,
    workspace_id: int,
    db: AsyncSession,
) -> Optional[Role]:
    """Ищет роль пользователя в конкретном workspace."""
    stmt = (
        select(WorkspaceMember.role)
        .where(
            WorkspaceMember.workspace_id == workspace_id,
            WorkspaceMember.user_id == user.id,
        )
    )
    result = await db.execute(stmt)
    row = result.scalar_one_or_none()
    if row is not None:
        try:
            return Role(row)
        except ValueError:
            return None
    return None


# ---------------------------------------------------------------------------
# FastAPI dependencies
# ---------------------------------------------------------------------------


def require_role(*roles: Role) -> Callable:
    """Dependency factory: require the current user to hold one of *roles*.

    Usage::

        @router.get("/admin-only", dependencies=[Depends(require_role(Role.ADMIN))])
        async def admin_only(): ...
    """
    allowed = frozenset(roles)

    async def _dependency(
        user: Any = Depends(get_current_user),
    ) -> Any:
        user_role = _resolve_role(user)
        if user_role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Role '{user_role.value}' is not permitted. "
                    f"Required: {', '.join(r.value for r in allowed)}."
                ),
            )
        return user

    return _dependency


def require_permission(permission: Permission) -> Callable:
    """Dependency factory: require a specific *permission*.

    Usage::

        @router.post("/upload", dependencies=[Depends(require_permission(Permission.UPLOAD))])
        async def upload_file(): ...
    """

    async def _dependency(
        request: Request,
        user: Any = Depends(get_current_user),
        db: AsyncSession = Depends(get_db),
    ) -> Any:
        # Extract workspace_id from path if present.
        workspace_id = _extract_workspace_id(request)
        perms = await get_user_permissions(user, workspace_id=workspace_id, db=db)
        if permission not in perms:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Permission '{permission.value}' is required. "
                    f"Your role ('{_resolve_role(user).value}') does not include it."
                ),
            )
        return user

    return _dependency


async def check_workspace_role(
    workspace_id: int,
    user: Any = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> Role:
    """FastAPI dependency that resolves the user's role within a workspace.

    Raises 403 if the user is not a member of the workspace.

    """
    ws_role = await _get_workspace_role(user, workspace_id, db)
    if ws_role is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Вы не являетесь участником данного рабочего пространства",
        )
    return ws_role


# ---------------------------------------------------------------------------
# URL-pattern -> permission mapping (used by middleware)
# ---------------------------------------------------------------------------

# Each entry is a tuple of (compiled regex, set of required permissions).
# The first matching pattern wins.
_ROUTE_PERMISSION_MAP: list[tuple[re.Pattern[str], set[Permission]]] = [
    # Upload & validate
    (re.compile(r"^/api/upload(/|$)"), {Permission.UPLOAD}),
    (re.compile(r"^/api/validate(/|$)"), {Permission.VALIDATE}),
    # Generate & compare
    (re.compile(r"^/api/generate(/|$)"), {Permission.GENERATE}),
    (re.compile(r"^/api/compare(/|$)"), {Permission.COMPARE}),
    # Results & download (read-only)
    (re.compile(r"^/api/results(/|$)"), {Permission.VIEW_RESULTS}),
    (re.compile(r"^/api/download(/|$)"), {Permission.DOWNLOAD}),
    # Workspace management
    (re.compile(r"^/api/workspaces/\d+/settings(/|$)"), {Permission.MANAGE_WORKSPACE}),
    (re.compile(r"^/api/workspaces/\d+/invite(/|$)"), {Permission.MANAGE_WORKSPACE}),
    # User management
    (re.compile(r"^/api/users(/|$)"), {Permission.MANAGE_USERS}),
    # API key management
    (re.compile(r"^/api/api-keys(/|$)"), {Permission.MANAGE_API_KEYS}),
]

# Paths that should bypass permission checks entirely (health, docs, auth).
_PUBLIC_PATH_PREFIXES: tuple[str, ...] = (
    "/docs",
    "/redoc",
    "/openapi.json",
    "/api/health",
    "/api/auth",
    "/api/login",
    "/api/register",
)


# ---------------------------------------------------------------------------
# Middleware
# ---------------------------------------------------------------------------


class RoleMiddleware(BaseHTTPMiddleware):
    """Intercept requests and enforce permission checks based on URL patterns.

    The middleware reads ``request.state.user`` (set by an upstream auth
    middleware) and checks against ``_ROUTE_PERMISSION_MAP``.  If the user
    lacks the required permission, a **403 Forbidden** JSON response is
    returned before the route handler executes.

    Public paths (docs, health, auth endpoints) skip the check.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: RequestResponseEndpoint,
    ) -> Response:
        path = request.url.path

        # Skip public/unprotected paths.
        if any(path.startswith(prefix) for prefix in _PUBLIC_PATH_PREFIXES):
            return await call_next(request)

        # Determine required permissions for this path.
        required = _match_route_permissions(path)
        if not required:
            # No explicit permission rule — allow through.
            return await call_next(request)

        # Check that user is present on request (set by auth middleware).
        user = getattr(request.state, "user", None)
        if user is None:
            # No authenticated user — let downstream auth handle 401.
            return await call_next(request)

        user_role = _resolve_role(user)
        user_perms = ROLE_PERMISSIONS.get(user_role, ROLE_PERMISSIONS[Role.VIEWER])

        missing = required - user_perms
        if missing:
            detail = (
                f"Forbidden: role '{user_role.value}' lacks permission(s): "
                f"{', '.join(p.value for p in sorted(missing, key=lambda p: p.value))}."
            )
            logger.info(
                "Permission denied for user %s (role=%s) on %s %s — missing: %s",
                getattr(user, "id", "?"),
                user_role.value,
                request.method,
                path,
                ", ".join(p.value for p in missing),
            )
            return JSONResponse(
                status_code=status.HTTP_403_FORBIDDEN,
                content={"detail": detail},
            )

        return await call_next(request)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------


def _match_route_permissions(path: str) -> set[Permission]:
    """Return the set of permissions required for *path*, or empty set."""
    for pattern, perms in _ROUTE_PERMISSION_MAP:
        if pattern.search(path):
            return perms
    return set()


def _extract_workspace_id(request: Request) -> Optional[int]:
    """Try to extract a workspace_id from the request path or query params."""
    # Path: /api/workspaces/{id}/...
    match = re.search(r"/api/workspaces/(\d+)", request.url.path)
    if match:
        return int(match.group(1))

    # Query parameter fallback.
    ws = request.query_params.get("workspace_id")
    if ws is not None:
        try:
            return int(ws)
        except (ValueError, TypeError):
            pass

    return None


# ---------------------------------------------------------------------------
# Route-level permission decorator
# ---------------------------------------------------------------------------


def permissions_required(*perms: Permission) -> Callable:
    """Decorator that annotates a route handler with required permissions.

    This is a convenience wrapper that adds a ``Depends(require_permission(p))``
    for each supplied permission.  Use it when you prefer decorator syntax over
    the ``dependencies=[...]`` argument on the router.

    Usage::

        @router.post("/upload")
        @permissions_required(Permission.UPLOAD)
        async def upload_file(request: Request):
            ...

    Note: Because FastAPI resolves ``Depends`` via its own injection system,
    the decorator injects permission metadata into ``route.__permissions__``
    so that the middleware / docs can introspect requirements.  The actual
    enforcement still happens through the ``require_permission`` dependency
    or the ``RoleMiddleware``.
    """

    def decorator(func: Callable) -> Callable:
        # Attach metadata for introspection.
        func.__permissions__ = set(perms)  # type: ignore[attr-defined]

        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> Any:
            return await func(*args, **kwargs)

        # Preserve the metadata on the wrapper too.
        wrapper.__permissions__ = func.__permissions__  # type: ignore[attr-defined]
        return wrapper

    return decorator


# ---------------------------------------------------------------------------
# Convenience exports
# ---------------------------------------------------------------------------


def role_permissions_summary() -> dict[str, list[str]]:
    """Return a JSON-serialisable summary of role-to-permission mapping.

    Useful for frontend clients to build UI based on the current user's role.
    """
    return {
        role.value: sorted(p.value for p in perms)
        for role, perms in ROLE_PERMISSIONS.items()
    }
