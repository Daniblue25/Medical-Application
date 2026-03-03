#!/usr/bin/env python
"""
test_search_retrieval.py — Test de pertinence de la récupération PubMed
========================================================================
Valide l'objectif #1 de l'application : pour une requête donnée, les articles
attendus sont effectivement trouvés par PubMed.

3 niveaux de tests :
  1. Unit: _build_query construit correctement les requêtes PubMed
  2. PMID lookup: articles connus sont retrouvés par PMID
  3. Keyword retrieval: requêtes chirurgicales retrouvent des articles pertinents

Prérequis :
  - Connexion internet + NCBI_API_KEY valide (pour tests en ligne)

Usage :
  pytest benchmarks/test_search_retrieval.py -v --tb=short
"""

import os
import sys
import re
import time
import pytest

# ── Django bootstrap ────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from search.services.pubmed_client import search_pubmed, _build_query, PubMedError
from search.services.journal_config import (
    build_journal_filter, build_nursing_journal_filter,
    ALL_TARGET_JOURNALS, TARGET_JOURNALS, NURSING_JOURNALS,
)


# ════════════════════════════════════════════════════════════════════════════════
# HELPERS
# ════════════════════════════════════════════════════════════════════════════════

def _has_network():
    try:
        import socket
        socket.create_connection(("eutils.ncbi.nlm.nih.gov", 443), timeout=5)
        return True
    except OSError:
        return False


def _safe_search(**kwargs):
    """Search PubMed with skip on transient errors."""
    try:
        return search_pubmed(**kwargs)
    except (PubMedError, Exception) as e:
        if "rate" in str(e).lower() or "503" in str(e):
            pytest.skip(f"PubMed rate-limited: {e}")
        raise


# ════════════════════════════════════════════════════════════════════════════════
# LEVEL 1 — UNIT TESTS: _build_query & journal filter logic (offline)
# ════════════════════════════════════════════════════════════════════════════════

class TestBuildQuery:
    """Verify _build_query constructs correct PubMed queries for all modes."""

    # ── Journal filter mapping ──────────────────────────────────────────────

    def test_rank_a_applies_13_journal_filter(self):
        """journalRank='a' -> journal_filter='' -> query includes 13 journal names."""
        query = _build_query(term="liver resection", journal_filter="")
        assert "[Journal]" in query
        for journal in ALL_TARGET_JOURNALS:
            assert journal in query, f"Missing journal: {journal}"

    def test_rank_all_no_journal_filter(self):
        """journalRank='all' -> journal_filter='no_filter' -> no [Journal] in query."""
        query = _build_query(term="liver resection", journal_filter="no_filter")
        assert "[Journal]" not in query
        assert "liver resection[Title/Abstract]" in query

    def test_rank_nurse_applies_nursing_filter(self):
        """journalRank='nurse' -> journal_filter='nurse' -> nursing journals in query."""
        query = _build_query(term="pain management", journal_filter="nurse")
        assert "[Journal]" in query
        assert "J Adv Nurs" in query
        assert "Nurs Res" in query

    def test_specific_journal_code(self):
        """Specific journal code -> only that journal in filter."""
        query = _build_query(term="surgery", journal_filter="nejm")
        assert '"New England Journal of Medicine"[Journal]' in query
        assert "Annals of Surgery" not in query

    # ── Term handling ───────────────────────────────────────────────────────

    def test_simple_term_in_title_abstract(self):
        """Simple terms are searched in [Title/Abstract]."""
        query = _build_query(term="pancreatic surgery", journal_filter="no_filter")
        assert "pancreatic surgery[Title/Abstract]" in query

    def test_boolean_operators_preserved(self):
        """Boolean operators (OR, AND) in term are preserved."""
        query = _build_query(term="liver OR hepatic", journal_filter="no_filter")
        assert "liver OR hepatic" in query
        assert "[Title/Abstract]" in query

    def test_empty_term_defaults_gracefully(self):
        """Empty keyword does not crash _build_query."""
        query = _build_query(term="", journal_filter="no_filter")
        assert isinstance(query, str)

    # ── Study type filter ───────────────────────────────────────────────────

    def test_study_type_rct(self):
        """study_type='randomized_controlled_trial' adds publication type filter."""
        query = _build_query(
            term="surgery", study_type="randomized_controlled_trial",
            journal_filter="no_filter"
        )
        assert '"Randomized Controlled Trial"[Publication Type]' in query

    def test_study_type_meta_analysis(self):
        """study_type='meta_analysis' adds meta-analysis filter."""
        query = _build_query(
            term="outcomes", study_type="meta_analysis",
            journal_filter="no_filter"
        )
        assert '"Meta-Analysis"[Publication Type]' in query

    def test_multiple_study_types(self):
        """Multiple study types combined with OR."""
        query = _build_query(
            term="surgery", study_type="randomized_controlled_trial,meta_analysis",
            journal_filter="no_filter"
        )
        assert '"Randomized Controlled Trial"[Publication Type]' in query
        assert '"Meta-Analysis"[Publication Type]' in query
        assert " OR " in query

    def test_invalid_study_type_ignored(self):
        """Invalid study type is silently ignored."""
        query = _build_query(
            term="surgery", study_type="invalid_type",
            journal_filter="no_filter"
        )
        assert "[Publication Type]" not in query


class TestJournalConfig:
    """Verify journal configuration integrity."""

    def test_target_journals_count(self):
        """13 target journals configured."""
        assert len(ALL_TARGET_JOURNALS) == 13
        assert len(TARGET_JOURNALS) == 13

    def test_nursing_journals_count(self):
        """At least 100 nursing journals configured."""
        assert len(NURSING_JOURNALS) >= 100

    def test_journal_filter_empty_returns_all_13(self):
        """build_journal_filter('') returns OR of all 13 journals."""
        f = build_journal_filter('')
        assert f.startswith("(")
        assert f.endswith(")")
        count = f.count("[Journal]")
        assert count == 13, f"Expected 13 journals, got {count}"

    def test_journal_filter_no_filter_returns_empty(self):
        """build_journal_filter('no_filter') returns empty string."""
        assert build_journal_filter('no_filter') == ""

    def test_journal_filter_unknown_code_returns_empty(self):
        """Unknown journal code returns empty string (no filter)."""
        assert build_journal_filter('xyz_unknown') == ""

    def test_nursing_filter_length(self):
        """Nursing filter contains all nursing journals."""
        f = build_nursing_journal_filter()
        count = f.count("[Journal]")
        assert count == len(NURSING_JOURNALS)


# ════════════════════════════════════════════════════════════════════════════════
# LEVEL 2 — PMID LOOKUP: known articles are retrievable (online)
# ════════════════════════════════════════════════════════════════════════════════

# Reference articles from gold standard — well-known surgical PMIDs
# Each entry: (pmid, expected_title_fragment, expected_journal_fragment)
REFERENCE_ARTICLES = [
    # Hepatic surgery — Annals of Surgery
    ("21037437", "pentoxifylline", "Annals of Surgery"),
    # Hepatic surgery — randomized trial
    ("9409569", "Pringle maneuver", ""),
    # Meta-analysis
    ("35081569", "Coronary Revascularization", ""),
    # Cardiac surgery — JAMA Surgery
    ("31042283", "Circulating Tumor Cell", "JAMA"),
    # Observational — large cohort
    ("37459169", "Myocardial Injury", ""),
    # Pediatric — RCT
    ("15798461", "Glutamine supplementation", ""),
]


@pytest.mark.skipif(not _has_network(), reason="No network connectivity")
class TestPMIDLookup:
    """Verify that known PMIDs are retrievable and correctly parsed."""

    @pytest.fixture(scope="class")
    def fetched_articles(self):
        """Fetch all reference PMIDs in a single batch via efetch."""
        from search.services.pubmed_client import _request, _parse_article_xml
        pmids = [r[0] for r in REFERENCE_ARTICLES]
        efetch_params = {
            "db": "pubmed",
            "id": ",".join(pmids),
            "retmode": "xml",
        }
        response = _request("efetch.fcgi", efetch_params)
        articles = _parse_article_xml(response.text)
        return {a["pmid"]: a for a in articles}

    def test_all_pmids_found(self, fetched_articles):
        """All reference PMIDs are returned by PubMed."""
        for pmid, title_frag, journal_frag in REFERENCE_ARTICLES:
            assert pmid in fetched_articles, \
                f"PMID {pmid} not found in PubMed response"

    def test_titles_match(self, fetched_articles):
        """Article titles contain expected keywords."""
        for pmid, title_frag, _ in REFERENCE_ARTICLES:
            art = fetched_articles.get(pmid)
            if art and title_frag:
                assert title_frag.lower() in art["title"].lower(), \
                    f"PMID {pmid}: expected '{title_frag}' in title '{art['title'][:80]}'"

    def test_journals_match(self, fetched_articles):
        """Article journals match expected values (when specified)."""
        for pmid, _, journal_frag in REFERENCE_ARTICLES:
            if not journal_frag:
                continue
            art = fetched_articles.get(pmid)
            if art:
                assert journal_frag.lower() in art["journal"].lower(), \
                    f"PMID {pmid}: expected '{journal_frag}' in journal '{art['journal']}'"

    def test_articles_have_abstracts(self, fetched_articles):
        """Most reference articles have abstracts."""
        with_abstract = sum(
            1 for a in fetched_articles.values()
            if a.get("abstract", "").strip()
        )
        assert with_abstract >= len(REFERENCE_ARTICLES) * 0.7, \
            f"Only {with_abstract}/{len(REFERENCE_ARTICLES)} have abstracts"

    def test_nlp_fields_populated(self, fetched_articles):
        """NLP extraction runs on fetched articles (PE, OE, RD populated)."""
        for pmid, _, _ in REFERENCE_ARTICLES:
            art = fetched_articles.get(pmid)
            if not art or not art.get("abstract", "").strip():
                continue
            has_pe = art.get("sample_size") is not None
            has_oe = art.get("primary_outcome") is not None
            has_rd = bool(art.get("region"))
            assert has_pe or has_oe or has_rd, \
                f"PMID {pmid}: no NLP field populated (PE={has_pe}, OE={has_oe}, RD={has_rd})"


# ════════════════════════════════════════════════════════════════════════════════
# LEVEL 3 — KEYWORD RETRIEVAL: search queries return relevant articles (online)
# ════════════════════════════════════════════════════════════════════════════════

# Each entry: (query, expected_min_results, journal_filter, study_type, description)
RETRIEVAL_SCENARIOS = [
    # Basic surgical queries — broad search on all PubMed
    ("liver resection", 50, "no_filter", "", "broad surgical query"),
    ("pancreatic surgery outcomes", 10, "no_filter", "", "specific surgical query"),
    ("cardiac surgery complications", 20, "no_filter", "", "cardiac surgery"),

    # A-rank journal filter — should still return results
    ("liver resection", 5, "", "", "liver resection in 13 A-rank journals"),
    ("liver transplantation", 5, "", "", "liver transplant in A-rank journals"),

    # With study type filter
    ("liver surgery", 5, "no_filter", "randomized_controlled_trial", "RCT filter"),
    ("surgery outcomes", 5, "no_filter", "meta_analysis", "meta-analysis filter"),

    # Nursing filter
    ("postoperative pain", 5, "nurse", "", "nursing journals"),
]


@pytest.mark.skipif(not _has_network(), reason="No network connectivity")
class TestKeywordRetrieval:
    """Verify keyword searches return relevant, correctly structured results."""

    @pytest.mark.parametrize(
        "query,min_results,journal_filter,study_type,desc",
        RETRIEVAL_SCENARIOS,
        ids=[s[4] for s in RETRIEVAL_SCENARIOS],
    )
    def test_retrieval_returns_enough_results(
        self, query, min_results, journal_filter, study_type, desc
    ):
        """Search returns at least min_results articles."""
        total, articles = _safe_search(
            term=query, start=0, size=50,
            study_type=study_type, journal_filter=journal_filter,
        )
        assert total >= min_results, \
            f"'{query}' ({desc}): expected >= {min_results} results, got {total}"
        assert len(articles) >= 1, \
            f"'{query}' ({desc}): no articles returned"

    def test_a_rank_results_are_from_target_journals(self):
        """Results from A-rank filter should be from the 13 target journals."""
        total, articles = _safe_search(
            term="liver resection", start=0, size=20, journal_filter="",
        )
        target_lower = {j.lower() for j in ALL_TARGET_JOURNALS}
        for art in articles:
            journal = art.get("journal", "").lower()
            assert journal in target_lower, \
                f"PMID {art.get('pmid')}: journal '{art.get('journal')}' not in A-rank list"

    def test_no_filter_returns_diverse_journals(self):
        """Results without journal filter should include journals outside A-rank."""
        total, articles = _safe_search(
            term="liver resection", start=0, size=50, journal_filter="no_filter",
        )
        target_lower = {j.lower() for j in ALL_TARGET_JOURNALS}
        non_target = [
            a for a in articles
            if a.get("journal", "").lower() not in target_lower
        ]
        assert len(non_target) >= 3, \
            f"Expected diverse journals, but {len(non_target)}/{len(articles)} are non-target"

    def test_nursing_results_from_nursing_journals(self):
        """Results from nursing filter should be from nursing journals."""
        total, articles = _safe_search(
            term="postoperative pain", start=0, size=20, journal_filter="nurse",
        )
        nursing_lower = {j.lower() for j in NURSING_JOURNALS}
        for art in articles:
            journal = art.get("journal", "").lower()
            matching = journal in nursing_lower or "nurs" in journal
            assert matching, \
                f"PMID {art.get('pmid')}: journal '{art.get('journal')}' not a nursing journal"

    def test_articles_have_complete_structure(self):
        """All returned articles have required fields with valid values."""
        _, articles = _safe_search(
            term="surgery outcomes", start=0, size=10, journal_filter="no_filter",
        )
        required_fields = {
            "pmid": str,
            "title": str,
            "journal": str,
            "year": int,
            "abstract": str,
            "study_type": str,
            "region": str,
            "country": str,
        }
        for art in articles:
            for field, expected_type in required_fields.items():
                assert field in art, f"PMID {art.get('pmid')}: missing field '{field}'"
                val = art[field]
                if val is not None:
                    assert isinstance(val, expected_type), \
                        f"PMID {art.get('pmid')}: {field} is {type(val)}, expected {expected_type}"

    def test_pagination_works(self):
        """start/size parameters correctly paginate results."""
        _, page1 = _safe_search(
            term="surgery", start=0, size=5, journal_filter="no_filter",
        )
        time.sleep(0.5)
        _, page2 = _safe_search(
            term="surgery", start=5, size=5, journal_filter="no_filter",
        )
        pmids1 = {a["pmid"] for a in page1}
        pmids2 = {a["pmid"] for a in page2}
        overlap = pmids1 & pmids2
        assert len(overlap) == 0, \
            f"Pages overlap: {overlap}"


# ════════════════════════════════════════════════════════════════════════════════
# LEVEL 4 — SPECIFIC PMID RETRIEVAL: find a known article by keyword search
# ════════════════════════════════════════════════════════════════════════════════

# Articles that MUST be findable by their title keywords
# (pmid, search_terms, journal_filter)
MUST_FIND_ARTICLES = [
    # "Pringle maneuver hepatectomy" in Annals of Surgery (A-rank)
    ("9409569", "Pringle maneuver hepatectomy", ""),
    # "pentoxifylline liver regeneration" in any journal
    ("21037437", "pentoxifylline liver regeneration", "no_filter"),
]


@pytest.mark.skipif(not _has_network(), reason="No network connectivity")
class TestSpecificArticleRetrieval:
    """Find specific known articles by keyword search."""

    @pytest.mark.parametrize(
        "pmid,keywords,journal_filter",
        MUST_FIND_ARTICLES,
        ids=[f"PMID_{a[0]}" for a in MUST_FIND_ARTICLES],
    )
    def test_known_article_found_by_keywords(self, pmid, keywords, journal_filter):
        """A known article should be findable by its title keywords."""
        total, articles = _safe_search(
            term=keywords, start=0, size=50,
            journal_filter=journal_filter,
        )
        found_pmids = {a["pmid"] for a in articles}
        assert pmid in found_pmids, \
            f"PMID {pmid} not found in first 50 results for '{keywords}' " \
            f"(got {total} total, {len(articles)} returned)"
