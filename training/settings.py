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
# Deprecated — classifier_koelectra and summarizer replaced by GPT in Phase 5.
# Referenced only by train_classifier.py and train_summarizer.py which are
# slated for removal after Phase 5-E. Do not use in new code.
MODEL_DIR = ROOT_DIR / "models" / "classifier_koelectra"
SUMMARIZER_MODEL_DIR = ROOT_DIR / "models" / "summarizer_kobart_v2"

LOTTE_RELATED_MODEL_DIR = ROOT_DIR / "models" / "lotte_related_koelectra"

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
    "롯데관전평",
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
        f"{TEAM_FULL_NAME_KO} 응원",
        f"{TEAM_FULL_NAME_KO} 이벤트",
        f"{TEAM_FULL_NAME_KO} 홈경기",
        f"{TEAM_FULL_NAME_KO} 팬서비스",
        f"{TEAM_FULL_NAME_KO} 운영",
        f"{TEAM_FULL_NAME_KO} MD",
        f"사직 구장",
        f"사직 야구장",
        f"부산 야구 팬",
        f"{TEAM_FULL_NAME_KO} 구단주",
        f"{TEAM_FULL_NAME_KO} 스폰서",
        f"{TEAM_FULL_NAME_KO} 후원",
        f"{TEAM_FULL_NAME_KO} 개막",
        f"사직 이벤트",
    ],
    "INTERVIEW": [
        f"{TEAM_FULL_NAME_KO} 감독 인터뷰",
        f"{TEAM_FULL_NAME_KO} 감독 현장",
        f"{TEAM_FULL_NAME_KO} 선수 인터뷰",
        f"{TEAM_FULL_NAME_KO} 인터뷰",
        f"{TEAM_FULL_NAME_KO} 소감",
        f"{TEAM_FULL_NAME_KO} 감독 발언",
        f"{TEAM_FULL_NAME_KO} 일문일답",
        f"{TEAM_FULL_NAME_KO} 밝혔다",
        f"{TEAM_FULL_NAME_KO} 말했다",
        f"{TEAM_FULL_NAME_KO} 각오",
        f"{TEAM_FULL_NAME_KO} 다짐",
        f"{TEAM_FULL_NAME_KO}  인터뷰",
        f"{TEAM_FULL_NAME_KO} 선수 소감",
        f"롯데 감독 기자회견",
        f"롯데 선수 각오",
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
        f"{TEAM_FULL_NAME_KO} 평균자책",
        f"{TEAM_FULL_NAME_KO} 지표",
        f"{TEAM_FULL_NAME_KO} 상승세",
        f"{TEAM_FULL_NAME_KO} 하락세",
        f"{TEAM_FULL_NAME_KO} 반등",
        f"{TEAM_FULL_NAME_KO} 통산 기록",
        f"{TEAM_FULL_NAME_KO} wRC",
        f"{TEAM_FULL_NAME_KO} WAR",
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
        f"{TEAM_FULL_NAME_KO} 연봉",
        f"{TEAM_FULL_NAME_KO} 자유계약",
        f"{TEAM_FULL_NAME_KO} 용병",
        f"{TEAM_FULL_NAME_KO} 보류",
        f"{TEAM_FULL_NAME_KO} 웨이버",
        f"{TEAM_FULL_NAME_KO} 신인",
        f"{TEAM_FULL_NAME_KO} 재계약",
        f"{TEAM_FULL_NAME_KO} 입단",
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
OPENAI_SUMMARY_MAX_TOKENS = 1400

ARTICLE_SNIPPET_LENGTH = 300
COLLECT_REQUEST_SLEEP_SECONDS = 0.3
AUTO_LABEL_SLEEP_SECONDS = 0.15

DEFAULT_LABELING_COUNT = 500
LABEL_MIN_THRESHOLDS: dict[str, float] = {}
FALLBACK_ONLY_LABELS: set[str] = {"ETC"}
DEFAULT_TRAIN_EPOCHS = 5
DEFAULT_TRAIN_LR = 5e-5
DEFAULT_TRAIN_BATCH_SIZE = 16
DEFAULT_EVAL_BATCH_SIZE = 32
DEFAULT_TRAIN_WARMUP_RATIO = 0.1
DEFAULT_TRAIN_SEED = 42
DEFAULT_VALIDATION_SPLIT = 0.15
DEFAULT_MIN_MACRO_F1 = 0.70
DEFAULT_CLASSIFIER_MAX_LENGTH = 256

DEFAULT_LOTTE_RELATED_PRETRAINED = "klue/roberta-large"
DEFAULT_LOTTE_RELATED_EPOCHS = 5
DEFAULT_LOTTE_RELATED_LR = 5e-5
DEFAULT_LOTTE_RELATED_BATCH_SIZE = 16
DEFAULT_LOTTE_RELATED_THRESHOLD = 0.40
LOTTE_RELATED_RECALL_TARGET = 0.97

DEFAULT_SUMMARIZER_PRETRAINED = "digit82/kobart-summarization"
DEFAULT_SUMMARIZER_EPOCHS = 10
DEFAULT_SUMMARIZER_LR = 2e-5
DEFAULT_SUMMARIZER_BATCH_SIZE = 4
DEFAULT_SUMMARIZER_MAX_SOURCE_LEN = 384
DEFAULT_SUMMARIZER_MAX_TARGET_LEN = 256
DEFAULT_SUMMARIZER_NUM_BEAMS = 6
DEFAULT_SUMMARIZER_WEIGHT_DECAY = 0.01
DEFAULT_SUMMARIZER_EARLY_STOPPING_PATIENCE = 2
DEFAULT_SUMMARIZER_LENGTH_PENALTY = 1.2
DEFAULT_SUMMARIZER_NO_REPEAT_NGRAM = 3
DEFAULT_SUMMARIZER_EARLY_STOPPING = True
DEFAULT_SUMMARIZER_GRAD_ACCUMULATION = 2

STANCE_MODEL_DIR = ROOT_DIR / "models" / "stance_koelectra"
DEFAULT_STANCE_PRETRAINED = "monologg/koelectra-small-v3-discriminator"
DEFAULT_STANCE_EPOCHS = 5
DEFAULT_STANCE_LR = 5e-5
DEFAULT_STANCE_BATCH_SIZE = 16
STANCE_LABELS = ["negative", "neutral", "positive"]

PLAYER_STANCE_MODEL_DIR = ROOT_DIR / "models" / "player_stance_koelectra"
DEFAULT_PLAYER_STANCE_PRETRAINED = "monologg/koelectra-small-v3-discriminator"
DEFAULT_PLAYER_STANCE_EPOCHS = 5
DEFAULT_PLAYER_STANCE_LR = 5e-5
DEFAULT_PLAYER_STANCE_BATCH_SIZE = 16
PLAYER_STANCE_LABELS = ["negative", "neutral", "positive"]
