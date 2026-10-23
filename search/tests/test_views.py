"""
Unit tests for API views.
Tests search_api, sample_api, export_all_results, batch_search_api, and health endpoints.
"""
import pytest
from django.test import TestCase, RequestFactory, override_settings
from rest_framework.test import APIClient
from unittest.mock import patch, MagicMock
from search.views.search import search_api, sample_api, export_all_results
from search.services.cache_manager import CacheManager
from search.models import SearchCache, CachedArticle


# Disable rate limiting middleware during tests
TEST_MIDDLEWARE = [
    mw for mw in [
        'django.middleware.security.SecurityMiddleware',
        'whitenoise.middleware.WhiteNoiseMiddleware',
        'django.contrib.sessions.middleware.SessionMiddleware',
        'django.middleware.common.CommonMiddleware',
        'django.middleware.csrf.CsrfViewMiddleware',
        'django.contrib.auth.middleware.AuthenticationMiddleware',
        'django.contrib.messages.middleware.MessageMiddleware',
        'django.middleware.clickjacking.XFrameOptionsMiddleware',
    ]
]


@pytest.mark.django_db
@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class TestSearchAPI(TestCase):
    """Tests for the main search endpoint."""

    def setUp(self):
        self.client = APIClient()

    @patch('search.views.search.search_pubmed')
    def test_search_returns_200(self, mock_pubmed):
        mock_pubmed.return_value = (5, [
            {'pmid': '123', 'title': 'Test Article', 'authors': 'Smith J', 'journal': 'NEJM',
             'year': 2024, 'abstract': 'Test abstract', 'doi': '10.1000/test', 'quality': '',
             'study_type': 'RCT', 'sample_size': 100, 'region': 'north_america',
             'country': 'usa', 'keywords': [], 'mesh_terms': []}
        ])
        response = self.client.post('/api/search/', {
            'keywords': 'liver resection',
            'journalRank': 'all'
        }, format='json')
        assert response.status_code == 200
        assert response.data['status'] == 'success'

    @patch('search.views.search.search_pubmed')
    def test_search_with_journal_filter_a(self, mock_pubmed):
        mock_pubmed.return_value = (1, [
            {'pmid': '456', 'title': 'Surgery Article', 'authors': 'Doe J', 'journal': 'Annals of Surgery',
             'year': 2023, 'abstract': '', 'doi': '', 'quality': '', 'study_type': '',
             'sample_size': None, 'region': '', 'country': '', 'keywords': [], 'mesh_terms': []}
        ])
        response = self.client.post('/api/search/', {
            'keywords': 'pancreatic surgery',
            'journalRank': 'a'
        }, format='json')
        assert response.status_code == 200
        # Verify journal_filter was '' (for A-rank journals)
        call_kwargs = mock_pubmed.call_args.kwargs
        assert call_kwargs['journal_filter'] == ''

    @patch('search.views.search.search_pubmed')
    def test_search_empty_keyword(self, mock_pubmed):
        mock_pubmed.return_value = (0, [])
        response = self.client.post('/api/search/', {
            'keywords': '',
        }, format='json')
        assert response.status_code == 200

    @patch('search.views.search.search_pubmed')
    def test_search_pubmed_error_returns_503(self, mock_pubmed):
        from search.services.pubmed_client import PubMedError
        mock_pubmed.side_effect = PubMedError("API down")
        response = self.client.post('/api/search/', {
            'keywords': 'test',
        }, format='json')
        assert response.status_code == 503
        assert response.data['status'] == 'error'


@pytest.mark.django_db
@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class TestCacheIntegration(TestCase):
    """Tests for cache integration in search."""

    def setUp(self):
        self.client = APIClient()

    @patch('search.views.search.search_pubmed')
    def test_results_are_cached(self, mock_pubmed):
        """First search should hit PubMed and cache results."""
        articles = [
            {'pmid': '100', 'title': 'Cached Article', 'authors': 'A B', 'journal': 'Test',
             'year': 2024, 'abstract': 'Abstract', 'doi': '', 'quality': '', 'study_type': 'RCT',
             'sample_size': 50, 'region': '', 'country': '', 'keywords': [], 'mesh_terms': [],
             'publicationDate': '2024-01-01'}
        ]
        mock_pubmed.return_value = (1, articles)
        response = self.client.post('/api/search/', {
            'keywords': 'unique_cache_test_keyword',
            'journalRank': 'all'
        }, format='json')
        assert response.status_code == 200
        # Verify cache was populated
        assert SearchCache.objects.filter(keywords='unique_cache_test_keyword').exists()

    @patch('search.views.search.search_pubmed')
    def test_cached_results_returned(self, mock_pubmed):
        """Second identical search should return cached results."""
        # Pre-populate cache
        CacheManager.save_to_cache(
            keywords='cached_keyword',
            articles=[
                {'pmid': '200', 'title': 'Pre-cached', 'authors': 'X Y', 'journal': 'J',
                 'publicationDate': '2024', 'year': 2024, 'abstract': 'A', 'doi': '',
                 'studyType': 'RCT', 'sampleSize': 10, 'region': '', 'quality': '',
                 'participants': '', 'outcomes': ''}
            ],
            journal_rank='all'
        )
        response = self.client.post('/api/search/', {
            'keywords': 'cached_keyword',
            'journalRank': 'all'
        }, format='json')
        assert response.status_code == 200
        assert response.data['source'] == 'cache'
        # PubMed should NOT have been called
        mock_pubmed.assert_not_called()


@pytest.mark.django_db
@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class TestSampleAPI(TestCase):
    """Tests for sample endpoint."""

    def setUp(self):
        self.client = APIClient()

    @patch('search.views.search.search_pubmed')
    def test_sample_returns_articles(self, mock_pubmed):
        mock_pubmed.return_value = (1, [
            {'pmid': '999', 'title': 'Sample', 'authors': 'A', 'journal': 'J',
             'year': 2024, 'abstract': '', 'doi': '', 'quality': '', 'study_type': '',
             'sample_size': None, 'region': '', 'country': '', 'keywords': [], 'mesh_terms': []}
        ])
        response = self.client.get('/api/sample/')
        assert response.status_code == 200
        assert response.data['status'] == 'success'


@pytest.mark.django_db
@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class TestBatchSearchAPI(TestCase):
    """Tests for batch search endpoint."""

    def setUp(self):
        self.client = APIClient()

    def test_batch_no_queries_returns_400(self):
        response = self.client.post('/api/batch-search/', {
            'queries': []
        }, format='json')
        assert response.status_code == 400

    def test_batch_too_many_queries_returns_400(self):
        queries = [{'keywords': f'test{i}'} for i in range(11)]
        response = self.client.post('/api/batch-search/', {
            'queries': queries
        }, format='json')
        assert response.status_code == 400

    @patch('search.services.batch_search.search_pubmed')
    def test_batch_basic(self, mock_pubmed):
        mock_pubmed.return_value = (1, [
            {'pmid': '111', 'title': 'Batch Test', 'authors': 'B C', 'journal': 'J',
             'year': 2024, 'abstract': '', 'doi': '', 'quality': '', 'study_type': '',
             'sample_size': None, 'region': '', 'country': '', 'keywords': [], 'mesh_terms': []}
        ])
        response = self.client.post('/api/batch-search/', {
            'queries': [{'keywords': 'liver surgery'}]
        }, format='json')
        assert response.status_code == 200


@pytest.mark.django_db
class TestCacheManager(TestCase):
    """Tests for CacheManager service."""

    def test_save_and_retrieve(self):
        articles = [
            {'pmid': '500', 'title': 'Cache Test', 'authors': 'T', 'journal': 'J',
             'publicationDate': '2024', 'year': 2024, 'abstract': 'A', 'doi': '',
             'studyType': 'RCT', 'sampleSize': 50, 'region': 'europe', 'quality': 'high',
             'participants': '50', 'outcomes': 'survival'}
        ]
        CacheManager.save_to_cache('test_keyword', articles)
        result = CacheManager.get_cached_results('test_keyword')
        assert result is not None
        assert result['from_cache'] is True
        assert len(result['articles']) == 1

    def test_merge_new_articles(self):
        # Save initial articles
        CacheManager.save_to_cache('merge_test', [
            {'pmid': 'A1', 'title': 'First', 'authors': '', 'journal': '', 'publicationDate': '',
             'year': 2024, 'abstract': '', 'doi': '', 'studyType': '', 'sampleSize': None,
             'region': '', 'quality': '', 'participants': '', 'outcomes': ''}
        ])
        # Merge with one new + one duplicate
        new_count = CacheManager.merge_into_cache('merge_test', [
            {'pmid': 'A1', 'title': 'First (dup)', 'authors': '', 'journal': '', 'publicationDate': '',
             'year': 2024, 'abstract': '', 'doi': '', 'studyType': '', 'sampleSize': None,
             'region': '', 'quality': '', 'participants': '', 'outcomes': ''},
            {'pmid': 'A2', 'title': 'Second (new)', 'authors': '', 'journal': '', 'publicationDate': '',
             'year': 2024, 'abstract': '', 'doi': '', 'studyType': '', 'sampleSize': None,
             'region': '', 'quality': '', 'participants': '', 'outcomes': ''}
        ])
        assert new_count == 1
        # Verify total is 2
        result = CacheManager.get_cached_results('merge_test')
        assert len(result['articles']) == 2

    def test_cache_miss(self):
        result = CacheManager.get_cached_results('nonexistent_keyword')
        assert result is None

    def test_get_cached_pmids(self):
        CacheManager.save_to_cache('pmid_test', [
            {'pmid': 'P1', 'title': '', 'authors': '', 'journal': '', 'publicationDate': '',
             'year': 2024, 'abstract': '', 'doi': '', 'studyType': '', 'sampleSize': None,
             'region': '', 'quality': '', 'participants': '', 'outcomes': ''},
            {'pmid': 'P2', 'title': '', 'authors': '', 'journal': '', 'publicationDate': '',
             'year': 2024, 'abstract': '', 'doi': '', 'studyType': '', 'sampleSize': None,
             'region': '', 'quality': '', 'participants': '', 'outcomes': ''}
        ])
        pmids = CacheManager.get_cached_pmids('pmid_test')
        assert pmids == {'P1', 'P2'}

    def test_cache_stats(self):
        stats = CacheManager.get_cache_stats()
        assert 'total_searches' in stats
        assert 'total_articles' in stats

    def test_clear_old_cache(self):
        count = CacheManager.clear_old_cache(days_old=0)
        assert isinstance(count, int)


@pytest.mark.django_db
@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class TestHealthEndpoint(TestCase):
    """Tests for health check endpoint."""

    def setUp(self):
        self.client = APIClient()

    def test_health_returns_200(self):
        response = self.client.get('/health/')
        assert response.status_code == 200
        import json
        data = json.loads(response.content)
        assert data['status'] == 'ok'


@pytest.mark.django_db
@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class TestSearchPageAssets(TestCase):
    """Ensure the main page does not depend on blocked external CDNs."""

    def setUp(self):
        self.client = APIClient()

    def test_search_page_uses_local_tailwind_asset(self):
        response = self.client.get('/')

        assert response.status_code == 200
        content = response.content.decode('utf-8')
        assert "static/vendor/tailwind.js" in content
        assert "cdn.tailwindcss.com" not in content
        assert "cdnjs.cloudflare.com" not in content
        assert "fonts.googleapis.com" not in content
