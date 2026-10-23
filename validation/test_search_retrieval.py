#!/usr/bin/env python
"""
test_search_retrieval.py — Test de pertinence de la récupération PubMed
========================================================================
Valide l'objectif #1 de l'application : pour une requête donnée, les articles
attendus sont effectivement trouvés par PubMed.

4 niveaux de tests (~253 tests) :
  1. Unit: _build_query, journal config, publication type mapping (offline)
  2. PMID lookup: articles connus sont retrouvés par PMID (online)
  3. Keyword retrieval: requêtes chirurgicales retrouvent des articles pertinents (online)
  4. Specific article: articles précis retrouvés par mots-clés (online)

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

from search.services.pubmed_client import (
    search_pubmed, _build_query, PubMedError,
    PUBLICATION_TYPE_MAP, ALLOWED_PUBLICATION_TYPES,
)
from search.services.journal_config import (
    build_journal_filter, build_nursing_journal_filter,
    ALL_TARGET_JOURNALS, TARGET_JOURNALS, NURSING_JOURNALS,
    JOURNAL_VARIANTS, get_journal_name, is_target_journal,
    get_journal_display_name,
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


def _matches_nlm_abbreviation(full_title: str, abbreviation: str) -> bool:
    """True if each word of an NLM abbreviation prefixes successive words of a full title.

    PubMed returns full journal titles ("Journal of child health care : ...")
    while journal_config lists NLM abbreviations ("J Child Health Care").
    """
    stopwords = {"of", "the", "and", "for", "in", "on", "de", "la", "&"}
    title_words = [w for w in re.findall(r"[a-z]+", full_title.lower()) if w not in stopwords]
    abbr_words = re.findall(r"[a-z]+", abbreviation.lower())
    if not abbr_words or len(abbr_words) > len(title_words):
        return False
    return all(t.startswith(a) for a, t in zip(abbr_words, title_words))


# ════════════════════════════════════════════════════════════════════════════════
# DATA FOR PARAMETRIZED TESTS
# ════════════════════════════════════════════════════════════════════════════════

# Study types in PUBLICATION_TYPE_MAP but NOT in ALLOWED_PUBLICATION_TYPES
NON_ALLOWED_STUDY_TYPES = [
    "adaptive_clinical_trial",
    "clinical_trial",
    "clinical_trial_protocol",
    "clinical_trial_phase_i",
    "clinical_trial_phase_ii",
    "clinical_trial_phase_iii",
    "clinical_trial_phase_iv",
    "equivalence_trial",
    "pragmatic_clinical_trial",
    "twin_study",
]

# Legacy/backward-compatible aliases in PUBLICATION_TYPE_MAP
LEGACY_STUDY_TYPE_MAPPINGS = [
    ("randomized_controlled", "Randomized Controlled Trial"),
    ("meta", "Meta-Analysis"),
    ("cohort", "Cohort Studies"),
    ("case_control", "Case-Control Studies"),
]

# One representative variant per journal for parametrized tests
SELECTED_VARIANTS = [
    ("NEJM", "New England Journal of Medicine"),
    ("Lancet", "The Lancet"),
    ("JAMA", "Journal of the American Medical Association"),
    ("JAMA Surg", "JAMA Surgery"),
    ("BJS", "British Journal of Surgery"),
    ("Ann Surg", "Annals of Surgery"),
    ("Int J Surg", "International Journal of Surgery"),
    ("Dig Endosc", "Digestive Endoscopy"),
    ("Liver Transpl", "Liver Transplantation"),
    ("J Am Coll Surg", "Journal of the American College of Surgeons"),
    ("Am J Transplant", "American Journal of Transplantation"),
    ("Endoscopy", "Endoscopy"),
    ("Hepatobiliary Surg Nutr", "Hepatobiliary Surgery and Nutrition"),
]


# ════════════════════════════════════════════════════════════════════════════════
# LEVEL 1 — UNIT TESTS: _build_query, journal config, publication types (offline)
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

    # ── Semicolon handling ──────────────────────────────────────────────────

    def test_semicolon_converts_to_and(self):
        """Semicolons in search terms are converted to AND operators."""
        query = _build_query(term="liver; resection", journal_filter="no_filter")
        assert "AND" in query
        assert "liver" in query
        assert "resection" in query

    def test_multiple_semicolons(self):
        """Multiple semicolons produce multiple AND joins."""
        query = _build_query(
            term="liver; resection; outcomes", journal_filter="no_filter"
        )
        assert query.count("AND") >= 2

    # ── MeSH / Other Term fields ────────────────────────────────────────────

    def test_query_includes_mesh_terms(self):
        """Query includes [MeSH Terms] field for better recall."""
        query = _build_query(term="hepatectomy", journal_filter="no_filter")
        assert "[MeSH Terms]" in query

    def test_query_includes_other_term(self):
        """Query includes [Other Term] field for author keywords."""
        query = _build_query(term="hepatectomy", journal_filter="no_filter")
        assert "[Other Term]" in query

    # ── Combined filters ────────────────────────────────────────────────────

    def test_journal_filter_combined_with_study_type(self):
        """Journal filter and study type can be applied simultaneously."""
        query = _build_query(
            term="surgery", study_type="randomized_controlled_trial",
            journal_filter=""
        )
        assert "[Journal]" in query
        assert "[Publication Type]" in query

    def test_empty_term_with_journal_filter(self):
        """Empty term with journal filter still produces valid query."""
        query = _build_query(term="", journal_filter="")
        assert isinstance(query, str)
        assert "[Journal]" in query

    def test_whitespace_term_handled(self):
        """Whitespace-only term does not crash."""
        query = _build_query(term="   ", journal_filter="no_filter")
        assert isinstance(query, str)

    # ── Each journal code individually ──────────────────────────────────────

    @pytest.mark.parametrize("code", list(TARGET_JOURNALS.keys()),
                             ids=list(TARGET_JOURNALS.keys()))
    def test_specific_journal_code_each(self, code):
        """Each journal code produces a filter with only that journal."""
        query = _build_query(term="surgery", journal_filter=code)
        expected = TARGET_JOURNALS[code]
        assert expected in query, f"Journal '{expected}' not in query for code '{code}'"
        assert "[Journal]" in query

    # ── Each allowed study type ─────────────────────────────────────────────

    @pytest.mark.parametrize("study_type", sorted(ALLOWED_PUBLICATION_TYPES),
                             ids=sorted(ALLOWED_PUBLICATION_TYPES))
    def test_each_allowed_study_type(self, study_type):
        """Each ALLOWED study type produces [Publication Type] in query."""
        query = _build_query(
            term="surgery", study_type=study_type, journal_filter="no_filter"
        )
        assert "[Publication Type]" in query, \
            f"Allowed type '{study_type}' did not produce Publication Type filter"

    # ── Non-allowed types filtered ──────────────────────────────────────────

    @pytest.mark.parametrize("study_type", NON_ALLOWED_STUDY_TYPES,
                             ids=NON_ALLOWED_STUDY_TYPES)
    def test_non_allowed_study_type_excluded(self, study_type):
        """Non-allowed study types produce no additional filter."""
        query_with = _build_query(
            term="surgery", study_type=study_type, journal_filter="no_filter"
        )
        query_without = _build_query(
            term="surgery", study_type="", journal_filter="no_filter"
        )
        assert query_with == query_without, \
            f"Non-allowed type '{study_type}' should not modify query"

    # ── Legacy study type mappings ──────────────────────────────────────────

    @pytest.mark.parametrize("alias,expected_frag", LEGACY_STUDY_TYPE_MAPPINGS,
                             ids=[m[0] for m in LEGACY_STUDY_TYPE_MAPPINGS])
    def test_legacy_study_type_in_map(self, alias, expected_frag):
        """Legacy aliases resolve to correct PubMed query fragment in map."""
        assert alias in PUBLICATION_TYPE_MAP, f"Legacy alias '{alias}' not in map"
        assert expected_frag in PUBLICATION_TYPE_MAP[alias], \
            f"'{alias}' maps to '{PUBLICATION_TYPE_MAP[alias]}', expected '{expected_frag}'"


class TestJournalConfig:
    """Verify journal configuration integrity."""

    # ── Existing tests ──────────────────────────────────────────────────────

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

    # ── get_journal_name ────────────────────────────────────────────────────

    @pytest.mark.parametrize("code,expected_name", list(TARGET_JOURNALS.items()),
                             ids=list(TARGET_JOURNALS.keys()))
    def test_get_journal_name_valid(self, code, expected_name):
        """get_journal_name returns correct name for each valid code."""
        result = get_journal_name(code)
        assert result == expected_name

    def test_get_journal_name_invalid_returns_empty(self):
        """get_journal_name returns empty string for unknown code."""
        result = get_journal_name("xyz_nonexistent")
        assert result == ""

    # ── is_target_journal ───────────────────────────────────────────────────

    @pytest.mark.parametrize("canonical", ALL_TARGET_JOURNALS,
                             ids=[j[:30] for j in ALL_TARGET_JOURNALS])
    def test_is_target_journal_canonical(self, canonical):
        """is_target_journal returns True for each canonical journal name."""
        assert is_target_journal(canonical) is True, \
            f"'{canonical}' should be target journal"

    @pytest.mark.parametrize("variant,canonical", SELECTED_VARIANTS,
                             ids=[v[0][:25] for v in SELECTED_VARIANTS])
    def test_is_target_journal_variant(self, variant, canonical):
        """is_target_journal returns True for known abbreviations."""
        assert is_target_journal(variant) is True, \
            f"Variant '{variant}' (of '{canonical}') should be target journal"

    def test_is_target_journal_false_for_unknown(self):
        """Unknown journal returns False."""
        assert is_target_journal("Fake Journal of Nothing") is False

    def test_is_target_journal_empty_string(self):
        """Empty string returns False."""
        assert is_target_journal("") is False

    def test_is_target_journal_case_insensitive(self):
        """is_target_journal is case-insensitive."""
        first = ALL_TARGET_JOURNALS[0]
        assert is_target_journal(first.upper()) is True
        assert is_target_journal(first.lower()) is True

    # ── get_journal_display_name ────────────────────────────────────────────

    @pytest.mark.parametrize("canonical", ALL_TARGET_JOURNALS,
                             ids=[j[:30] for j in ALL_TARGET_JOURNALS])
    def test_display_name_canonical(self, canonical):
        """Canonical name maps to itself as display name."""
        result = get_journal_display_name(canonical)
        assert result == canonical

    @pytest.mark.parametrize("variant,canonical", SELECTED_VARIANTS,
                             ids=[v[0][:25] for v in SELECTED_VARIANTS])
    def test_display_name_from_variant(self, variant, canonical):
        """Variant maps to canonical display name."""
        result = get_journal_display_name(variant)
        assert result == canonical, \
            f"Variant '{variant}' should display as '{canonical}', got '{result}'"

    # ── JOURNAL_VARIANTS consistency ────────────────────────────────────────

    def test_journal_variants_keys_cover_all_targets(self):
        """Every target journal has an entry in JOURNAL_VARIANTS."""
        for journal in ALL_TARGET_JOURNALS:
            assert journal in JOURNAL_VARIANTS, \
                f"'{journal}' missing from JOURNAL_VARIANTS"

    def test_journal_variants_values_are_lists(self):
        """All JOURNAL_VARIANTS values are non-empty lists of strings."""
        for canon, variants in JOURNAL_VARIANTS.items():
            assert isinstance(variants, list), f"Variants for '{canon}' not a list"
            assert len(variants) >= 1, f"No variants for '{canon}'"
            for v in variants:
                assert isinstance(v, str) and len(v) > 0

    def test_nursing_journals_all_nonempty_strings(self):
        """All nursing journal entries are non-empty strings."""
        for j in NURSING_JOURNALS:
            assert isinstance(j, str) and len(j.strip()) > 0

    def test_all_target_list_matches_dict_values(self):
        """ALL_TARGET_JOURNALS matches TARGET_JOURNALS.values()."""
        assert set(ALL_TARGET_JOURNALS) == set(TARGET_JOURNALS.values())


class TestPublicationTypeConfig:
    """Verify publication type map and allowed types consistency."""

    def test_allowed_types_subset_of_map(self):
        """All ALLOWED types are present in PUBLICATION_TYPE_MAP."""
        for t in ALLOWED_PUBLICATION_TYPES:
            assert t in PUBLICATION_TYPE_MAP, \
                f"Allowed type '{t}' not in PUBLICATION_TYPE_MAP"

    def test_map_values_contain_bracket_format(self):
        """All MAP values contain [Publication Type] or [MeSH Terms]."""
        for key, val in PUBLICATION_TYPE_MAP.items():
            assert "[Publication Type]" in val or "[MeSH Terms]" in val, \
                f"Map entry '{key}' has unexpected format: {val}"

    def test_allowed_types_count(self):
        """Expected number of allowed publication types."""
        assert len(ALLOWED_PUBLICATION_TYPES) == 14

    def test_map_has_core_types(self):
        """Core study types are in the map."""
        core = [
            "randomized_controlled_trial", "meta_analysis", "systematic_review",
            "clinical_trial", "observational_study", "case_reports",
        ]
        for t in core:
            assert t in PUBLICATION_TYPE_MAP

    def test_map_size_minimum(self):
        """Map contains at least 30 entries."""
        assert len(PUBLICATION_TYPE_MAP) >= 30


class TestQueryEdgeCases:
    """Verify _build_query handles edge cases correctly."""

    def test_very_long_term(self):
        """Very long term does not crash."""
        long_term = "liver " * 200
        query = _build_query(term=long_term.strip(), journal_filter="no_filter")
        assert isinstance(query, str) and len(query) > 0

    def test_special_characters_in_term(self):
        """Special characters in term don't crash."""
        query = _build_query(term="p53 gene (tumor)", journal_filter="no_filter")
        assert isinstance(query, str)

    def test_unicode_term(self):
        """Unicode characters in term don't crash."""
        query = _build_query(term="résection hépatique", journal_filter="no_filter")
        assert isinstance(query, str) and len(query) > 0

    def test_quoted_phrase(self):
        """Quoted phrase in term is preserved."""
        query = _build_query(term='"liver resection"', journal_filter="no_filter")
        assert '"liver resection"' in query

    def test_all_allowed_types_combined(self):
        """All allowed types combined produce a valid query."""
        combined = ",".join(sorted(ALLOWED_PUBLICATION_TYPES))
        query = _build_query(
            term="surgery", study_type=combined, journal_filter="no_filter"
        )
        assert "[Publication Type]" in query
        assert " OR " in query

    def test_nurse_with_study_type(self):
        """Nursing filter combined with study type."""
        query = _build_query(
            term="pain", study_type="randomized_controlled_trial",
            journal_filter="nurse"
        )
        assert "[Journal]" in query
        assert "[Publication Type]" in query

    def test_empty_everything(self):
        """All empty parameters still produce a string."""
        query = _build_query(term="", study_type="", journal_filter="")
        assert isinstance(query, str)

    def test_term_with_and_operator(self):
        """AND operator in term is preserved."""
        query = _build_query(term="liver AND resection", journal_filter="no_filter")
        assert "AND" in query

    def test_term_with_not_operator(self):
        """NOT operator in term is preserved."""
        query = _build_query(term="liver NOT cirrhosis", journal_filter="no_filter")
        assert "NOT" in query

    def test_numeric_term(self):
        """Numeric-only term does not crash."""
        query = _build_query(term="12345", journal_filter="no_filter")
        assert "12345" in query

    def test_single_character_term(self):
        """Single character term does not crash."""
        query = _build_query(term="A", journal_filter="no_filter")
        assert isinstance(query, str)

    def test_mixed_boolean_operators(self):
        """Multiple boolean operators in term are preserved."""
        query = _build_query(
            term="liver OR hepatic AND resection", journal_filter="no_filter"
        )
        assert "OR" in query
        assert "AND" in query

    def test_semicolon_with_study_type(self):
        """Semicolons combined with study type filter."""
        query = _build_query(
            term="liver; resection", study_type="randomized_controlled_trial",
            journal_filter="no_filter"
        )
        assert "AND" in query
        assert "[Publication Type]" in query

    def test_specific_journal_with_semicolon(self):
        """Semicolons combined with specific journal filter."""
        query = _build_query(
            term="liver; surgery", journal_filter="nejm"
        )
        assert "AND" in query
        assert "[Journal]" in query


# ════════════════════════════════════════════════════════════════════════════════
# LEVEL 2 — PMID LOOKUP: known articles are retrievable (online)
# ════════════════════════════════════════════════════════════════════════════════

# Reference articles from gold standard — well-known surgical PMIDs
# Each entry: (pmid, expected_title_fragment, expected_journal_fragment)
REFERENCE_ARTICLES = [
    ("21037437", "pentoxifylline", "Annals of Surgery"),
    ("9409569", "Pringle maneuver", ""),
    ("35081569", "Coronary Revascularization", ""),
    ("31042283", "Circulating Tumor Cell", "JAMA"),
    ("37459169", "Myocardial Injury", ""),
    ("15798461", "Glutamine supplementation", ""),
]


@pytest.mark.network
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

    # ── Batch validation ────────────────────────────────────────────────────

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

    # ── Article structure validation ────────────────────────────────────────

    def test_articles_have_year(self, fetched_articles):
        """All articles have a valid year field."""
        for art in fetched_articles.values():
            year = art.get("year")
            assert isinstance(year, int), f"PMID {art['pmid']}: year not int"
            assert 1800 < year < 2100, f"PMID {art['pmid']}: year {year} out of range"

    def test_articles_have_authors(self, fetched_articles):
        """Most articles have author information."""
        with_authors = sum(
            1 for a in fetched_articles.values()
            if a.get("authors")
        )
        assert with_authors >= len(REFERENCE_ARTICLES) * 0.5

    def test_article_keys_complete(self, fetched_articles):
        """All articles have required keys."""
        required = {"pmid", "title", "journal", "year", "abstract", "study_type"}
        for art in fetched_articles.values():
            missing = required - set(art.keys())
            assert not missing, f"PMID {art.get('pmid')}: missing {missing}"

    def test_pmid_format_is_digits(self, fetched_articles):
        """All PMIDs are digit strings."""
        for pmid in fetched_articles:
            assert pmid.isdigit(), f"PMID '{pmid}' is not all digits"

    def test_language_field_present(self, fetched_articles):
        """All articles have a language field."""
        for art in fetched_articles.values():
            assert "language" in art, f"PMID {art['pmid']}: no language field"

    def test_study_type_assigned(self, fetched_articles):
        """All articles have a study_type string."""
        for art in fetched_articles.values():
            assert "study_type" in art
            assert isinstance(art["study_type"], str)

    def test_region_is_string_when_present(self, fetched_articles):
        """Region field is a string when populated."""
        for art in fetched_articles.values():
            region = art.get("region")
            if region:
                assert isinstance(region, str)

    def test_primary_outcome_is_string_when_present(self, fetched_articles):
        """Primary outcome is a string when populated."""
        for art in fetched_articles.values():
            po = art.get("primary_outcome")
            if po:
                assert isinstance(po, str)

    def test_sample_size_is_int_when_present(self, fetched_articles):
        """Sample size is an int when populated."""
        for art in fetched_articles.values():
            ss = art.get("sample_size")
            if ss is not None:
                assert isinstance(ss, int), \
                    f"PMID {art['pmid']}: sample_size type {type(ss)}"

    # ── Per-PMID parametrized checks ────────────────────────────────────────

    @pytest.mark.parametrize(
        "pmid,title_frag,journal_frag", REFERENCE_ARTICLES,
        ids=[r[0] for r in REFERENCE_ARTICLES],
    )
    def test_individual_pmid_has_title(
        self, fetched_articles, pmid, title_frag, journal_frag
    ):
        """Each article has a non-trivial title."""
        art = fetched_articles.get(pmid)
        assert art is not None, f"PMID {pmid} not in results"
        assert isinstance(art["title"], str) and len(art["title"]) > 5

    @pytest.mark.parametrize(
        "pmid,title_frag,journal_frag", REFERENCE_ARTICLES,
        ids=[r[0] for r in REFERENCE_ARTICLES],
    )
    def test_individual_pmid_has_journal(
        self, fetched_articles, pmid, title_frag, journal_frag
    ):
        """Each article has a non-trivial journal name."""
        art = fetched_articles.get(pmid)
        assert art is not None
        assert isinstance(art["journal"], str) and len(art["journal"]) > 2

    @pytest.mark.parametrize(
        "pmid,title_frag,journal_frag", REFERENCE_ARTICLES,
        ids=[r[0] for r in REFERENCE_ARTICLES],
    )
    def test_individual_pmid_year_reasonable(
        self, fetched_articles, pmid, title_frag, journal_frag
    ):
        """Each article has a reasonable publication year."""
        art = fetched_articles.get(pmid)
        assert art is not None
        assert 1950 <= art["year"] <= 2025


# ════════════════════════════════════════════════════════════════════════════════
# LEVEL 3 — KEYWORD RETRIEVAL: search queries return relevant articles (online)
# ════════════════════════════════════════════════════════════════════════════════

# Each entry: (query, expected_min_results, journal_filter, study_type, description)
RETRIEVAL_SCENARIOS = [
    # Broad surgical queries
    ("liver resection", 50, "no_filter", "", "broad liver resection"),
    ("pancreatic surgery outcomes", 10, "no_filter", "", "pancreatic surgery"),
    ("cardiac surgery complications", 20, "no_filter", "", "cardiac surgery"),
    ("colorectal surgery laparoscopic", 20, "no_filter", "", "colorectal surgery"),
    ("knee replacement outcomes", 10, "no_filter", "", "orthopedic query"),
    ("craniotomy complications", 10, "no_filter", "", "neurosurgery query"),
    ("prostate cancer surgery", 20, "no_filter", "", "urology query"),
    ("pediatric appendectomy", 5, "no_filter", "", "pediatric surgery"),
    ("breast cancer surgery outcomes", 10, "no_filter", "", "oncologic surgery"),
    ("bariatric surgery outcomes", 5, "no_filter", "", "bariatric query"),
    ("hernia repair surgery", 10, "no_filter", "", "hernia surgery"),
    ("thyroid surgery complications", 5, "no_filter", "", "thyroid surgery"),
    ("spinal surgery outcomes", 10, "no_filter", "", "spine surgery"),
    ("organ transplantation rejection", 5, "no_filter", "", "transplant rejection"),
    ("laparoscopic cholecystectomy", 30, "no_filter", "", "common surgery"),
    ("ICU delirium prevention", 5, "no_filter", "", "critical care"),
    ("anesthesia complications cardiac", 5, "no_filter", "", "anesthesia query"),

    # A-rank journal filter
    ("liver resection", 5, "", "", "liver in A-rank"),
    ("liver transplantation", 5, "", "", "transplant in A-rank"),
    ("coronary artery bypass", 5, "", "", "CABG in A-rank"),
    ("colectomy outcomes", 3, "", "", "colectomy in A-rank"),
    ("transplantation immunosuppression", 3, "", "", "transplant immunosupp A-rank"),

    # With study type filter
    ("liver surgery", 5, "no_filter", "randomized_controlled_trial", "liver RCT"),
    ("surgery outcomes", 5, "no_filter", "meta_analysis", "meta-analysis filter"),
    ("burn treatment randomized", 3, "no_filter", "randomized_controlled_trial", "burn RCT"),
    ("hip fracture surgery", 3, "no_filter", "systematic_review", "hip fracture SR"),
    ("wound infection surgical", 3, "no_filter", "observational_study", "wound observational"),
    ("cancer immunotherapy", 3, "no_filter", "meta_analysis", "immunotherapy MA"),

    # Nursing filter
    ("postoperative pain", 5, "nurse", "", "nursing postop pain"),
    ("nursing pain assessment postoperative", 3, "nurse", "", "nursing pain assessment"),
    ("wound care management", 3, "nurse", "", "nursing wound care"),

    # Specific journal codes
    ("surgery", 3, "jama", "", "JAMA search"),
]


@pytest.mark.network
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

    def test_a_rank_second_query(self):
        """Second A-rank query also returns correctly filtered results."""
        total, articles = _safe_search(
            term="colorectal surgery", start=0, size=20, journal_filter="",
        )
        target_lower = {j.lower() for j in ALL_TARGET_JOURNALS}
        for art in articles:
            assert art.get("journal", "").lower() in target_lower

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
        nursing_keywords = ("nurs", "enferm", "midwi", "soins infirm", "pflege")
        for art in articles:
            journal = art.get("journal", "").lower()
            matching = journal in nursing_lower or any(
                kw in journal for kw in nursing_keywords
            ) or any(
                _matches_nlm_abbreviation(journal, abbr) for abbr in NURSING_JOURNALS
            )
            assert matching, \
                f"PMID {art.get('pmid')}: journal '{art.get('journal')}' not a nursing journal"

    def test_nursing_second_query(self):
        """Second nursing query also returns nursing journals."""
        total, articles = _safe_search(
            term="chronic pain", start=0, size=20, journal_filter="nurse",
        )
        assert len(articles) >= 1, "Nursing filter returned no results"
        # PubMed returns full journal names while our list uses NLM abbreviations;
        # check that at least half match our abbreviated names or nursing keywords
        nursing_lower = {j.lower() for j in NURSING_JOURNALS}
        nursing_keywords = ("nurs", "enferm", "midwi", "soins infirm", "pflege",
                            "caring", "birth", "wound")
        matched = sum(
            1 for art in articles
            if art.get("journal", "").lower() in nursing_lower
            or any(kw in art.get("journal", "").lower() for kw in nursing_keywords)
        )
        assert matched >= len(articles) * 0.5, \
            f"Only {matched}/{len(articles)} matched nursing journals"

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

    # ── Year range search ───────────────────────────────────────────────────

    YEAR_RANGE_PARAMS = [
        (2020, 2023, "recent 2020-2023"),
        (2010, 2015, "mid range 2010-2015"),
        (2000, 2005, "older 2000-2005"),
        (2022, 2022, "single year 2022"),
    ]

    @pytest.mark.parametrize("year_from,year_to,desc", YEAR_RANGE_PARAMS,
                             ids=[p[2] for p in YEAR_RANGE_PARAMS])
    def test_year_range_search(self, year_from, year_to, desc):
        """Date-filtered searches return articles within the year range."""
        total, articles = _safe_search(
            term="surgery", start=0, size=10,
            journal_filter="no_filter",
            year_from=year_from, year_to=year_to,
        )
        assert total >= 1, f"No results for year range {year_from}-{year_to}"
        for art in articles:
            assert year_from - 1 <= art["year"] <= year_to + 1, \
                f"PMID {art['pmid']}: year {art['year']} outside [{year_from},{year_to}]"

    # ── Additional structure tests ──────────────────────────────────────────

    def test_search_returns_unique_pmids(self):
        """All PMIDs in a single search result are unique."""
        _, articles = _safe_search(
            term="surgery", start=0, size=50, journal_filter="no_filter",
        )
        pmids = [a["pmid"] for a in articles]
        assert len(pmids) == len(set(pmids)), "Duplicate PMIDs in results"

    def test_articles_have_nlp_enrichment(self):
        """At least some returned articles have NLP-enriched fields."""
        _, articles = _safe_search(
            term="randomized controlled trial surgery", start=0, size=20,
            journal_filter="no_filter",
        )
        has_nlp = sum(
            1 for a in articles
            if a.get("sample_size") is not None
            or a.get("primary_outcome")
            or a.get("region")
        )
        assert has_nlp >= 1, "No articles with NLP enrichment"

    def test_results_journal_nonempty(self):
        """All returned articles have non-empty journal names."""
        _, articles = _safe_search(
            term="liver resection", start=0, size=20, journal_filter="no_filter",
        )
        for art in articles:
            assert art.get("journal", "").strip(), \
                f"PMID {art['pmid']}: empty journal"

    def test_size_parameter_respected(self):
        """size parameter limits number of returned articles."""
        _, articles = _safe_search(
            term="surgery", start=0, size=5, journal_filter="no_filter",
        )
        assert len(articles) <= 5

    # ── Study type filter online ────────────────────────────────────────────

    STUDY_TYPE_ONLINE_PARAMS = [
        ("randomized_controlled_trial", "RCT online"),
        ("meta_analysis", "meta-analysis online"),
        ("systematic_review", "systematic review online"),
        ("observational_study", "observational online"),
    ]

    @pytest.mark.parametrize("study_type,desc", STUDY_TYPE_ONLINE_PARAMS,
                             ids=[p[1] for p in STUDY_TYPE_ONLINE_PARAMS])
    def test_study_type_filter_online(self, study_type, desc):
        """Study type filter returns results when applied to broad query."""
        total, articles = _safe_search(
            term="cancer surgery", start=0, size=10,
            study_type=study_type, journal_filter="no_filter",
        )
        assert total >= 1, f"No results for study type '{study_type}'"
        assert len(articles) >= 1

    # ── Specific journal code search ────────────────────────────────────────

    JOURNAL_CODE_SEARCH_PARAMS = [
        ("jama", "JAMA online"),
        ("annals_surgery", "Annals online"),
        ("jama_surgery", "JAMA Surgery online"),
    ]

    @pytest.mark.parametrize("code,desc", JOURNAL_CODE_SEARCH_PARAMS,
                             ids=[p[1] for p in JOURNAL_CODE_SEARCH_PARAMS])
    def test_specific_journal_code_search(self, code, desc):
        """Specific journal code returns articles from that journal."""
        total, articles = _safe_search(
            term="surgery", start=0, size=10, journal_filter=code,
        )
        assert total >= 1, f"No results for journal code '{code}'"
        expected = TARGET_JOURNALS[code].lower()
        for art in articles:
            assert expected in art.get("journal", "").lower(), \
                f"Article from '{art.get('journal')}' not from '{TARGET_JOURNALS[code]}'"

    def test_combined_journal_and_study_type_search(self):
        """Combined journal + study type filter works online."""
        total, articles = _safe_search(
            term="surgery outcomes", start=0, size=10,
            study_type="randomized_controlled_trial", journal_filter="",
        )
        assert total >= 1


# ════════════════════════════════════════════════════════════════════════════════
# LEVEL 4 — SPECIFIC PMID RETRIEVAL: find a known article by keyword search
# ════════════════════════════════════════════════════════════════════════════════

# Articles that MUST be findable by their title keywords
# (pmid, search_terms, journal_filter)
MUST_FIND_ARTICLES = [
    # Hepatic surgery — Pringle maneuver (A-rank: Annals of Surgery)
    ("9409569", "Pringle maneuver hepatectomy", ""),
    # Burn — pentoxifylline (any journal)
    ("21037437", "pentoxifylline liver regeneration", "no_filter"),
    # A-rank filtered — coronary revascularization (NEJM)
    ("35081569", "coronary revascularization", ""),
    # A-rank filtered — circulating tumor cell (JAMA)
    ("31042283", "Circulating Tumor Cell surgery", ""),
    # A-rank filtered — myocardial injury (JAMA)
    ("37459169", "Myocardial Injury noncardiac surgery", ""),
    # A-rank filtered — pentoxifylline (Annals of Surgery)
    ("21037437", "pentoxifylline liver", ""),
    # A-rank filtered — Pringle variant keywords
    ("9409569", "Pringle maneuver intermittent", ""),
]


@pytest.mark.network
@pytest.mark.skipif(not _has_network(), reason="No network connectivity")
class TestSpecificArticleRetrieval:
    """Find specific known articles by keyword search."""

    @pytest.mark.parametrize(
        "pmid,keywords,journal_filter",
        MUST_FIND_ARTICLES,
        ids=[f"PMID_{a[0]}_{i}" for i, a in enumerate(MUST_FIND_ARTICLES)],
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
