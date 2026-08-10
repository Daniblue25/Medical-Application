from django.conf import settings
from django.core.cache import cache

CACHE_KEYS_SET = 'search_cache_keys'
CACHE_COUNT_KEY = 'search_cache_count'

def cache_is_full() -> bool:
    threshold = int(getattr(settings, 'CACHE_THRESHOLD', 50))
    count = cache.get(CACHE_COUNT_KEY, 0)
    return count >= threshold

def clear_search_cache():
    keys = cache.get(CACHE_KEYS_SET, set())
    for key in keys:
        cache.delete(key)
    cache.delete(CACHE_KEYS_SET)
    cache.delete(CACHE_COUNT_KEY)
    return len(keys)
