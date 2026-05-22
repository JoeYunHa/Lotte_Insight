from __future__ import annotations

_supabase_client = None


class _LazySupabase:
    """supabase 클라이언트를 첫 속성 접근 시점까지 지연 생성한다.

    import 시점 환경변수 검증 실패를 방지하여 pytest collect와 로컬 도구 실행성을 높인다.

    테스트에서 목(mock)을 주입할 때는 반드시 모듈 네임스페이스 단위로 교체해야 한다.
    patch.object(supabase, "table", ...)는 __getattr__ → create_client 를 트리거하므로 사용 금지.
    올바른 패턴: patch.object(target_module, "supabase", mock_client)
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
