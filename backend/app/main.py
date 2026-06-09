from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import auth, chat, files, projects, sources
from app.config import get_settings
from app.core.exceptions import register_exception_handlers
from app.core.logging import configure_logging, get_logger


def create_app() -> FastAPI:
    settings = get_settings()
    configure_logging(settings.log_level)
    logger = get_logger("app")

    app = FastAPI(title="Agentic Research Tool API", version="0.1.0")

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(auth.router, prefix="/api")
    app.include_router(projects.router, prefix="/api")
    app.include_router(files.router, prefix="/api")
    app.include_router(sources.router, prefix="/api")
    app.include_router(chat.router, prefix="/api")

    @app.get("/health", tags=["health"])
    async def health() -> dict[str, str]:
        return {"status": "ok", "env": settings.app_env}

    logger.info("application started in %s mode", settings.app_env)
    return app


app = create_app()
