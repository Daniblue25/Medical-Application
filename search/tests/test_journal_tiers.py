"""
Tests for the Surgery journal groups (High / Medium Impact Factor) of the Journal filter.
"""
import re

import pytest
from django.test import TestCase, override_settings
from rest_framework.test import APIClient
from unittest.mock import patch

from search.models import SearchCache
from search.services.cache_manager import CacheManager
from search.services.journal_config import (
    ALL_TARGET_JOURNALS, SURGERY_JOURNAL_TIERS, build_surgery_journal_filter,
    get_surgery_tier, normalize_surgery_tiers, resolve_journal_rank,
)
from search.services.pubmed_client import _build_query
from search.tests.test_views import TEST_MIDDLEWARE


def _journals_in(query):
    return re.findall(r'"([^"]+)"\[Journal\]', query)


class TestTierConfig:
    def test_tier_sizes(self):
        assert len(SURGERY_JOURNAL_TIERS['high']['journals']) == 24   # 23 journals + Arch Surg (former JAMA Surg title)
        assert len(SURGERY_JOURNAL_TIERS['medium']['journals']) == 18

    def test_no_journal_in_both_tiers(self):
        high = {a for a, _ in SURGERY_JOURNAL_TIERS['high']['journals']}
        medium = {a for a, _ in SURGERY_JOURNAL_TIERS['medium']['journals']}
        assert not high & medium

    @pytest.mark.parametrize("tiers,expected", [
        (None, ['high', 'medium']),
        ([], ['high', 'medium']),
        (['medium'], ['medium']),
        (['medium', 'high'], ['high', 'medium']),
        ('high', ['high']),
        ('medium, HIGH', ['high', 'medium']),
        (['bogus'], ['high', 'medium']),
    ])
    def test_normalize(self, tiers, expected):
        assert normalize_surgery_tiers(tiers) == expected

    @pytest.mark.parametrize("abbrev,tier", [
        ('Ann Surg', 'high'), ('JAMA Surg', 'high'), ('Arch Surg', 'high'), ('N Engl J Med', 'high'),
        ('Surgery', 'medium'), ('Ann Surg Oncol', 'medium'), ('BJS Open', 'medium'), ('HPB (Oxford)', 'medium'),
        ('ann surg', 'high'), ('Nature', ''), ('', ''), (None, ''),
    ])
    def test_get_surgery_tier(self, abbrev, tier):
        assert get_surgery_tier(abbrev) == tier


class TestTierFilter:
    def test_high_only(self):
        journals = _journals_in(build_surgery_journal_filter(['high']))
        assert len(journals) == 24
        assert 'Ann Surg' in journals and 'Ann Oncol' in journals
        assert 'Surgery' not in journals and 'Ann Surg Oncol' not in journals

    def test_medium_only(self):
        journals = _journals_in(build_surgery_journal_filter(['medium']))
        assert len(journals) == 18
        assert 'Surgery' in journals and 'Ann Surg' not in journals

    def test_both(self):
        query = build_surgery_journal_filter(['high', 'medium'])
        assert len(_journals_in(query)) == 42
        assert query.startswith('(') and query.endswith(')')

    def test_build_query_uses_tiers(self):
        query = _build_query(term="liver resection", journal_filter="surgery:medium")
        journals = _journals_in(query)
        assert len(journals) == 18
        assert "liver resection" in query

    def test_legacy_13_journal_filter_unchanged(self):
        """journal_filter='' keeps the 13 journals covered by the PubMed retrieval validation."""
        journals = _journals_in(_build_query(term="surgery", journal_filter=""))
        assert journals == ALL_TARGET_JOURNALS


class TestResolveJournalRank:
    @pytest.mark.parametrize("rank,tiers,expected", [
        ('surgery', ['high', 'medium'], ('surgery:high+medium', 'surg_hm')),
        ('surgery', ['high'], ('surgery:high', 'surg_h')),
        ('surgery', ['medium'], ('surgery:medium', 'surg_m')),
        ('surgery', None, ('surgery:high+medium', 'surg_hm')),
        ('a', None, ('', 'a')),
        ('nurse', ['high'], ('nurse', 'nurse')),
        ('all', None, ('no_filter', 'all')),
        (None, None, ('no_filter', 'all')),
    ])
    def test_mapping(self, rank, tiers, expected):
        assert resolve_journal_rank(rank, tiers) == expected

    def test_cache_key_fits_model_field(self):
        max_len = SearchCache._meta.get_field('journal_rank').max_length
        for rank, tiers in [('surgery', ['high', 'medium']), ('nurse', None), ('all', None), ('a', None)]:
            assert len(resolve_journal_rank(rank, tiers)[1]) <= max_len


def _article(pmid='1'):
    return {'pmid': pmid, 'title': 'T', 'authors': 'A B', 'journal': 'Annals of surgery', 'year': 2024,
            'abstract': 'Abstract', 'doi': '', 'quality': '', 'study_type': '', 'sample_size': None,
            'region': '', 'country': '', 'keywords': [], 'mesh_terms': []}


@pytest.mark.django_db
@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class TestViewsWithTiers(TestCase):
    def setUp(self):
        self.client = APIClient()

    @patch('search.views.search.search_pubmed')
    def test_search_passes_tier_filter_and_cache_key(self, mock_pubmed):
        mock_pubmed.return_value = (1, [_article()])
        response = self.client.post('/api/search/', {
            'keywords': 'tier_test_kw', 'journalRank': 'surgery', 'journalTiers': ['medium'],
        }, format='json')
        assert response.status_code == 200
        assert mock_pubmed.call_args.kwargs['journal_filter'] == 'surgery:medium'
        assert SearchCache.objects.get(keywords='tier_test_kw').journal_rank == 'surg_m'

    @patch('search.views.search.search_pubmed')
    def test_other_tier_selection_is_not_served_from_cache(self, mock_pubmed):
        mock_pubmed.return_value = (1, [_article()])
        for tiers in (['medium'], ['high']):
            self.client.post('/api/search/', {
                'keywords': 'tier_cache_kw', 'journalRank': 'surgery', 'journalTiers': tiers,
            }, format='json')
        assert mock_pubmed.call_count == 2

    @patch('search.views.search.search_pubmed')
    def test_legacy_rank_a_still_uses_13_journals(self, mock_pubmed):
        mock_pubmed.return_value = (0, [])
        self.client.post('/api/search/', {'keywords': 'legacy', 'journalRank': 'a'}, format='json')
        assert mock_pubmed.call_args.kwargs['journal_filter'] == ''

    @patch('search.views.search.search_pubmed')
    def test_max_results_capped_at_100000(self, mock_pubmed):
        mock_pubmed.return_value = (250000, [_article()])
        response = self.client.post('/api/search/', {
            'keywords': 'cap_test', 'journalRank': 'all', 'maxResults': 200000,
        }, format='json')
        assert response.data['total'] == 100000

    @patch('search.views.search.search_pubmed')
    def test_export_all_passes_tier_filter(self, mock_pubmed):
        mock_pubmed.return_value = (1, [_article()])
        self.client.post('/api/export-all/', {
            'keywords': 'x', 'journalRank': 'surgery', 'journalTiers': ['high'],
        }, format='json')
        assert mock_pubmed.call_args.kwargs['journal_filter'] == 'surgery:high'

    @patch('search.services.batch_search.search_pubmed')
    def test_batch_nurse_with_cache_keeps_nursing_filter(self, mock_pubmed):
        """Regression: with the cache enabled, batch search used to drop the nursing filter."""
        mock_pubmed.return_value = (1, [_article()])
        self.client.post('/api/batch-search/', {
            'queries': [{'keywords': 'batch_nurse_kw', 'journal_rank': 'nurse'}],
        }, format='json')
        assert mock_pubmed.call_args.kwargs['journal_filter'] == 'nurse'

    @patch('search.services.batch_search.search_pubmed')
    def test_batch_with_cache_applies_custom_years(self, mock_pubmed):
        """Regression: with the cache enabled, batch search ignored the custom year range."""
        mock_pubmed.return_value = (1, [_article()])
        self.client.post('/api/batch-search/', {
            'queries': [{'keywords': 'batch_years_kw', 'journal_rank': 'surgery', 'journal_tiers': ['high'],
                         'time_period': '', 'year_from': 2020, 'year_to': 2022}],
        }, format='json')
        kwargs = mock_pubmed.call_args.kwargs
        assert kwargs['journal_filter'] == 'surgery:high'
        assert (kwargs['year_from'], kwargs['year_to'], kwargs['time_period']) == (2020, 2022, '')


@pytest.mark.django_db
@override_settings(MIDDLEWARE=TEST_MIDDLEWARE)
class TestCacheKeepsFullArticle(TestCase):
    """Cached results must carry every field of the article (outcomes, impact factor, countries...)."""

    @patch('search.views.search.search_pubmed')
    def test_cache_hit_returns_all_fields(self, mock_pubmed):
        article = {**_article('900'), 'primary_outcome': 'The primary outcome was mortality.',
                   'impact_factor': 6.5, 'impact_factor_year': 2024, 'surgery_tier': 'high',
                   'last_author_affiliation': 'Dept of Surgery, Lyon, France', 'sample_size': 120}
        CacheManager.save_to_cache(keywords='full_payload_kw', articles=[article], journal_rank='all')
        response = APIClient().post('/api/search/', {'keywords': 'full_payload_kw', 'journalRank': 'all'}, format='json')
        assert response.data['source'] == 'cache'
        mock_pubmed.assert_not_called()
        cached = response.data['data'][0]
        for key in ('primary_outcome', 'impact_factor', 'surgery_tier', 'last_author_affiliation', 'sample_size'):
            assert cached[key] == article[key]
