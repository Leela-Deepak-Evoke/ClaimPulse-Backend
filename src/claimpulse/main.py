from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse

from claimpulse.api import auth, claims, dashboard, health, lookups, patients, payers, users
from claimpulse.config import get_settings
from claimpulse.errors import register_error_handlers
from claimpulse.observability import configure_logging, request_id_middleware


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    app = FastAPI(
        title="ClaimPulse API",
        version="0.1.0",
        description="ClaimPulse backend API",
    )
    register_error_handlers(app)
    app.middleware("http")(request_id_middleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    for module in (health, auth, users, payers, patients, claims, dashboard, lookups):
        app.include_router(module.router)

    @app.get("/", include_in_schema=False)
    def root() -> RedirectResponse:
        return RedirectResponse(url="/docs")

    return app


app = create_app()
