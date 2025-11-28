from django.db import models
from django.utils import timezone
import hashlib
import json


class SearchCache(models.Model):
    """
    Cache des recherches PubMed pour éviter les requêtes répétitives.
    Stocke les paramètres de recherche et la date de dernière mise à jour.
    """
    query_hash = models.CharField(max_length=64, unique=True, db_index=True)
    keywords = models.TextField()
    surgery_type = models.CharField(max_length=100, blank=True)
    journal_rank = models.CharField(max_length=10, default='all')
    year_from = models.IntegerField(null=True, blank=True)
    year_to = models.IntegerField(null=True, blank=True)
    last_updated = models.DateTimeField(auto_now=True)
    article_count = models.IntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-last_updated']
        verbose_name = 'Search Cache'
        verbose_name_plural = 'Search Caches'
    
    @staticmethod
    def generate_hash(keywords, surgery_type='', journal_rank='all', year_from=None, year_to=None):
        """Génère un hash unique pour identifier une recherche."""
        params = {
            'keywords': keywords.lower().strip(),
            'surgery_type': surgery_type,
            'journal_rank': journal_rank,
            'year_from': year_from,
            'year_to': year_to
        }
        params_str = json.dumps(params, sort_keys=True)
        return hashlib.sha256(params_str.encode()).hexdigest()
    
    def is_fresh(self, max_age_days=7):
        """Vérifie si le cache est encore frais (< max_age_days)."""
        age = timezone.now() - self.last_updated
        return age.days < max_age_days
    
    def __str__(self):
        return f"{self.keywords[:50]} ({self.article_count} articles)"


class CachedArticle(models.Model):
    """
    Articles PubMed mis en cache localement.
    Relation avec SearchCache pour retrouver rapidement les résultats.
    """
    search_cache = models.ForeignKey(SearchCache, on_delete=models.CASCADE, related_name='cached_articles')
    pmid = models.CharField(max_length=32, db_index=True)
    title = models.TextField()
    authors = models.TextField()
    journal = models.CharField(max_length=255)
    publication_date = models.CharField(max_length=50)
    year = models.IntegerField()
    abstract = models.TextField(blank=True)
    doi = models.CharField(max_length=100, blank=True)
    
    # Champs extraits par LLM (peuvent être null si pas encore traités)
    study_type = models.CharField(max_length=100, blank=True)
    sample_size = models.IntegerField(null=True, blank=True)
    region = models.CharField(max_length=100, blank=True)
    quality = models.CharField(max_length=10, blank=True)
    participants = models.TextField(blank=True)
    outcomes = models.TextField(blank=True)
    
    # Métadonnées
    added_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-year', '-publication_date']
        unique_together = ['search_cache', 'pmid']
        verbose_name = 'Cached Article'
        verbose_name_plural = 'Cached Articles'
    
    def to_dict(self):
        """Convertit l'article en dictionnaire pour l'API."""
        return {
            'pmid': self.pmid,
            'title': self.title,
            'authors': self.authors,
            'journal': self.journal,
            'publicationDate': self.publication_date,
            'year': self.year,
            'abstract': self.abstract,
            'doi': self.doi,
            'studyType': self.study_type,
            'sampleSize': self.sample_size,
            'region': self.region,
            'quality': self.quality,
            'participants': self.participants,
            'outcomes': self.outcomes
        }
    
    def __str__(self):
        return f"[{self.pmid}] {self.title[:60]}"


class Article(models.Model):
    """
    Modèle legacy - conservé pour compatibilité.
    Utiliser CachedArticle pour les nouvelles fonctionnalités.
    """
    pmid = models.CharField(max_length=32, unique=True)
    title = models.TextField()
    authors = models.TextField()
    journal = models.CharField(max_length=255)
    year = models.IntegerField()
    quality = models.CharField(max_length=10)
    study_type = models.CharField(max_length=100)
    sample_size = models.IntegerField(default=0)
    region = models.CharField(max_length=100, blank=True)
    abstract = models.TextField(blank=True)

    def __str__(self):
        return f"{self.title[:60]}..."
