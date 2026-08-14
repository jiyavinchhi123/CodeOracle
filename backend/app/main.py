from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.dependencies import get_storage
from app.api.routes import router
from app.config import get_settings
from app.services.startup import recover_jobs_on_startup


@asynccontextmanager
async def lifespan(app: FastAPI):
    settings = get_settings()
    settings.upload_path.mkdir(parents=True, exist_ok=True)
    storage = get_storage()
    await recover_jobs_on_startup(storage, settings)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title="CodeOracle",
        description="AI-powered legacy codebase analyzer and modernizer",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(router)
    return app


app = create_app()
