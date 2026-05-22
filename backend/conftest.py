import os
import sys

sys.path.insert(0, os.path.dirname(__file__))

# Dummy credentials so Settings() validates in test environments without a .env file.
# os.environ.setdefault preserves real values if already set.
for _k, _v in {
    "SUPABASE_URL": "https://test.supabase.co",
    "SUPABASE_ANON_KEY": "test-anon-key",
    "SUPABASE_SERVICE_ROLE_KEY": "test-service-key",
    "NAVER_CLIENT_ID": "test-naver-id",
    "NAVER_CLIENT_SECRET": "test-naver-secret",
    "OPENAI_API_KEY": "sk-test",
}.items():
    os.environ.setdefault(_k, _v)
