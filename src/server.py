from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from src.app.api.controller import router
from logging import getLogger

logger = getLogger(__name__)


def init_routers(app_: FastAPI) -> None:
    app_.include_router(router, prefix="/api")


def create_app() -> FastAPI:
    app_ = FastAPI(
        title="GenAI Project API",
        description="API para responder perguntas financeiras usando modelos Gemini e uma base de conhecimento personalizada.",
        version="1.0.0",
    )

    app_.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    init_routers(app_=app_)
    return app_


app = create_app()
