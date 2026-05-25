"""FastAPI application entry point — Concierge backend."""
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import admin, chat, widget
from app.middleware.cors_dynamic import DynamicCORSMiddleware

WIDGET_DIST = Path(__file__).parent.parent.parent / "widget" / "dist"
WIDGET_PUBLIC = Path(__file__).parent.parent.parent / "widget" / "public"


@asynccontextmanager
async def lifespan(app: FastAPI):  # type: ignore[type-arg]
    yield


app = FastAPI(title="Concierge API", lifespan=lifespan)

# Dynamic CORS middleware — reads allowed_origins from DB per request
app.add_middleware(DynamicCORSMiddleware)

# Routers
app.include_router(widget.router)
app.include_router(chat.router)
app.include_router(admin.router)


@app.get("/health")
async def health() -> dict:
    return {"status": "ok"}


@app.get("/widget.js", include_in_schema=False)
async def serve_loader() -> FileResponse:
    """Serve the widget loader script with long cache headers."""
    loader = WIDGET_PUBLIC / "loader.js"
    return FileResponse(
        loader,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=604800, immutable"},
    )


# Serve widget dist (iframe content) — mounted after routes so /widget.js wins
if WIDGET_DIST.exists():
    app.mount("/widget", StaticFiles(directory=str(WIDGET_DIST), html=True), name="widget")
