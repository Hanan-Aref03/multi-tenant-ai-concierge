"""API route assembly and versioned endpoints."""

from apps.api.app.api.router import RouteCatalog, RouteSpec, build_route_catalog

__all__ = ["RouteCatalog", "RouteSpec", "build_route_catalog"]
