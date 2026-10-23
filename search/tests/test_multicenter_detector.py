"""
Unit tests for MulticenterDetector.

Tests the four-level hierarchy:
  1. Explicit multicenter keywords (high confidence)
  2. Explicit single-center keywords (high confidence)
  3. Numeric center count (high/medium confidence)
  4. Indirect affiliation evidence (low/medium confidence)
"""
import pytest
from search.services.multicenter_detector import detect_multicenter


# ===========================================================================
# LEVEL 1 — Explicit multicenter keywords
# ===========================================================================

class TestExplicitMulticenter:

    def test_multicenter_keyword(self):
        abstract = "This multicenter randomized controlled trial enrolled 500 patients."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is True
        assert result['confidence'] == 'high'

    def test_multicentre_british_spelling(self):
        abstract = "A prospective multicentre study was conducted across Europe."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is True
        assert result['confidence'] == 'high'

    def test_multi_center_hyphen(self):
        abstract = "In this multi-center trial, patients were randomized 1:1."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is True
        assert result['confidence'] == 'high'

    def test_multisite(self):
        abstract = "This multisite cohort study included participants from 8 academic hospitals."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is True
        assert result['confidence'] == 'high'

    def test_multi_institutional(self):
        abstract = "A multi-institutional prospective study evaluated outcomes in 300 patients."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is True
        assert result['confidence'] == 'high'

    def test_conducted_at_n_centers(self):
        abstract = "The study was conducted at 12 centers in the United States and Canada."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is True
        assert result['confidence'] == 'high'

    def test_from_n_hospitals(self):
        abstract = "Data were collected from 7 hospitals between January 2020 and December 2023."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is True
        assert result['confidence'] == 'high'

    def test_n_centers_participated(self):
        abstract = "20 centers participated in this prospective randomized study."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is True
        assert result['confidence'] == 'high'

    def test_across_n_countries(self):
        abstract = "This trial was performed across 15 countries in North America, Europe, and Asia."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is True
        assert result['confidence'] == 'high'

    def test_consortium(self):
        abstract = "The study was conducted by a collaborative consortium of 25 academic centers."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is True
        assert result['confidence'] == 'high'

    def test_national_registry(self):
        abstract = "We analyzed data from a national registry of 45,320 patients with heart failure."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is True
        assert result['confidence'] == 'high'

    def test_international_database(self):
        abstract = "We queried the international database, which contained 12,000 patients with heart failure."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is True
        assert result['confidence'] == 'high'

    def test_pooled_analysis(self):
        abstract = "Pooled data from centers in France, Germany, and Italy were analyzed."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is True
        assert result['confidence'] == 'high'

    def test_french_multicentrique(self):
        abstract = "Une étude multicentrique prospective a été menée dans 10 centres français."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is True
        assert result['confidence'] == 'high'

    def test_french_pluricentrique(self):
        abstract = "Cette étude pluri-centrique a inclus 450 patients en chirurgie orthopédique."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is True
        assert result['confidence'] == 'high'

    def test_french_conducted_across_centers(self):
        abstract = "L'étude a été réalisée dans 8 centres universitaires français."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is True
        assert result['confidence'] == 'high'

    def test_research_network(self):
        abstract = "This prospective study was designed by the French Surgical Research Network."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is True
        assert result['confidence'] == 'high'


# ===========================================================================
# LEVEL 2 — Explicit single-center keywords
# ===========================================================================

class TestExplicitSingleCenter:

    def test_single_center(self):
        abstract = "This single-center retrospective study reviewed 120 consecutive patients."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is False
        assert result['confidence'] == 'high'

    def test_single_centre_british(self):
        abstract = "A single-centre randomized trial was conducted at our tertiary hospital."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is False
        assert result['confidence'] == 'high'

    def test_single_institution(self):
        abstract = "We performed a retrospective analysis at a single institution over 10 years."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is False
        assert result['confidence'] == 'high'

    def test_single_site(self):
        abstract = "This single-site prospective trial enrolled 85 patients with colorectal cancer."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is False
        assert result['confidence'] == 'high'

    def test_at_a_single_center(self):
        abstract = "All procedures were performed at a single center between 2018 and 2023."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is False
        assert result['confidence'] == 'high'

    def test_at_one_hospital(self):
        abstract = "The study was conducted at one hospital in the Paris metropolitan area."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is False
        assert result['confidence'] == 'high'

    def test_french_monocentrique(self):
        abstract = "Il s'agit d'une étude monocentrique rétrospective portant sur 200 patients."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is False
        assert result['confidence'] == 'high'

    def test_french_unicentrique(self):
        abstract = "Cette étude uni-centrique a été conduite au CHU de Clermont-Ferrand."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is False
        assert result['confidence'] == 'high'

    def test_french_un_seul_centre(self):
        abstract = "L'étude a été réalisée dans un seul centre hospitalier universitaire."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is False
        assert result['confidence'] == 'high'


# ===========================================================================
# LEVEL 3 — Numeric center count
# ===========================================================================

class TestNumericCenterCount:

    def test_count_greater_than_1_multicenter(self):
        abstract = "Patients were enrolled from 3 academic hospitals in Southwest France."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is True
        assert result['center_count'] == 3

    def test_count_equals_1_single_center(self):
        abstract = "Data from 1 center were analyzed in this retrospective cohort."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is False
        assert result['center_count'] == 1

    def test_performed_at_5_sites(self):
        abstract = "The trial was performed at 5 sites across the United Kingdom."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is True
        assert result['center_count'] == 5

    def test_center_count_extracted(self):
        abstract = "Conducted across 18 centers in 6 countries, this RCT enrolled 1200 patients."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is True
        assert result['center_count'] == 18

    def test_french_dans_n_centres(self):
        abstract = "L'étude a été conduite dans 4 centres de chirurgie digestive."
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is True
        assert result['center_count'] == 4


# ===========================================================================
# LEVEL 4 — Indirect evidence from affiliations
# ===========================================================================

class TestIndirectAffiliationEvidence:

    def test_multiple_countries_in_abstract(self):
        abstract = (
            "Patients were recruited from centers in france and germany during 2021. "
            "The primary endpoint was 30-day mortality."
        )
        result = detect_multicenter(abstract, affiliation="CHU Clermont-Ferrand, France")
        assert result['is_multicenter'] is True
        assert result['confidence'] == 'medium'

    def test_multiple_institutions_in_affiliation(self):
        abstract = "A prospective observational study assessing postoperative outcomes."
        affiliation = (
            "Department of Surgery, University Hospital A; "
            "Department of Oncology, Medical Center B"
        )
        result = detect_multicenter(abstract, affiliation=affiliation)
        assert result['is_multicenter'] is True
        assert result['confidence'] == 'low'


# ===========================================================================
# UNKNOWN / INSUFFICIENT EVIDENCE
# ===========================================================================

class TestUnknown:

    def test_empty_abstract(self):
        result = detect_multicenter("")
        assert result['is_multicenter'] is None
        assert result['confidence'] == 'none'

    def test_short_abstract(self):
        result = detect_multicenter("No data.")
        assert result['is_multicenter'] is None
        assert result['confidence'] == 'none'

    def test_no_center_info_abstract(self):
        abstract = (
            "This study investigated the effect of metformin on HbA1c levels in patients "
            "with type 2 diabetes. Patients were randomized to receive either metformin or placebo. "
            "The primary outcome was change in HbA1c at 12 weeks."
        )
        result = detect_multicenter(abstract)
        # No explicit center info → is_multicenter could be None or False, never True
        assert result['is_multicenter'] is not True

    def test_return_keys_always_present(self):
        """Result dict always contains all required keys."""
        result = detect_multicenter("A randomized study of 100 patients.")
        assert 'is_multicenter' in result
        assert 'confidence' in result
        assert 'center_count' in result
        assert 'evidence' in result

    def test_valid_confidence_values(self):
        """Confidence is always one of the four allowed values."""
        valid = {'high', 'medium', 'low', 'none'}
        for abstract in [
            "",
            "Single-center study.",
            "Multicenter RCT conducted at 10 hospitals.",
            "A study of 200 patients with no center information provided.",
        ]:
            result = detect_multicenter(abstract)
            assert result['confidence'] in valid


# ===========================================================================
# PRIORITY ORDER — Explicit multicenter takes precedence over single-center
# ===========================================================================

class TestPriorityOrder:

    def test_multicenter_wins_over_single_center_mention(self):
        """
        Abstract mentions both: 'single-center' in context of past studies
        but the current study is explicitly multicenter.
        """
        abstract = (
            "Unlike previous single-center reports, this multicenter randomized trial "
            "enrolled 800 patients from 15 hospitals."
        )
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is True
        assert result['confidence'] == 'high'

    def test_center_count_gt_1_overrides_no_keyword(self):
        abstract = (
            "Patients were recruited from 6 institutions between January 2020 and June 2023."
        )
        result = detect_multicenter(abstract)
        assert result['is_multicenter'] is True

    def test_evidence_text_non_empty_when_detected(self):
        abstract = "This multisite study enrolled 300 patients."
        result = detect_multicenter(abstract)
        assert len(result['evidence']) > 0
