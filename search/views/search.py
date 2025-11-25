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
    max_input = data.get('max_results') or data.get('maxResults') or 20000
    page_input = data.get('page') or data.get('pageNumber') or 1
    page_size_input = data.get('page_size') or data.get('pageSize') or max_input
    try:
        page_size = max(1, min(int(page_size_input), 50000))
    except (TypeError, ValueError):
        page_size = 200
    try:
        max_results = max(1, min(int(max_input), 50000))
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
    
    # Gérer le filtre de rang de revue
    journal_rank = data.get('journalRank', 'all')
    if journal_rank == 'a':
        # Utiliser les 13 revues de rang A
        journal_filter = ''  # Chaîne vide = filtre sur les 13 revues cibles
    else:
        # 'all' = rechercher dans toutes les revues PubMed
        journal_filter = 'no_filter'  # Valeur spéciale pour désactiver le filtre
    
    filters = dict(
        keywords=data.get('keywords', data.get('query', '')),
        study_type=data.get('studyType', ''),
        journal_filter=journal_filter,
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
            time_period=filters['time_period'],
            journal_filter=filters['journal_filter']
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
@api_view(['POST'])
def export_all_results(request):
    """
    Récupère TOUS les résultats d'une recherche pour l'export (pas seulement ceux affichés)
    Fait des requêtes multiples si nécessaire pour contourner la limite de 200 par requête
    """
    data = request.data or {}
    
    # Gérer le filtre de rang de revue
    journal_rank = data.get('journalRank', 'all')
    if journal_rank == 'a':
        # Utiliser les 13 revues de rang A
        journal_filter = ''  # Chaîne vide = filtre sur les 13 revues cibles
    else:
        # 'all' = rechercher dans toutes les revues PubMed
        journal_filter = 'no_filter'  # Valeur spéciale pour désactiver le filtre
    
    # Récupérer les paramètres de recherche originaux
    filters = dict(
        keywords=data.get('keywords', data.get('query', '')),
        study_type=data.get('studyType', ''),
        journal_filter=journal_filter,
        region=data.get('regionFilter', ''),
        time_period=data.get('timePeriod', '10'),
        sample_size=data.get('sampleSize', '')
    )

    keyword = (filters['keywords'] or '').strip()
    
    # Limite d'export pour éviter les timeouts (max 5000 articles)
    MAX_EXPORT = 5000
    BATCH_SIZE = 200  # Limite PubMed par requête
    
    try:
        # Première requête pour connaître le total
        total_available, first_batch = search_pubmed(
            term=keyword,
            start=0,
            size=BATCH_SIZE,
            study_type=filters['study_type'],
            time_period=filters['time_period'],
            journal_filter=filters['journal_filter']
        )
        
        all_articles = first_batch
        logger.info(f"Export: First batch retrieved {len(first_batch)} articles, total available: {total_available}")
        
        # Calculer combien d'articles on peut récupérer au maximum
        articles_to_fetch = min(total_available, MAX_EXPORT)
        
        # Récupérer les articles restants par batch de 200
        if articles_to_fetch > BATCH_SIZE:
            remaining_batches = (articles_to_fetch - BATCH_SIZE + BATCH_SIZE - 1) // BATCH_SIZE
            
            for batch_num in range(1, remaining_batches + 1):
                start_index = batch_num * BATCH_SIZE
                if start_index >= articles_to_fetch:
                    break
                    
                logger.info(f"Export: Fetching batch {batch_num + 1}, starting at {start_index}")
                
                try:
                    _, batch_articles = search_pubmed(
                        term=keyword,
                        start=start_index,
                        size=BATCH_SIZE,
                        study_type=filters['study_type'],
                        time_period=filters['time_period'],
                        journal_filter=filters['journal_filter']
                    )
                    all_articles.extend(batch_articles)
                    logger.info(f"Export: Retrieved {len(batch_articles)} articles in batch {batch_num + 1}")
                except Exception as batch_error:
                    logger.warning(f"Export: Failed to fetch batch {batch_num + 1}: {batch_error}")
                    # Continue avec les articles déjà récupérés
                    break
        
        message = f"Retrieved {len(all_articles)} articles out of {total_available} total for export"
        if articles_to_fetch < total_available:
            message += f" (limited to {MAX_EXPORT} for performance)"
        
        return Response({
            "status": "success",
            "data": all_articles,
            "total": total_available,
            "returned": len(all_articles),
            "source": "pubmed",
            "message": message
        })
    except (PubMedError, requests.RequestException, ValueError) as exc:
        logger.exception("Export all results failed", exc_info=exc)
        return Response({
            "status": "error",
            "message": "Unable to retrieve all results. Please try again later.",
            "error": str(exc)
        }, status=503)

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
