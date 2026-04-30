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

LABELED_TITLES_CSV = DATA_DIR / "labeled_titles.csv"
LABELED_PLAYERS_CSV = DATA_DIR / "labeled_players.csv"
REVIEW_LOTTE_RELATED_CSV = DATA_DIR / "review_lotte_related.csv"

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
    "PLAYER_RELATED": [
        f"{TEAM_FULL_NAME_KO} 선수",
        f"{TEAM_FULL_NAME_KO} 유망주",
        f"{TEAM_FULL_NAME_KO} 베테랑",
        f"{TEAM_FULL_NAME_KO} 타자",
        f"{TEAM_FULL_NAME_KO} 투수",
        f"{TEAM_FULL_NAME_KO} 포수",
        f"{TEAM_FULL_NAME_KO} 주장",
        f"{TEAM_FULL_NAME_KO} 성장",
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

ARTICLE_SNIPPET_LENGTH = 120
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
