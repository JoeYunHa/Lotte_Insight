from __future__ import annotations

_supabase_client = None


class _LazySupabase:
    """supabase 클라이언트를 첫 속성 접근 시점까지 지연 생성한다.

    import 시점 환경변수 검증 실패를 방지하여 pytest collect와 로컬 도구 실행성을 높인다.
    patch.object(supabase, "table", ...) 패턴도 정상 동작한다 (인스턴스 __dict__ 우선 탐색).
    """

    def __getattr__(self, name: str):
        global _supabase_client
        if _supabase_client is None:
            from supabase import create_client
            from core.config import settings
            _supabase_client = create_client(
                settings.supabase_url,
                settings.supabase_service_role_key,
            )
        return getattr(_supabase_client, name)


supabase = _LazySupabase()
