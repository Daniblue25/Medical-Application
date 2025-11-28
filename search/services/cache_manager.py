"""
Service de gestion du cache des recherches PubMed.
Gère la logique de cache intelligent pour éviter les requêtes répétitives.
"""

from django.utils import timezone
from search.models import SearchCache, CachedArticle
from typing import List, Dict, Optional
import logging

logger = logging.getLogger(__name__)


class CacheManager:
    """
    Gestionnaire de cache pour les recherches PubMed.
    Implémente une stratégie de cache intelligent avec mise à jour incrémentale.
    """
    
    DEFAULT_CACHE_DAYS = 7  # Cache valide pendant 7 jours
    
    @staticmethod
    def get_cached_results(keywords: str, surgery_type: str = '', journal_rank: str = 'all',
                          year_from: Optional[int] = None, year_to: Optional[int] = None,
                          max_age_days: int = DEFAULT_CACHE_DAYS) -> Optional[Dict]:
        """
        Récupère les résultats depuis le cache s'ils existent et sont récents.
        
        Returns:
            Dict avec 'articles' et 'from_cache' si trouvé et frais, None sinon
        """
        query_hash = SearchCache.generate_hash(keywords, surgery_type, journal_rank, year_from, year_to)
        
        try:
            cache_entry = SearchCache.objects.get(query_hash=query_hash)
            
            if cache_entry.is_fresh(max_age_days):
                # Cache frais, retourner les articles
                articles = list(cache_entry.cached_articles.all().values(
                    'pmid', 'title', 'authors', 'journal', 'publication_date', 'year',
                    'abstract', 'doi', 'study_type', 'sample_size', 'region', 
                    'quality', 'participants', 'outcomes'
                ))
                
                logger.info(f"Cache HIT: {keywords} - {len(articles)} articles (age: {(timezone.now() - cache_entry.last_updated).days} days)")
                
                return {
                    'articles': articles,
                    'from_cache': True,
                    'cache_age_days': (timezone.now() - cache_entry.last_updated).days,
                    'last_updated': cache_entry.last_updated.isoformat()
                }
            else:
                logger.info(f"Cache EXPIRED: {keywords} (age: {(timezone.now() - cache_entry.last_updated).days} days)")
                return None
                
        except SearchCache.DoesNotExist:
            logger.info(f"Cache MISS: {keywords}")
            return None
    
    @staticmethod
    def save_to_cache(keywords: str, articles: List[Dict], surgery_type: str = '', 
                     journal_rank: str = 'all', year_from: Optional[int] = None, 
                     year_to: Optional[int] = None) -> SearchCache:
        """
        Sauvegarde les résultats de recherche dans le cache.
        Crée ou met à jour l'entrée de cache et les articles associés.
        
        Args:
            keywords: Mots-clés de recherche
            articles: Liste des articles PubMed (format dict)
            surgery_type: Type de chirurgie
            journal_rank: Rang des revues ('a' ou 'all')
            year_from: Année de début
            year_to: Année de fin
            
        Returns:
            L'objet SearchCache créé ou mis à jour
        """
        query_hash = SearchCache.generate_hash(keywords, surgery_type, journal_rank, year_from, year_to)
        
        # Créer ou mettre à jour l'entrée de cache
        cache_entry, created = SearchCache.objects.update_or_create(
            query_hash=query_hash,
            defaults={
                'keywords': keywords,
                'surgery_type': surgery_type,
                'journal_rank': journal_rank,
                'year_from': year_from,
                'year_to': year_to,
                'article_count': len(articles)
            }
        )
        
        if not created:
            # Si mise à jour, supprimer les anciens articles
            cache_entry.cached_articles.all().delete()
        
        # Sauvegarder les nouveaux articles
        cached_articles = []
        for article in articles:
            cached_article = CachedArticle(
                search_cache=cache_entry,
                pmid=article.get('pmid', ''),
                title=article.get('title', ''),
                authors=article.get('authors', ''),
                journal=article.get('journal', ''),
                publication_date=article.get('publicationDate', ''),
                year=article.get('year', 0),
                abstract=article.get('abstract', ''),
                doi=article.get('doi', ''),
                study_type=article.get('studyType', ''),
                sample_size=article.get('sampleSize'),
                region=article.get('region', ''),
                quality=article.get('quality', ''),
                participants=article.get('participants', ''),
                outcomes=article.get('outcomes', '')
            )
            cached_articles.append(cached_article)
        
        # Bulk create pour optimisation
        if cached_articles:
            CachedArticle.objects.bulk_create(cached_articles, batch_size=100)
        
        action = "Created" if created else "Updated"
        logger.info(f"Cache {action}: {keywords} - {len(articles)} articles saved")
        
        return cache_entry
    
    @staticmethod
    def get_cache_stats() -> Dict:
        """
        Retourne des statistiques sur le cache.
        Utile pour monitoring et debugging.
        """
        total_searches = SearchCache.objects.count()
        total_articles = CachedArticle.objects.count()
        fresh_searches = SearchCache.objects.filter(
            last_updated__gte=timezone.now() - timezone.timedelta(days=CacheManager.DEFAULT_CACHE_DAYS)
        ).count()
        
        return {
            'total_searches': total_searches,
            'total_articles': total_articles,
            'fresh_searches': fresh_searches,
            'stale_searches': total_searches - fresh_searches
        }
    
    @staticmethod
    def clear_old_cache(days_old: int = 30) -> int:
        """
        Supprime les entrées de cache plus anciennes que le nombre de jours spécifié.
        
        Args:
            days_old: Nombre de jours après lesquels le cache est considéré comme obsolète
            
        Returns:
            Nombre d'entrées supprimées
        """
        cutoff_date = timezone.now() - timezone.timedelta(days=days_old)
        old_entries = SearchCache.objects.filter(last_updated__lt=cutoff_date)
        count = old_entries.count()
        old_entries.delete()
        
        logger.info(f"Cleared {count} cache entries older than {days_old} days")
        return count
