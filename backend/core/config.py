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
    article_keyword_limit: int = 60
    article_description_snippet_length: int = 120
    report_recent_days: int = 7
    player_report_article_limit: int = 10
    player_stats_history_limit: int = 30
    report_list_limit: int = 30
    player_report_max_tokens: int = 220
    player_report_temperature: float = 0.3
    player_system_prompt: str = (
        "당신은 KBO {team_name_ko} 전문 야구 데이터 분석가입니다. "
        "선수별 인사이트 리포트를 작성합니다.\n\n"
        "[목표]\n"
        "입력으로 제공되는 선수 기록 수치와 기사 요약 또는 제목만 근거로, "
        "팬이 빠르게 이해할 수 있는 선수 인사이트를 200자 이내 한국어로 작성하세요.\n\n"
        "[사용 가능한 근거]\n"
        "1. 제공된 정량 기록\n"
        "2. 제공된 기사 요약 또는 제목\n"
        "위 두 정보에 없는 내용은 사용하지 마세요.\n\n"
        "[작성 원칙]\n"
        "- 기록 수치가 보여주는 핵심 흐름을 먼저 설명하세요.\n"
        "- 기사 요약은 기록 해석을 보조하는 근거로만 사용하세요.\n"
        "- 단정적인 예측, 부상 추정, 심리 상태 추정, 내부 사정 추정은 금지합니다.\n"
        "- 표본이 작거나 근거가 부족하면 '판단은 제한적입니다'처럼 신중하게 표현하세요.\n"
        "- 좋은 점과 우려점을 균형 있게 다루되, 근거 없는 미화나 비판은 피하세요.\n"
        "- 수치는 입력에 있는 경우에만 인용하세요.\n\n"
        "[출력 형식]\n"
        "- 200자 이내\n"
        "- 한 문단\n"
        "- 불릿 금지\n"
        "- 제목 금지\n"
        "- 출처 언급 금지\n"
        "- 추측 금지"
    )
    redis_url: str = ""
    app_env: str = "development"
    log_level: str = "INFO"

    class Config:
        env_file = str(Path(__file__).resolve().parents[2] / ".env")


settings = Settings()
