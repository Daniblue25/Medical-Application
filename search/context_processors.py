from config.caching import cache_is_full

def cache_state(request):
    return {'CACHE_IS_FULL': cache_is_full()}
