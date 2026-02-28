#!/usr/bin/env python
"""
test_end_to_end.py — Tests d'intégration end-to-end (sans mocks)
=================================================================
Teste le flux complet : PubMed API → extraction NLP → export Excel/PDF
Contrairement à test_views.py qui utilise des mocks, ces tests contactent
réellement PubMed et vérifient les résultats NLP en conditions réelles.

Prérequis :
  - Connexion internet + NCBI_API_KEY valide
  - venv activé

Usage :
  pytest benchmarks/test_end_to_end.py -v --tb=short
  python benchmarks/test_end_to_end.py   # standalone mode
"""

import os
import sys
import json
import time
import tempfile
import pytest

# ── Django bootstrap ────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from search.services.pubmed_client import search_pubmed
from search.services.participant_extractor import ParticipantExtractor
from search.services.outcome_extractor import OutcomeExtractor
from search.services.region_detector import get_region_from_affiliation, get_country_name


# ════════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════════

def _fetch_real_articles(query: str, n: int = 20, study_type: str = "randomized_controlled_trial"):
    """Fetch real articles from PubMed (requires network)."""
    try:
        total, articles = search_pubmed(term=query, start=0, size=n, study_type=study_type)
        return total, articles
    except Exception as e:
        pytest.skip(f"PubMed unavailable: {e}")


def _has_network():
    """Quick check for network connectivity."""
    try:
        import socket
        socket.create_connection(("eutils.ncbi.nlm.nih.gov", 443), timeout=5)
        return True
    except OSError:
        return False


# ════════════════════════════════════════════════════════════════════════════════
# END-TO-END TESTS
# ════════════════════════════════════════════════════════════════════════════════

@pytest.mark.skipif(not _has_network(), reason="No network connectivity")
class TestPubMedFetchAndNLP:
    """Test the full pipeline: PubMed fetch → NLP extraction on real data."""

    def test_fetch_returns_articles_with_abstracts(self):
        """PubMed returns articles and most have abstracts."""
        total, articles = _fetch_real_articles("liver resection", n=10)
        assert total > 0
        assert len(articles) >= 1
        with_abstract = sum(1 for a in articles if a.get('abstract', '').strip())
        assert with_abstract >= len(articles) * 0.5, \
            f"Only {with_abstract}/{len(articles)} articles have abstracts"

    def test_articles_have_required_fields(self):
        """Each article has the fields expected by the frontend."""
        _, articles = _fetch_real_articles("cardiac surgery", n=5)
        required_fields = ['pmid', 'title', 'journal', 'year', 'abstract']
        for art in articles:
            for field in required_fields:
                assert field in art, f"Article {art.get('pmid')} missing field '{field}'"

    def test_sample_size_extracted_on_real_articles(self):
        """ParticipantExtractor finds sample_size on at least some real RCTs."""
        # Use a query likely to return articles that mention participant counts
        _, articles = _fetch_real_articles("enrolled patients randomized", n=30)
        with_size = [a for a in articles if a.get('sample_size') is not None]
        assert len(with_size) >= 1, \
            f"Only {len(with_size)}/{len(articles)} articles have sample_size extracted"

    def test_sample_size_values_are_reasonable(self):
        """Extracted sample sizes are positive integers in reasonable range."""
        _, articles = _fetch_real_articles("clinical trial outcomes", n=20)
        for art in articles:
            ss = art.get('sample_size')
            if ss is not None:
                assert isinstance(ss, (int, float)), f"PMID {art.get('pmid')}: sample_size is {type(ss)}"
                assert 1 <= ss <= 10_000_000, f"PMID {art.get('pmid')}: sample_size={ss} out of range"

    def test_primary_outcome_extracted_on_rcts(self):
        """OutcomeExtractor finds primary outcomes in at least some RCTs."""
        _, articles = _fetch_real_articles("primary endpoint randomized", n=20)
        with_outcome = [a for a in articles if a.get('primary_outcome')]
        assert len(with_outcome) >= 3, \
            f"Only {len(with_outcome)}/20 articles have primary_outcome extracted"

    def test_region_detected_on_real_articles(self):
        """RegionDetector assigns a region to at least some articles."""
        _, articles = _fetch_real_articles("liver resection", n=20)
        with_region = [a for a in articles if a.get('region')]
        assert len(with_region) >= 5, \
            f"Only {len(with_region)}/20 articles have region detected"

    def test_region_values_are_valid(self):
        """Detected regions are from the valid set."""
        valid_regions = {'north_america', 'europe', 'asia', 'south_america', 'africa', 'oceania'}
        _, articles = _fetch_real_articles("surgery outcomes", n=20)
        for art in articles:
            region = art.get('region', '')
            if region:
                assert region in valid_regions, \
                    f"PMID {art.get('pmid')}: invalid region '{region}'"


@pytest.mark.skipif(not _has_network(), reason="No network connectivity")
class TestNLPReExtraction:
    """Re-extract NLP on fetched articles to verify current code matches cached values."""

    @pytest.fixture(scope="class")
    def real_articles(self):
        _, articles = _fetch_real_articles("surgery OR chemotherapy", n=30)
        return articles

    def test_participant_extractor_consistency(self, real_articles):
        """PE re-extraction matches the cached value from pubmed_client."""
        pe = ParticipantExtractor()
        mismatches = 0
        checked = 0
        for art in real_articles:
            abstract = art.get('abstract', '')
            if not abstract:
                continue
            cached_ss = art.get('sample_size')
            result = pe.extract_sample_size(abstract)
            extracted_ss = result.get('sample_size') if result else None
            checked += 1
            if cached_ss != extracted_ss:
                mismatches += 1
        # Allow small tolerance (pubmed_client may use slightly different params)
        assert mismatches <= checked * 0.1, \
            f"{mismatches}/{checked} PE mismatches between cached and re-extracted"

    def test_outcome_extractor_consistency(self, real_articles):
        """OE re-extraction matches the cached value from pubmed_client."""
        oe = OutcomeExtractor()
        mismatches = 0
        checked = 0
        for art in real_articles:
            abstract = art.get('abstract', '')
            if not abstract:
                continue
            cached_has = art.get('primary_outcome') is not None
            result = oe.extract_outcomes(abstract)
            extracted_has = result.get('primary_outcome') is not None if result else False
            checked += 1
            if cached_has != extracted_has:
                mismatches += 1
        assert mismatches <= checked * 0.1, \
            f"{mismatches}/{checked} OE mismatches between cached and re-extracted"

    def test_region_detector_consistency(self, real_articles):
        """RD re-extraction matches the cached value from pubmed_client."""
        mismatches = 0
        checked = 0
        for art in real_articles:
            affiliation = art.get('affiliation', '') or art.get('last_author_affiliation', '')
            if not affiliation:
                continue
            cached_region = art.get('region', '')
            extracted_region = get_region_from_affiliation(affiliation)
            checked += 1
            if cached_region != extracted_region:
                mismatches += 1
        assert mismatches <= checked * 0.05, \
            f"{mismatches}/{checked} RD mismatches between cached and re-extracted"


@pytest.mark.skipif(not _has_network(), reason="No network connectivity")
@pytest.mark.django_db
class TestExportEndToEnd:
    """Test export functionality with real article data."""

    def test_excel_export_produces_valid_file(self):
        """Export real articles to Excel → verify file is valid."""
        from django.test import RequestFactory
        from search.views.export import export_excel

        _, articles = _fetch_real_articles("liver resection", n=5)
        assert len(articles) >= 1

        factory = RequestFactory()
        request = factory.post('/export/excel/', json.dumps({'articles': articles}),
                               content_type='application/json')
        # DRF requires `.data` attribute
        import io
        request.data = {'articles': articles}
        request.content_type = 'application/json'

        response = export_excel(request)
        assert response.status_code == 200
        assert 'spreadsheetml' in response['Content-Type']
        assert len(response.content) > 100, "Excel file too small"

        # Verify it's a valid XLSX by trying to open it
        from openpyxl import load_workbook
        wb = load_workbook(io.BytesIO(response.content))
        ws = wb.active
        assert ws is not None
        rows = list(ws.iter_rows(values_only=True))
        assert len(rows) >= 2, "Excel should have header + at least 1 data row"
        header = rows[0]
        assert 'PMID' in header
        assert 'Region' in header

    def test_pdf_export_produces_valid_file(self):
        """Export real articles to PDF → verify file is valid."""
        from django.test import RequestFactory
        from search.views.export import export_pdf

        _, articles = _fetch_real_articles("cardiac surgery", n=3)

        factory = RequestFactory()
        request = factory.post('/export/pdf/', json.dumps({'articles': articles}),
                               content_type='application/json')
        request.data = {'articles': articles}
        request.content_type = 'application/json'

        response = export_pdf(request)
        assert response.status_code == 200
        assert 'pdf' in response['Content-Type']
        assert response.content[:4] == b'%PDF', "Response is not a valid PDF"


@pytest.mark.skipif(not _has_network(), reason="No network connectivity")
@pytest.mark.django_db
class TestSearchAPICacheFlow:
    """Test the full search → cache → re-search flow with real PubMed data."""

    def test_search_then_cache_hit(self):
        """First search hits PubMed, second returns from cache."""
        from rest_framework.test import APIClient
        from django.test import override_settings

        # Disable rate limiting
        client = APIClient()

        # Use a unique keyword to avoid collisions
        keyword = f"endoscopic_surgery_e2e_{int(time.time())}"

        # First search (PubMed)
        response = client.post('/api/search/', {
            'keywords': keyword,
            'journalRank': 'all'
        }, format='json')

        # May return 200 with 0 results or 503 if PubMed rate-limited
        if response.status_code == 503:
            pytest.skip("PubMed rate limited")
        assert response.status_code == 200

        # If articles were found and cached
        if response.data.get('total', 0) > 0 and response.data.get('source') == 'pubmed':
            time.sleep(0.5)
            # Second search — should hit cache
            response2 = client.post('/api/search/', {
                'keywords': keyword,
                'journalRank': 'all'
            }, format='json')
            assert response2.status_code == 200
            assert response2.data.get('source') == 'cache'


# ════════════════════════════════════════════════════════════════════════════════
# STANDALONE MODE
# ════════════════════════════════════════════════════════════════════════════════

def main():
    """Run end-to-end checks standalone."""
    print("\n🔗 Test End-to-End — Flux complet PubMed → NLP → Export")
    print("=" * 60)

    if not _has_network():
        print("❌ Pas de connexion réseau. Impossible de tester.")
        return 1

    pe = ParticipantExtractor()
    oe = OutcomeExtractor()
    all_pass = True

    # 1. Fetch articles
    print("\n📡 1. Récupération de 20 articles réels depuis PubMed...")
    total, articles = _fetch_real_articles("liver resection randomized", n=20)
    print(f"   ✓ {len(articles)} articles récupérés (total PubMed: {total})")

    # 2. Verify NLP extraction
    print("\n🧠 2. Vérification extraction NLP...")
    with_ss = sum(1 for a in articles if a.get('sample_size') is not None)
    with_oe = sum(1 for a in articles if a.get('primary_outcome'))
    with_rd = sum(1 for a in articles if a.get('region'))
    with_abstract = sum(1 for a in articles if a.get('abstract', '').strip())

    print(f"   Articles avec abstract: {with_abstract}/{len(articles)}")
    print(f"   Sample size extrait:    {with_ss}/{len(articles)}")
    print(f"   Primary outcome extrait: {with_oe}/{len(articles)}")
    print(f"   Région détectée:        {with_rd}/{len(articles)}")

    if with_ss < 3:
        print("   ⚠ Trop peu de sample sizes extraits")
        all_pass = False
    if with_oe < 3:
        print("   ⚠ Trop peu de primary outcomes extraits")
        all_pass = False
    if with_rd < 5:
        print("   ⚠ Trop peu de régions détectées")
        all_pass = False

    # 3. Re-extraction consistency
    print("\n🔄 3. Vérification cohérence re-extraction...")
    pe_mismatch = oe_mismatch = rd_mismatch = 0
    checked = 0
    for art in articles:
        abstract = art.get('abstract', '')
        if not abstract:
            continue
        checked += 1

        # PE
        pe_result = pe.extract_sample_size(abstract)
        pe_val = pe_result.get('sample_size') if pe_result else None
        if pe_val != art.get('sample_size'):
            pe_mismatch += 1

        # OE
        oe_result = oe.extract_outcomes(abstract)
        oe_has = oe_result.get('primary_outcome') is not None if oe_result else False
        if oe_has != (art.get('primary_outcome') is not None):
            oe_mismatch += 1

        # RD
        aff = art.get('affiliation', '') or art.get('last_author_affiliation', '')
        if aff:
            rd_val = get_region_from_affiliation(aff)
            if rd_val != art.get('region', ''):
                rd_mismatch += 1

    print(f"   PE mismatches: {pe_mismatch}/{checked}")
    print(f"   OE mismatches: {oe_mismatch}/{checked}")
    print(f"   RD mismatches: {rd_mismatch}/{checked}")

    # 4. Excel export
    print("\n📊 4. Test export Excel...")
    try:
        from openpyxl import Workbook
        import io
        from django.test import RequestFactory
        from search.views.export import export_excel

        factory = RequestFactory()
        request = factory.post('/export/excel/', json.dumps({'articles': articles[:5]}),
                               content_type='application/json')
        request.data = {'articles': articles[:5]}
        response = export_excel(request)
        if response.status_code == 200 and len(response.content) > 100:
            wb = load_workbook(io.BytesIO(response.content))
            ws = wb.active
            rows = list(ws.iter_rows(values_only=True))
            print(f"   ✓ Excel OK: {len(rows)} lignes, {len(rows[0])} colonnes")
        else:
            print(f"   ❌ Excel export échoué (status={response.status_code})")
            all_pass = False
    except Exception as e:
        print(f"   ❌ Excel export erreur: {e}")
        all_pass = False

    # Summary
    print(f"\n{'═' * 60}")
    if all_pass:
        print("  ✅ TOUS LES TESTS E2E PASSENT")
    else:
        print("  ⚠ CERTAINS TESTS E2E ONT EU DES PROBLÈMES")
    print(f"{'═' * 60}\n")

    return 0 if all_pass else 1


if __name__ == '__main__':
    from openpyxl import load_workbook
    sys.exit(main())
