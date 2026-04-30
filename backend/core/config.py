from pathlib import Path

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    supabase_url: str
    supabase_anon_key: str
    supabase_service_role_key: str
    naver_client_id: str
    naver_client_secret: str
    openai_api_key: str
    openai_model: str = "gpt-4o-mini"
    crawl_user_agent: str = "LotteInsightBot/1.0"
    kbo_crawl_interval_hours: int = 2
    team_code: str = "LT"
    team_name_ko: str = "롯데"
    article_keyword_limit: int = 20
    article_description_snippet_length: int = 120
    report_recent_days: int = 7
    player_report_article_limit: int = 10
    player_stats_history_limit: int = 30
    report_list_limit: int = 30
    player_report_max_tokens: int = 400
    player_report_temperature: float = 0.3
    app_env: str = "development"
    log_level: str = "INFO"

    class Config:
        env_file = str(Path(__file__).resolve().parents[2] / ".env")


settings = Settings()
