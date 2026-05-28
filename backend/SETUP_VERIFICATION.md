# 검증 스크립트 실행 가이드

## 🚀 빠른 실행 (Windows)

### 1단계: 가상환경 활성화

```cmd
cd backend
.venv\Scripts\activate
```

가상환경이 활성화되면 터미널에 `(.venv)` 표시가 나타납니다.

### 2단계: 의존성 설치 (최초 1회만)

```cmd
pip install -r requirements.txt
```

⏱️ 약 1~2분 소요됩니다.

### 3단계: 검증 스크립트 실행

```cmd
python -m batch.verify_supabase_setup
```

---

## 🐧 Linux/Mac 사용자

### 1단계: 가상환경 활성화

```bash
cd backend
source .venv/bin/activate
```

### 2단계: 의존성 설치 (최초 1회만)

```bash
pip install -r requirements.txt
```

### 3단계: 검증 스크립트 실행

```bash
python -m batch.verify_supabase_setup
```

---

## ⚠️ 문제 해결

### "No module named 'pydantic_settings'" 에러

**원인**: 의존성 패키지가 설치되지 않음

**해결**:
```cmd
cd backend
pip install -r requirements.txt
```

### "ModuleNotFoundError: No module named 'core'" 에러

**원인**: 잘못된 디렉토리에서 실행

**해결**:
```cmd
# backend 디렉토리에서 실행
cd backend
python -m batch.verify_supabase_setup
```

### 가상환경이 없는 경우

**생성 방법**:
```cmd
cd backend
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

---

## ✅ 예상 출력

성공 시:
```
============================================================
Supabase 설정 검증 시작
============================================================
🔍 환경변수 확인 중...
  ✅ SUPABASE_URL = https://xxx.supabase.co
  ✅ SUPABASE_SERVICE_ROLE_KEY = eyJhbGc...
  ✅ NAVER_CLIENT_ID = xxxx...
  ✅ NAVER_CLIENT_SECRET = xxxx...
  ✅ OPENAI_API_KEY = sk-proj...
🔍 Service Role Key 사용 확인 중...
  ✅ Service Role Key 형식 확인
🔍 테이블 존재 확인 중...
  ✅ players
  ✅ games
  ✅ articles
  ... (생략)
============================================================
검증 결과 요약
============================================================
✅ 모든 검증 통과! Supabase 설정이 완료되었습니다.

다음 단계:
  1. Railway 배포 환경변수 설정
  2. Railway Cron Job 등록
  3. 모델 파일 공급 (Volume or HF Hub)
```

---

## 📝 참고

- 가상환경은 이미 생성되어 있음 (`backend/.venv`)
- 의존성 설치는 최초 1회만 필요
- 이후에는 가상환경 활성화 후 바로 스크립트 실행 가능
