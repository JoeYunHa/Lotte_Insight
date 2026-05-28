from fastapi import FastAPI
from api import articles, fan_voice, fan_voice_review, home, players, reports, topics

app = FastAPI(title="Lotte Insight API")

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
