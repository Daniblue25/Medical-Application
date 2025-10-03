from rest_framework.decorators import api_view
from rest_framework.response import Response
from django.core.cache import cache
from django.views.decorators.csrf import csrf_exempt
from config.caching import register_cache_key
from ..services.pubmed_client import search_pubmed, PubMedError
import math
import logging
import requests


logger = logging.getLogger(__name__)

@csrf_exempt
@api_view(['POST'])
def search_api(request):
    data = request.data or {}
    max_input = data.get('max_results') or data.get('maxResults') or 200
    page_input = data.get('page') or data.get('pageNumber') or 1
    page_size_input = data.get('page_size') or data.get('pageSize') or max_input
    try:
        page_size = max(1, min(int(page_size_input), 20000))
    except (TypeError, ValueError):
        page_size = 200
    try:
        max_results = max(1, min(int(max_input), 20000))
    except (TypeError, ValueError):
        max_results = 20000
    try:
        page = max(1, int(page_input))
    except (TypeError, ValueError):
        page = 1

    cache_key = f"search:{hash(frozenset({**data, 'page': page, 'page_size': page_size}.items()))}"
    cached = cache.get(cache_key)
    if cached:
        return Response({"status": "success", "cached": True, **cached})
    
    filters = dict(
        keywords=data.get('keywords', data.get('query', '')),
        study_type=data.get('studyType', ''),
        journal_quality=data.get('journalQuality', ''),
        region=data.get('regionFilter', ''),
        time_period=data.get('timePeriod', '10'),
        sample_size=data.get('sampleSize', '')
    )

    keyword = (filters['keywords'] or '').strip()
    
    try:
        # Toujours utiliser PubMed - si pas de keyword, recherche générale
        start_index = (page - 1) * min(page_size, 200)
        total_count, articles = search_pubmed(
            term=keyword,  # Vide = recherche par défaut "medicine[MeSH Terms]"
            start=start_index,
            size=min(page_size, 200),
            study_type=filters['study_type'],
            time_period=filters['time_period']
        )
        total_available = min(total_count, max_results)
        effective_page_size = min(page_size, max_results, 200)
        page_count = max(1, math.ceil(total_available / effective_page_size))
        payload = {
            "data": articles,
            "total": total_available,
            "returned": len(articles),
            "page": page,
            "page_size": effective_page_size,
            "page_count": page_count,
            "source": "pubmed",
            "message": f"PubMed returned {total_available} articles (page {page}/{page_count})"
        }
    except (PubMedError, requests.RequestException, ValueError) as exc:
        logger.exception("PubMed search failed", exc_info=exc)
        return Response({
            "status": "error",
            "message": "PubMed API is currently unavailable. Please try again later.",
            "error": str(exc)
        }, status=503)
    
    cache.set(cache_key, payload, 60 * 15)
    register_cache_key(cache_key)
    return Response({"status": "success", **payload})

@csrf_exempt
@api_view(['GET', 'POST'])
def sample_api(request):
    """
    Retourne un échantillon aléatoire d'articles PubMed récents
    """
    try:
        # Recherche aléatoire d'articles médicaux récents
        total_count, articles = search_pubmed(
            term="medicine[MeSH Terms]",
            start=0,
            size=20,
            time_period="5"  # 5 dernières années
        )
        return Response({
            "status": "success",
            "data": articles,
            "total": len(articles),
            "source": "pubmed"
        })
    except (PubMedError, requests.RequestException, ValueError) as exc:
        logger.exception("PubMed sample failed", exc_info=exc)
        return Response({
            "status": "error",
            "message": "PubMed API is currently unavailable.",
            "error": str(exc)
        }, status=503)
