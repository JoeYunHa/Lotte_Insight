from fastapi import FastAPI
from api import articles, home, players, reports, topics

app = FastAPI(title="Lotte Insight API")

app.include_router(reports.router, prefix="/reports")
app.include_router(home.router, prefix="/reports")
app.include_router(players.router, prefix="/players")
app.include_router(articles.router, prefix="/articles")
app.include_router(topics.router, prefix="/topics")


@app.get("/health")
def health():
    return {"status": "ok"}
