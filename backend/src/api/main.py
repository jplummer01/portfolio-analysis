"""FastAPI application entry point."""

import logging

from fastapi import FastAPI

from src.api.routes import analyse, health, ingest, recommend
from src.core.config import settings

logging.basicConfig(level=getattr(logging, settings.log_level.upper(), logging.INFO))

app = FastAPI(
    title="Portfolio Overlap & Fund Analyzer",
    description="Analyses fund portfolio overlap and recommends switch candidates.",
    version="0.1.0",
)

app.include_router(health.router)
app.include_router(ingest.router)
app.include_router(analyse.router)
app.include_router(recommend.router)
