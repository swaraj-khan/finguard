from functools import lru_cache

from supabase import Client, create_client

from . import config


@lru_cache
def get_supabase() -> Client:
    return create_client(config.SUPABASE_URL, config.SUPABASE_SERVICE_ROLE_KEY)
