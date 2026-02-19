"""
Service de recherche batch (multi-requêtes).
Permet de lancer plusieurs recherches en parallèle et de combiner les résultats.
"""

from typing import List, Dict, Tuple
import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from ..services.pubmed_client import search_pubmed, PubMedError
from ..services.cache_manager import CacheManager

logger = logging.getLogger(__name__)


class BatchSearchService:
    """
    Gère les recherches batch (multiples mots-clés à la fois).
    Exécute les recherches en parallèle pour optimiser les performances.
    """
    
    MAX_PARALLEL_SEARCHES = 5  # Limite pour ne pas surcharger PubMed API
    
    @staticmethod
    def process_batch_queries(
        queries: List[Dict],
        max_results_per_query: int = 200,
        use_cache: bool = True
    ) -> Dict:
        """
        Lance plusieurs recherches PubMed en parallèle.
        
        Args:
            queries: Liste de dictionnaires avec paramètres de recherche
                Chaque dict contient: keywords, study_type, journal_rank, time_period
            max_results_per_query: Nombre max d'articles par recherche
            use_cache: Utiliser le cache de base de données
            
        Returns:
            Dict avec résultats groupés par query et statistiques globales
        """
        if not queries:
            return {
                'status': 'error',
                'message': 'No queries provided',
                'results': []
            }
        
        results = []
        total_articles = 0
        cached_count = 0
        errors = []
        
        def execute_single_search(idx: int, query: Dict) -> Tuple[int, Dict]:
            """Exécute une seule recherche (pour ThreadPoolExecutor)."""
            try:
                keywords = query.get('keywords', '').strip()
                study_type = query.get('study_type', '')
                journal_rank = query.get('journal_rank', 'all')
                time_period = query.get('time_period', '10')
                year_from_input = query.get('year_from')
                year_to_input = query.get('year_to')
                
                if not keywords:
                    return (idx, {
                        'query_index': idx,
                        'keywords': '',
                        'status': 'skipped',
                        'message': 'Empty keywords',
                        'articles': [],
                        'count': 0
                    })
                
                # Calculer year_from et year_to
                year_to = year_to_input
                year_from = year_from_input
                if not year_from and not year_to and time_period and time_period.isdigit():
                    from datetime import datetime
                    year_to = datetime.now().year
                    year_from = year_to - int(time_period)
                
                # Vérifier le cache si activé
                from_cache = False
                if use_cache:
                    cached_result = CacheManager.get_cached_results(
                        keywords=keywords,
                        surgery_type=study_type,
                        journal_rank=journal_rank,
                        year_from=year_from,
                        year_to=year_to
                    )
                    
                    if cached_result:
                        articles = cached_result['articles']
                        from_cache = True
                        logger.info(f"Batch [{idx}] Cache HIT: {keywords} - {len(articles)} articles")
                    else:
                        # Recherche PubMed
                        journal_filter = '' if journal_rank == 'a' else 'no_filter'
                        total_count, articles = search_pubmed(
                            term=keywords,
                            start=0,
                            size=min(max_results_per_query, 200),
                            study_type=study_type,
                            time_period=time_period,
                            journal_filter=journal_filter
                        )
                        
                        # Sauvegarder dans le cache
                        if articles:
                            CacheManager.save_to_cache(
                                keywords=keywords,
                                articles=articles,
                                surgery_type=study_type,
                                journal_rank=journal_rank,
                                year_from=year_from,
                                year_to=year_to
                            )
                        
                        logger.info(f"Batch [{idx}] PubMed: {keywords} - {len(articles)} articles")
                else:
                    # Recherche PubMed sans cache
                    if journal_rank == 'a':
                        journal_filter = ''
                    elif journal_rank == 'nurse':
                        journal_filter = 'nurse'
                    else:
                        journal_filter = 'no_filter'
                    
                    total_count, articles = search_pubmed(
                        term=keywords,
                        start=0,
                        size=min(max_results_per_query, 200),
                        study_type=study_type,
                        time_period=time_period if not (year_from or year_to) else '',
                        journal_filter=journal_filter,
                        year_from=year_from,
                        year_to=year_to
                    )
                    logger.info(f"Batch [{idx}] PubMed (no cache): {keywords} - {len(articles)} articles")
                
                return (idx, {
                    'query_index': idx,
                    'keywords': keywords,
                    'study_type': study_type,
                    'journal_rank': journal_rank,
                    'status': 'success',
                    'articles': articles,
                    'count': len(articles),
                    'from_cache': from_cache
                })
                
            except PubMedError as e:
                logger.error(f"Batch [{idx}] PubMed error: {e}")
                return (idx, {
                    'query_index': idx,
                    'keywords': query.get('keywords', ''),
                    'status': 'error',
                    'message': f'PubMed error: {str(e)}',
                    'articles': [],
                    'count': 0
                })
            except Exception as e:
                logger.exception(f"Batch [{idx}] Unexpected error: {e}")
                return (idx, {
                    'query_index': idx,
                    'keywords': query.get('keywords', ''),
                    'status': 'error',
                    'message': f'Error: {str(e)}',
                    'articles': [],
                    'count': 0
                })
        
        # Exécuter les recherches en parallèle
        with ThreadPoolExecutor(max_workers=BatchSearchService.MAX_PARALLEL_SEARCHES) as executor:
            # Lancer toutes les recherches
            futures = {
                executor.submit(execute_single_search, idx, query): idx
                for idx, query in enumerate(queries)
            }
            
            # Collecter les résultats au fur et à mesure
            temp_results = {}
            for future in as_completed(futures):
                idx, result = future.result()
                temp_results[idx] = result
                
                # Comptabiliser
                if result['status'] == 'success':
                    total_articles += result['count']
                    if result.get('from_cache'):
                        cached_count += 1
                else:
                    errors.append({
                        'query_index': idx,
                        'keywords': result['keywords'],
                        'error': result.get('message', 'Unknown error')
                    })
        
        # Réorganiser les résultats dans l'ordre original
        results = [temp_results[i] for i in range(len(queries)) if i in temp_results]
        
        return {
            'status': 'success',
            'total_queries': len(queries),
            'successful_queries': len([r for r in results if r['status'] == 'success']),
            'failed_queries': len(errors),
            'total_articles': total_articles,
            'cached_queries': cached_count,
            'results': results,
            'errors': errors if errors else None
        }
    
    @staticmethod
    def combine_results(batch_result: Dict, dedup_by_pmid: bool = True) -> List[Dict]:
        """
        Combine tous les articles des résultats batch en une seule liste.
        
        Args:
            batch_result: Résultat de process_batch_queries()
            dedup_by_pmid: Dédupliquer les articles par PMID (si un article apparaît dans plusieurs queries)
            
        Returns:
            Liste combinée d'articles
        """
        all_articles = []
        seen_pmids = set()
        
        for result in batch_result.get('results', []):
            if result['status'] != 'success':
                continue
            
            for article in result['articles']:
                pmid = article.get('pmid', '')
                
                if dedup_by_pmid:
                    if pmid and pmid in seen_pmids:
                        continue
                    if pmid:
                        seen_pmids.add(pmid)
                
                # Ajouter metadata de source
                article_with_meta = {
                    **article,
                    'batch_query_index': result['query_index'],
                    'batch_query_keywords': result['keywords']
                }
                all_articles.append(article_with_meta)
        
        return all_articles
