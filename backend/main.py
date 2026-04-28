from fastapi import FastAPI
from api import reports, players, articles

app = FastAPI(title="Lotte Insight API")

app.include_router(reports.router, prefix="/reports")
app.include_router(players.router, prefix="/players")
app.include_router(articles.router, prefix="/articles")


@app.get("/health")
def health():
    return {"status": "ok"}
