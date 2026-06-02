import os
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import articles, fan_voice, fan_voice_review, home, players, reports, topics

app = FastAPI(title="Lotte Insight API")

_raw = os.environ.get("ALLOWED_ORIGINS", "https://lotte-insight-frontend.vercel.app")
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in _raw.split(",")],
    allow_methods=["GET", "POST"],
    allow_headers=["*"],
)

app.include_router(reports.router, prefix="/reports")
app.include_router(home.router, prefix="/reports")
app.include_router(players.router, prefix="/players")
app.include_router(articles.router, prefix="/articles")
app.include_router(topics.router, prefix="/topics")
app.include_router(fan_voice.router, prefix="/fan-voice")
app.include_router(fan_voice_review.router, prefix="/fan-voice")


@app.get("/health")
def health():
    return {"status": "ok"}
