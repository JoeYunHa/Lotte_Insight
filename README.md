# Lotte Insight

> 2026 KBO 롯데 자이언츠 팬을 위한 AI 기반 뉴스 인사이트 서비스

![Status](https://img.shields.io/badge/status-production--ready-green)
![Tests](https://img.shields.io/badge/tests-260%20backend%20%2B%2034%20frontend-passing)
![Phase](https://img.shields.io/badge/phase-4%20deployment-blue)

## 📖 개요

Lotte Insight는 롯데 자이언츠 관련 뉴스를 자동으로 수집·분류·요약하여 팬들에게 맞춤형 인사이트를 제공하는 서비스입니다.

**핵심 특징:**
- 🤖 AI 기반 기사 분류 및 요약 (KoELECTRA + GPT-4o mini)
- 📰 다중 소스 뉴스 수집 (Naver API + 5개 RSS 피드)
- 📊 선수별 성적 추적 및 일일 리포트
- 🗺️ 토픽맵 시각화 (클러스터링 + 2D 임베딩)
- 💬 팬 오피니언 수집 및 감정 분석
- ⚡ 실시간 SSE 스트리밍

**준수 원칙:**
- 📄 기사 본문 미저장 (메타데이터 + AI 요약만 제공)
- 🔗 원문 링크 제공으로 저작권 존중
- 🪶 경량 인프라 및 저비용 운영

---

## 🚀 빠른 시작

### 사전 요구사항

- Python 3.11+
- Node.js 18+
- Supabase 계정
- Redis 인스턴스
- OpenAI API 키
- Naver Search API 키

### 1. 저장소 클론

```bash
git clone https://github.com/your-org/lotte-insight.git
cd lotte-insight
```

### 2. 백엔드 설정

```bash
cd backend
python -m venv .venv
source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 환경 변수 설정
cp .env.example .env
# .env 파일 편집하여 API 키 입력
```

### 3. 프론트엔드 설정

```bash
cd frontend
npm install

# 환경 변수 설정
cp .env.local.example .env.local
# .env.local 파일 편집
```

### 4. 데이터베이스 마이그레이션

Supabase 대시보드에서 `supabase/migrations/` 폴더의 SQL 파일들을 순서대로 실행:

```bash
# 총 13개 마이그레이션 파일 실행
01_initial_schema.sql
02_add_article_labels.sql
...
13_fan_voice_review_rpc.sql
```

### 5. 개발 서버 실행

**백엔드:**
```bash
cd backend
uvicorn main:app --reload --port 8000
```

**프론트엔드:**
```bash
cd frontend
npm run dev
```

브라우저에서 `http://localhost:3000` 접속

---

## 🏗️ 기술 스택

| 영역 | 기술 |
|------|------|
| **Frontend** | Next.js 16 (App Router), TypeScript, Tailwind CSS |
| **Backend** | FastAPI (Python), Uvicorn |
| **Database** | Supabase (PostgreSQL) |
| **Cache** | Redis |
| **AI/ML** | KoELECTRA (분류), GPT-4o mini (요약), UMAP (차원 축소) |
| **Data Sources** | Naver Search API, RSS Feeds (5 sources) |
| **Hosting** | Vercel (Frontend), Railway (Backend + Cron) |
| **Testing** | pytest (Backend), Vitest (Frontend) |

---

## 📂 프로젝트 구조

```
lotte-insight/
├── backend/                 # FastAPI 백엔드
│   ├── api/                # REST API 엔드포인트
│   ├── batch/              # 배치 작업 (뉴스 수집, 리포트 생성)
│   ├── core/               # 핵심 설정 (DB, 캐시, 부트스트랩)
│   ├── models/             # AI 모델 (KoELECTRA 분류기)
│   ├── services/           # 비즈니스 로직
│   └── tests/              # 260개 테스트
├── frontend/               # Next.js 프론트엔드
│   ├── app/                # Next.js App Router 페이지
│   ├── components/         # React 컴포넌트
│   │   ├── FanVoice/      # 팬 오피니언 UI
│   │   ├── Page/          # 페이지 레이아웃
│   │   ├── Player/        # 선수 카드
│   │   └── Topic/         # 토픽맵 시각화
│   ├── lib/                # 유틸리티 (API, 타입 정의)
│   └── __tests__/          # 34개 테스트
├── training/               # AI 모델 학습
│   ├── colab/             # Colab 노트북
│   ├── collect/           # 데이터 수집 및 라벨링
│   ├── train/             # 모델 학습 스크립트
│   ├── models/            # 학습된 모델 (KoELECTRA × 4)
│   └── data/              # 학습 데이터
├── supabase/
│   └── migrations/        # 13개 DB 마이그레이션
└── docs/                  # 프로젝트 문서
```

---

## 🎯 주요 기능

### 1. 뉴스 수집 및 분류
- **다중 소스 수집**: Naver Search API + 5개 RSS 피드
- **AI 분류**: 7개 라벨 (경기, 부상, 계약, 인터뷰, 성적 분석 등)
- **롯데 관련성 필터링**: 규칙 기반 + KoELECTRA 모델
- **스탠스 분석**: 긍정/중립/부정 3단계 감정 분석

### 2. 선수 추적
- **공식 KBO 데이터 크롤링**: 로스터, 성적, 경기 결과
- **선수별 일일 리포트**: 최신 기사 + 성적 스냅샷 + GPT 인사이트
- **멘션 추적**: 기사에서 선수 이름 자동 감지 및 스탠스 분석

### 3. 토픽맵 시각화
- **임베딩 기반 클러스터링**: KoELECTRA mean pooling + Agglomerative clustering
- **2D 투영**: UMAP을 이용한 시각화
- **인터랙티브 탐색**: 클릭으로 클러스터 상세 정보 확인

### 4. 팬 오피니언 리뷰 (NEW)
- **의견 수집**: 경기별 팬 반응 수집 (속도 제한 + 필터링)
- **클러스터링**: Jaccard 유사도 기반 의견 그룹화
- **감정 분석**: 감정별 랭킹 (언급 횟수 + 반응 수)
- **선수 랭킹**: 선수별 팬 반응 집계

### 5. 일일 리포트
- **팀 리포트**: 주요 이슈 요약, 라벨 분포, 핵심 선수
- **선수 리포트**: GPT 생성 인사이트 + 최근 기사 + 성적

---

## 🧪 테스트

**백엔드 (260개 테스트):**
```bash
cd backend
pytest -v
```

**프론트엔드 (34개 테스트):**
```bash
cd frontend
npm test
```

**전체 테스트 현황:**
- ✅ 260 backend tests passing (2 skipped)
- ✅ 34 frontend tests passing
- ✅ 100% 핵심 기능 커버리지

---

## 📚 문서

- **[CLAUDE.md](./CLAUDE.md)** - 전체 프로젝트 문서 (아키텍처, 데이터 파이프라인, 배포 가이드)
- **[DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md)** - 프로덕션 배포 체크리스트
- **[DATA_POLICY.md](./DATA_POLICY.md)** - 데이터 수집 및 사용 정책
- **[LEGAL_NOTICE.md](./LEGAL_NOTICE.md)** - 법적 고지 및 준수 사항
- **[backend/batch/RSS_FEEDS_GUIDE.md](./backend/batch/RSS_FEEDS_GUIDE.md)** - RSS 피드 통합 가이드
- **[training/collect/LABELING_GUIDE.md](./training/collect/LABELING_GUIDE.md)** - 모델 학습 가이드
- **[training/train/TRAINING_PROCESS.md](./training/train/TRAINING_PROCESS.md)** - 학습 워크플로우

---

## 🔐 환경 변수

### Backend (.env)
```bash
# Supabase
SUPABASE_URL=https://your-project.supabase.co
SUPABASE_ANON_KEY=your-anon-key
SUPABASE_SERVICE_ROLE_KEY=your-service-role-key

# Naver API
NAVER_CLIENT_ID=your-client-id
NAVER_CLIENT_SECRET=your-client-secret

# OpenAI
OPENAI_API_KEY=your-openai-key
OPENAI_MODEL=gpt-4o-mini

# Redis
REDIS_URL=redis://localhost:6379

# Model Paths (학습된 모델 디렉토리)
CLASSIFIER_MODEL_DIR=/app/models/classifier_koelectra
LOTTE_RELATED_MODEL_DIR=/app/models/lotte_related_koelectra
STANCE_CLASSIFIER_MODEL_DIR=/app/models/stance_koelectra
PLAYER_STANCE_CLASSIFIER_MODEL_DIR=/app/models/player_stance_koelectra
```

### Frontend (.env.local)
```bash
NEXT_PUBLIC_API_URL=http://localhost:8000
```

---

## 🚀 배포

### Vercel (Frontend)
```bash
cd frontend
vercel --prod
```

### Railway (Backend)
```bash
cd backend
railway up
```

**Cron Jobs 설정:**
- `news_collector.py` - 매시간 뉴스 수집
- `topic_clusterer.py` - 매일 04:00 토픽맵 생성
- `report_generator.py` - 매일 05:00 리포트 생성
- `fan_voice_review_generator.py` - 매일 06:00 팬 오피니언 리뷰 생성

상세 배포 가이드는 [DEPLOYMENT_CHECKLIST.md](./DEPLOYMENT_CHECKLIST.md) 참조

---

## 🧠 AI 모델 성능

| 모델 | 작업 | F1 Score | 입력 |
|------|------|----------|------|
| Article Classifier | 다중 라벨 분류 | 0.6331 | 제목 + 설명 |
| is_lotte_related | 관련성 필터 | 0.9779 | 규칙 + 모델 |
| lotte_stance | 팀 스탠스 3단계 | 0.6946 | 제목 + 설명 |
| player_stance | 선수 스탠스 3단계 | 0.7171 | 제목 + 선수 + 요약 |

**기반 모델:** monologg/koelectra-small-v3-discriminator

---

## 📊 현재 상태

**Phase 4 - Production Deployment Preparation**

✅ **완료된 기능:**
- 전체 데이터 파이프라인 (수집, 분류, 요약)
- Backend API + Redis 캐싱
- Frontend UI (토픽맵 통합)
- Fan Voice 오피니언 리뷰 (Phase A~E 완료)
- 모든 모델 학습 및 테스트 완료
- 260 백엔드 + 34 프론트엔드 테스트 통과
- 13개 DB 마이그레이션 완료
- 코드 품질 개선 (Critical 3 + Important 4 이슈 해결)

⏳ **배포 대기 중:**
- Vercel 프론트엔드 배포
- Railway 백엔드 + Cron 작업 배포
- 모델 파일 프로비저닝
- Redis 플러그인 구성

---

## 📄 라이선스

이 프로젝트는 교육 및 개인 사용 목적으로 개발되었습니다.

**중요 사항:**
- 기사 본문을 저장하거나 제공하지 않음
- 메타데이터 + AI 생성 요약만 저장
- 원본 소스로의 링크 제공
- KBO 및 뉴스 소스의 robots.txt 준수

자세한 내용은 [DATA_POLICY.md](./DATA_POLICY.md) 및 [LEGAL_NOTICE.md](./LEGAL_NOTICE.md) 참조

---

## 🤝 기여

이 프로젝트는 현재 개인 프로젝트입니다. 버그 리포트나 제안은 Issues를 통해 공유해 주세요.

---

## 📞 문의

프로젝트 관련 문의사항이 있으시면 Issues 탭을 이용해 주세요.

---

**Last Updated:** 2026-05-28
**Status:** Production-ready, awaiting deployment 🚀
