from contextlib import asynccontextmanager

from fastapi import FastAPI

from app import models
from app.auth_routes import router as auth_router
from app.config import get_settings
from app.db import Base, engine


@asynccontextmanager
async def lifespan(_: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(lifespan=lifespan)
    app.state.settings = settings
    app.include_router(auth_router)

    return app

app = create_app()
