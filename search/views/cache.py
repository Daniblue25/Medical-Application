from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.views.decorators.csrf import csrf_exempt
from config.caching import clear_search_cache, cache_is_full
from django.core.cache import cache

@csrf_exempt
@api_view(['POST'])
def clear_cache(request):
    removed = clear_search_cache()
    return Response({'status': 'success', 'removed': removed})

@api_view(['GET'])
def cache_status(request):
    keys_set = cache.get('search_cache_keys', set())
    return Response({'full': cache_is_full(), 'count': len(keys_set)})
