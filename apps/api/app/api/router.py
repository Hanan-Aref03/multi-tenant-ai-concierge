"""Top-level route assembly for the backend.

Hanan owns route composition and versioning.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(slots=True, frozen=True)
class RouteSpec:
    """Route manifest entry used to document the API surface."""

    method: str
    path: str
    summary: str
    owner: str
    implemented: bool = True
    tags: tuple[str, ...] = ()
    metadata: dict[str, Any] = field(default_factory=dict)


@dataclass(slots=True)
class RouteCatalog:
    """A declarative API surface map for the platform spine."""

    routes: tuple[RouteSpec, ...]

    def by_owner(self) -> dict[str, tuple[RouteSpec, ...]]:
        grouped: dict[str, list[RouteSpec]] = {}
        for route in self.routes:
            grouped.setdefault(route.owner, []).append(route)
        return {owner: tuple(routes) for owner, routes in grouped.items()}

    def implemented_routes(self) -> tuple[RouteSpec, ...]:
        return tuple(route for route in self.routes if route.implemented)

    def route_paths(self) -> tuple[str, ...]:
        return tuple(route.path for route in self.routes)


def build_route_catalog() -> RouteCatalog:
    """Build the route manifest for the current repo slice."""

    routes = (
        RouteSpec("GET", "/health", "Return service health", "Hanan"),
        RouteSpec("GET", "/ready", "Return readiness state", "Hanan"),
        RouteSpec("POST", "/api/v1/tenants", "Provision a tenant", "Hanan"),
        RouteSpec(
            "POST",
            "/api/v1/tenants/{tenant_id}/members",
            "Invite a tenant member",
            "Hanan",
        ),
        RouteSpec(
            "POST",
            "/api/v1/tenants/{tenant_id}/suspend",
            "Suspend a tenant",
            "Hanan",
        ),
        RouteSpec(
            "DELETE",
            "/api/v1/tenants/{tenant_id}",
            "Erase tenant data",
            "Hanan",
        ),
        RouteSpec(
            "GET",
            "/api/v1/widget/config",
            "Serve widget bootstrap config",
            "Ali Faddel",
            implemented=False,
        ),
        RouteSpec(
            "POST",
            "/api/v1/conversations",
            "Create a tenant conversation",
            "Mohammad",
            implemented=False,
        ),
        RouteSpec(
            "POST",
            "/api/v1/content",
            "Upload tenant knowledge",
            "Mohammad",
            implemented=False,
        ),
    )
    return RouteCatalog(routes=routes)
