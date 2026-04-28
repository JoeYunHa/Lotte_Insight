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
    app_env: str = "development"
    log_level: str = "INFO"

    class Config:
        env_file = "../.env"


settings = Settings()
