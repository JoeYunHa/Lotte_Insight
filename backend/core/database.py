from supabase import create_client
from core.config import settings

supabase = create_client(
    settings.supabase_url,
    settings.supabase_service_role_key,  # 배치 작업은 service role 사용
)
