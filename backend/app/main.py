"""Career Quest — FastAPI қосымшасы."""
from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .api import auth, chat, hr, idp, meta, profiles
from .config import get_settings

logging.basicConfig(level=logging.INFO)

app = FastAPI(
    title="Career Quest API",
    description="Қызметкердің дағдыларын талдап, кәсіби даму жолын ұсынатын AI-бағыттаушы",
    version="1.0.0",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in get_settings().cors_origins.split(",") if o.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
for r in (auth.router, meta.router, profiles.router, idp.router, chat.router, hr.router):
    app.include_router(r)
