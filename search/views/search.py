"""
Medical Search Platform - Search Views
Copyright (c) 2025 DRCI - CHU Clermont-Ferrand
All rights reserved.

Author: FIANKO Kossi Jean-Jacques Daniel
License: MIT License (see LICENSE file)
"""

from rest_framework.decorators import api_view
from rest_framework.response import Response
from ..services.pubmed_client import search_pubmed, PubMedError
from ..services.cache_manager import CacheManager
import math
import logging
import requests


logger = logging.getLogger(__name__)

@api_view(['POST'])
def search_api(request):
    data = request.data or {}
    max_input = data.get('max_results') or data.get('maxResults') or 100000
    page_input = data.get('page') or data.get('pageNumber') or 1
    page_size_input = data.get('page_size') or data.get('pageSize') or max_input
    try:
        page_size = max(1, min(int(page_size_input), 200000))
    except (TypeError, ValueError):
        page_size = 200
    try:
        max_results = max(1, min(int(max_input), 100000))
    except (TypeError, ValueError):
        max_results = 100000
    try:
        page = max(1, int(page_input))
    except (TypeError, ValueError):
        page = 1

    # Gérer le filtre de rang de revue
    journal_rank = data.get('journalRank', 'all')
    if journal_rank == 'a':
        journal_filter = ''  # Chaîne vide = filtre sur les 13 revues cibles
    elif journal_rank == 'nurse':
        journal_filter = 'nurse'
    else:
        journal_filter = 'no_filter'  # 'all' = toutes les revues PubMed
    
    # Gérer le filtre de période - support des années personnalisées
    year_from_input = data.get('yearFrom')
    year_to_input = data.get('yearTo')
    
    filters = {
        'keywords': data.get('keywords', data.get('query', '')),
        'study_type': data.get('studyType', ''),
        'journal_filter': journal_filter,
        'region': data.get('regionFilter', ''),
        'time_period': data.get('timePeriod', '10'),
        'year_from': year_from_input,
        'year_to': year_to_input,
        'sample_size': data.get('sampleSize', '')
    }

    keyword = (filters['keywords'] or '').strip()

    try:
        # --- Smart Cache: check if results are already cached ---
        cached = CacheManager.get_cached_results(
            keywords=keyword,
            surgery_type=filters['study_type'] if isinstance(filters['study_type'], str) else ','.join(filters['study_type']),
            journal_rank=data.get('journalRank', 'all'),
            year_from=filters['year_from'],
            year_to=filters['year_to'],
        )
        
        if cached:
            # Cache frais: retourner les articles du cache
            all_cached = cached['articles']
            total_available = len(all_cached)
            effective_page_size = min(page_size, 200)
            start_idx = (page - 1) * effective_page_size
            end_idx = start_idx + effective_page_size
            page_articles = all_cached[start_idx:end_idx]
            page_count = max(1, math.ceil(total_available / effective_page_size))
            
            return Response({
                "status": "success",
                "data": page_articles,
                "total": total_available,
                "total_on_pubmed": total_available,
                "returned": len(page_articles),
                "page": page,
                "page_size": effective_page_size,
                "page_count": page_count,
                "source": "cache",
                "cache_age_days": cached.get('cache_age_days', 0),
                "message": f"Returned {len(page_articles)} cached articles (page {page}/{page_count}, cache age: {cached.get('cache_age_days', 0)}d)"
            })

        # --- Cache miss or expired: query PubMed ---
        start_index = (page - 1) * min(page_size, 200)
        # Convertir study_type en string si c'est une liste
        study_type_value = filters['study_type']
        if isinstance(study_type_value, list):
            study_type_value = ','.join(study_type_value) if study_type_value else ''
        
        total_count, articles = search_pubmed(
            term=keyword,
            start=start_index,
            size=min(page_size, 200),
            study_type=study_type_value or '',
            time_period=filters['time_period'] or '',
            journal_filter=filters['journal_filter'] or '',
            year_from=filters['year_from'],
            year_to=filters['year_to']
        )
        
        # Sauvegarder/fusionner dans le cache (incrémental)
        if articles and keyword:
            try:
                new_count = CacheManager.merge_into_cache(
                    keywords=keyword,
                    new_articles=articles,
                    surgery_type=study_type_value or '',
                    journal_rank=data.get('journalRank', 'all'),
                    year_from=filters['year_from'],
                    year_to=filters['year_to'],
                )
                if new_count > 0:
                    logger.info(f"Cache: {new_count} new articles merged for '{keyword}'")
            except Exception as cache_err:
                logger.warning(f"Cache save failed (non-blocking): {cache_err}")

        total_available = min(total_count, max_results)
        effective_page_size = min(page_size, max_results, 200)
        page_count = max(1, math.ceil(total_available / effective_page_size))
        
        payload = {
            "data": articles,
            "total": total_available,
            "total_on_pubmed": total_count,  # Total réel trouvé sur PubMed (avant limite maxResults)
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
    
    return Response({"status": "success", **payload})

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
        journal_filter = ''  # Chaîne vide = filtre sur les 13 revues cibles
    elif journal_rank == 'nurse':
        journal_filter = 'nurse'
    else:
        journal_filter = 'no_filter'  # 'all' = toutes les revues PubMed
    
    # Gérer le filtre de période - support des années personnalisées
    year_from_input = data.get('yearFrom')
    year_to_input = data.get('yearTo')
    
    # Récupérer les paramètres de recherche originaux
    filters = dict(
        keywords=data.get('keywords', data.get('query', '')),
        study_type=data.get('studyType', ''),
        journal_filter=journal_filter,
        region=data.get('regionFilter', ''),
        time_period=data.get('timePeriod', '10'),
        year_from=year_from_input,
        year_to=year_to_input,
        sample_size=data.get('sampleSize', '')
    )

    keyword = (filters['keywords'] or '').strip()
    
    # Limite d'export pour éviter les timeouts (max 5000 articles)
    MAX_EXPORT = 5000
    BATCH_SIZE = 200  # Limite PubMed par requête
    
    try:
        # Première requête pour connaître le total
        # Convertir study_type en string si c'est une liste
        study_type_value = filters['study_type']
        if isinstance(study_type_value, list):
            study_type_value = ','.join(study_type_value) if study_type_value else ''
        
        total_available, first_batch = search_pubmed(
            term=keyword,
            start=0,
            size=BATCH_SIZE,
            study_type=study_type_value or '',
            time_period=filters['time_period'] or '',
            journal_filter=filters['journal_filter'] or '',
            year_from=filters['year_from'],
            year_to=filters['year_to']
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
                        study_type=study_type_value or '',
                        time_period=filters['time_period'] or '',
                        journal_filter=filters['journal_filter'] or '',
                        year_from=filters['year_from'],
                        year_to=filters['year_to']
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


@api_view(['POST'])
def batch_search_api(request):
    """
    Recherche batch: lance plusieurs recherches PubMed en parallèle.
    Accepte un array de queries et retourne les résultats groupés.
    
    Body: {
        "queries": [
            {
                "keywords": "liver resection",
                "study_type": "hepatic",
                "journal_rank": "a",
                "time_period": "10"
            },
            {
                "keywords": "pancreatic surgery outcomes",
                "study_type": "pancreatic",
                "journal_rank": "all",
                "time_period": "5"
            }
        ],
        "max_results_per_query": 200,
        "combine": true,  // Optionnel: combiner tous les résultats
        "dedup": true     // Optionnel: dédupliquer par PMID
    }
    """
    from ..services.batch_search import BatchSearchService
    
    data = request.data or {}
    queries = data.get('queries', [])
    max_results = data.get('max_results_per_query', 200)
    combine = data.get('combine', False)
    dedup = data.get('dedup', True)
    
    if not queries:
        return Response({
            "status": "error",
            "message": "No queries provided. Expected 'queries' array in request body."
        }, status=400)
    
    if len(queries) > 10:
        return Response({
            "status": "error",
            "message": "Maximum 10 queries allowed per batch request."
        }, status=400)
    
    try:
        # Lancer les recherches batch
        logger.info(f"Batch search: {len(queries)} queries")
        batch_result = BatchSearchService.process_batch_queries(
            queries=queries,
            max_results_per_query=max_results,
            use_cache=True
        )
        
        if combine:
            # Mode combiné: retourner une seule liste d'articles
            combined_articles = BatchSearchService.combine_results(batch_result, dedup_by_pmid=dedup)
            
            return Response({
                "status": "success",
                "mode": "combined",
                "total_queries": batch_result['total_queries'],
                "successful_queries": batch_result['successful_queries'],
                "total_articles": len(combined_articles),
                "cached_queries": batch_result.get('cached_queries', 0),
                "data": combined_articles,
                "errors": batch_result.get('errors')
            })
        else:
            # Mode groupé: retourner les résultats par query
            return Response({
                "status": "success",
                "mode": "grouped",
                **batch_result
            })
    
    except Exception as exc:
        logger.exception("Batch search failed", exc_info=exc)
        return Response({
            "status": "error",
            "message": "Batch search failed. Please try again.",
            "error": str(exc)
        }, status=500)

