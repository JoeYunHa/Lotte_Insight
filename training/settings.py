import os
from pathlib import Path

try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:
    pass

ROOT_DIR = Path(__file__).resolve().parent
REPO_ROOT = ROOT_DIR.parent
BACKEND_DIR = REPO_ROOT / "backend"
DATA_DIR = ROOT_DIR / "data"
MODEL_DIR = ROOT_DIR / "models" / "classifier_koelectra"
SUMMARIZER_MODEL_DIR = ROOT_DIR / "models" / "summarizer_kobart"

LABELED_TITLES_CSV = DATA_DIR / "labeled_titles.csv"
LABELED_PLAYERS_CSV = DATA_DIR / "labeled_players.csv"
REVIEW_LOTTE_RELATED_CSV = DATA_DIR / "review_lotte_related.csv"
GAME_RESULTS_CSV = DATA_DIR / "game_results.csv"

TEAM_NAME_KO = "롯데"
TEAM_FULL_NAME_KO = "롯데 자이언츠"
TEAM_ALIASES = ("롯데", "자이언츠", "사직", "LT")
TEAM_SEARCH_KEYWORDS = [
    # 기본 팀 검색
    TEAM_FULL_NAME_KO,
    "자이언츠",
    "사직 야구",
    # MATCH_RELATED
    f"{TEAM_FULL_NAME_KO} 경기",
    f"{TEAM_FULL_NAME_KO} 선발",
    f"{TEAM_FULL_NAME_KO} 승리",
    f"{TEAM_FULL_NAME_KO} 패배",
    f"{TEAM_FULL_NAME_KO} 불펜",
    f"{TEAM_FULL_NAME_KO} 홈런",
    # INJURY_ROSTER
    f"{TEAM_FULL_NAME_KO} 부상",
    f"{TEAM_FULL_NAME_KO} 콜업",
    f"{TEAM_FULL_NAME_KO} 엔트리",
    f"{TEAM_FULL_NAME_KO} 재활",
    # TRANSACTION_CONTRACT
    f"{TEAM_FULL_NAME_KO} 트레이드",
    f"{TEAM_FULL_NAME_KO} FA",
    f"{TEAM_FULL_NAME_KO} 계약",
    f"{TEAM_FULL_NAME_KO} 영입",
    # PERFORMANCE_ANALYSIS
    f"{TEAM_FULL_NAME_KO} 성적",
    f"{TEAM_FULL_NAME_KO} 타율",
    f"{TEAM_FULL_NAME_KO} 방어율",
    # INTERVIEW
    f"{TEAM_FULL_NAME_KO} 감독",
    f"{TEAM_FULL_NAME_KO} 인터뷰",
    # CLUB_OPERATION
    f"{TEAM_FULL_NAME_KO} 구단",
    f"{TEAM_FULL_NAME_KO} 팬",
]

FOCUS_LABEL_KEYWORDS = {
    "CLUB_OPERATION": [
        f"{TEAM_FULL_NAME_KO} 구단",
        f"{TEAM_FULL_NAME_KO} 팬",
        f"{TEAM_FULL_NAME_KO} 사직구장",
        f"{TEAM_FULL_NAME_KO} 마케팅",
        f"{TEAM_FULL_NAME_KO} 행사",
        f"{TEAM_FULL_NAME_KO} 티켓",
        f"{TEAM_FULL_NAME_KO} 유니폼",
        f"{TEAM_FULL_NAME_KO} 굿즈",
        f"{TEAM_FULL_NAME_KO} 시구",
    ],
    "INTERVIEW": [
        f"{TEAM_FULL_NAME_KO} 감독 인터뷰",
        f"{TEAM_FULL_NAME_KO} 감독 현장",
        f"{TEAM_FULL_NAME_KO} 선수 인터뷰",
        f"{TEAM_FULL_NAME_KO} 인터뷰",
        f"{TEAM_FULL_NAME_KO} 소감",
        f"{TEAM_FULL_NAME_KO} \"",
    ],
    "PERFORMANCE_ANALYSIS": [
        f"{TEAM_FULL_NAME_KO} 타율",
        f"{TEAM_FULL_NAME_KO} 방어율",
        f"{TEAM_FULL_NAME_KO} OPS",
        f"{TEAM_FULL_NAME_KO} ERA",
        f"{TEAM_FULL_NAME_KO} 성적 분석",
        f"{TEAM_FULL_NAME_KO} 기록",
        f"{TEAM_FULL_NAME_KO} 순위",
        f"{TEAM_FULL_NAME_KO} 부진",
        f"{TEAM_FULL_NAME_KO} 분석",
    ],
    "TRANSACTION_CONTRACT": [
        f"{TEAM_FULL_NAME_KO} FA",
        f"{TEAM_FULL_NAME_KO} 트레이드",
        f"{TEAM_FULL_NAME_KO} 계약",
        f"{TEAM_FULL_NAME_KO} 영입",
        f"{TEAM_FULL_NAME_KO} 방출",
        f"{TEAM_FULL_NAME_KO} 외국인",
        f"{TEAM_FULL_NAME_KO} 드래프트",
        f"{TEAM_FULL_NAME_KO} 이적",
    ],
}

NAVER_CLIENT_ID = os.getenv("NAVER_CLIENT_ID", "")
NAVER_CLIENT_SECRET = os.getenv("NAVER_CLIENT_SECRET", "")
NAVER_SEARCH_URL = "https://openapi.naver.com/v1/search/news.json"
NAVER_DISPLAY_LIMIT = 100
NAVER_MAX_START = 1000  # 네이버 API start 파라미터 상한

OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TIMEOUT_SECONDS = 20
OPENAI_TEMPERATURE = 0.0
OPENAI_LABEL_BATCH_SIZE = 8
OPENAI_LABEL_MAX_WORKERS = 4
OPENAI_LABEL_MAX_TOKENS = 500
OPENAI_SUMMARY_BATCH_SIZE = 8
OPENAI_SUMMARY_MAX_WORKERS = 4
OPENAI_SUMMARY_MAX_TOKENS = 700

ARTICLE_SNIPPET_LENGTH = 300
COLLECT_REQUEST_SLEEP_SECONDS = 0.3
AUTO_LABEL_SLEEP_SECONDS = 0.15

DEFAULT_LABELING_COUNT = 500
DEFAULT_TRAIN_EPOCHS = 5
DEFAULT_TRAIN_LR = 5e-5
DEFAULT_TRAIN_BATCH_SIZE = 16
DEFAULT_EVAL_BATCH_SIZE = 32
DEFAULT_TRAIN_WARMUP_RATIO = 0.1
DEFAULT_TRAIN_SEED = 42
DEFAULT_VALIDATION_SPLIT = 0.15
DEFAULT_MIN_MACRO_F1 = 0.70

DEFAULT_SUMMARIZER_PRETRAINED = "gogamza/kobart-base-v2"
DEFAULT_SUMMARIZER_EPOCHS = 5
DEFAULT_SUMMARIZER_LR = 3e-5
DEFAULT_SUMMARIZER_BATCH_SIZE = 8
DEFAULT_SUMMARIZER_MAX_SOURCE_LEN = 256
DEFAULT_SUMMARIZER_MAX_TARGET_LEN = 192
DEFAULT_SUMMARIZER_NUM_BEAMS = 4
DEFAULT_SUMMARIZER_WEIGHT_DECAY = 0.01
DEFAULT_SUMMARIZER_EARLY_STOPPING_PATIENCE = 2
