"""
Unit tests for ParticipantExtractor.
Tests regex-based sample size extraction from PubMed abstracts.
"""
import pytest
from search.services.participant_extractor import ParticipantExtractor


class TestParticipantExtractorBasic:
    """Tests for basic numeric extraction patterns."""

    def test_total_of_n_patients(self):
        abstract = "A total of 250 patients were enrolled in the randomized clinical trial."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 250
        assert result['confidence'] in ('high', 'medium')

    def test_n_participants_enrolled(self):
        abstract = "119 participants were enrolled in this multicenter study."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 119
        assert result['confidence'] in ('high', 'medium')

    def test_study_included_n(self):
        abstract = "The study included 500 patients with hepatocellular carcinoma."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 500

    def test_n_equals_pattern(self):
        abstract = "We analyzed the data (N = 342) from a prospective cohort."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 342

    def test_sample_size_with_comma_separator(self):
        abstract = "A total of 34,684 patients were included in this analysis."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 34684

    def test_cohort_of_n(self):
        abstract = "We studied a cohort of 1200 subjects over 5 years."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 1200

    def test_enrolled_n_patients(self):
        abstract = "The trial enrolled 53 patients from three hospitals."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 53

    def test_randomized_n_patients(self):
        abstract = "We randomized 400 patients to receive either drug A or placebo."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 400


class TestParticipantExtractorWrittenNumbers:
    """Tests for written-number extraction patterns."""

    def test_twenty_five_participants(self):
        abstract = "Twenty-five participants completed the study protocol."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 25

    def test_total_of_fifteen_subjects(self):
        abstract = "A total of fifteen subjects were recruited from the clinic."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 15

    def test_four_hundred_seventy_two_patients(self):
        """Compound hundred numbers must be fully parsed."""
        abstract = "Four hundred seventy-two patients with acute ischemic stroke were randomized to alteplase or placebo."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 472

    def test_one_hundred_twenty_patients(self):
        abstract = "One hundred twenty patients were randomly assigned. The primary endpoint was 30-day morbidity rate."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 120

    def test_three_hundred_fifty_subjects(self):
        abstract = "Three hundred fifty subjects were enrolled in the multicenter trial."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 350

    def test_two_thousand_patients(self):
        abstract = "Two thousand patients were included in this retrospective cohort study."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 2000

    def test_five_hundred_patients(self):
        abstract = "Five hundred patients were recruited across 12 European centers."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 500


class TestParticipantExtractorEdgeCases:
    """Tests for edge cases and validation."""

    def test_empty_abstract(self):
        result = ParticipantExtractor.extract_sample_size("")
        assert result['sample_size'] is None
        assert result['confidence'] == 'none'
        assert result['method'] == 'no_abstract'

    def test_none_abstract(self):
        result = ParticipantExtractor.extract_sample_size(None)
        assert result['sample_size'] is None
        assert result['confidence'] == 'none'

    def test_short_abstract(self):
        result = ParticipantExtractor.extract_sample_size("Too short")
        assert result['sample_size'] is None

    def test_no_participant_info(self):
        abstract = "This review discusses the mechanisms of action of immunotherapy in cancer treatment."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] is None
        assert result['method'] == 'no_match'

    def test_returns_dict_with_required_keys(self):
        abstract = "A total of 100 patients were screened."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert 'sample_size' in result
        assert 'confidence' in result
        assert 'matched_text' in result
        assert 'method' in result

    def test_very_small_number_rejected(self):
        """Numbers < 5 should be ignored (not realistic sample sizes)."""
        abstract = "Of 3 patients screened, all received treatment."
        result = ParticipantExtractor.extract_sample_size(abstract)
        # 3 is below the 5 threshold, so it may or may not match
        if result['sample_size'] is not None:
            assert result['sample_size'] >= 5


class TestParticipantExtractorConfidence:
    """Tests for confidence scoring."""

    def test_high_confidence_total_of(self):
        abstract = "A total of 1000 patients were enrolled in this phase III trial at 50 centers."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['confidence'] == 'high'

    def test_high_confidence_participants_enrolled(self):
        abstract = "In total, 500 participants were enrolled and randomized."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['confidence'] == 'high'


class TestScreeningVsEnrollment:
    """Tests for screening→enrollment funnel detection (Phase 8)."""

    def test_screened_of_whom_included(self):
        """Screening funnel: 'screened X, of whom Y were included'"""
        abstract = "Eleven hospitals screened 6148 patients, of whom 751 were included in this trial."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 751

    def test_total_assessed_and_enrolled(self):
        """Screening funnel: 'total of X assessed, and Y were enrolled'"""
        abstract = "A total of 3971 patients with severe obesity were assessed, and 217 patients were enrolled and randomized."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 217

    def test_total_screened_semicolon_randomized(self):
        """Screening funnel: 'total of X were screened; Y were randomized'"""
        abstract = "A total of 1645 patients were screened; 289 patients were randomized in a 2:1 fashion."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 289

    def test_screened_excluded_enrolled(self):
        """Screening with exclusion language"""
        abstract = "We screened 500 patients. Of these, 200 were excluded and 300 were enrolled."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 300

    def test_screening_number_not_preferred(self):
        """Plain 'screened X patients' should have low confidence vs enrollment"""
        abstract = "We screened 1000 patients and enrolled 200 patients in this trial."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 200


class TestMultiArmSummation:
    """Tests for multi-arm RCT detection and summation (Phase 8)."""

    def test_two_arm_randomization(self):
        """Sum (n=X) + (n=Y) in randomization context"""
        abstract = "Patients were randomized 1:1 to either the treatment group (n = 528) or the control group (n = 528)."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 1056

    def test_two_arm_assigned(self):
        """Sum arms with 'assigned' context"""
        abstract = "Participants were assigned to clipping (n = 834) or no clipping (n = 844)."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 1678

    def test_three_arm_trial(self):
        """Sum 3 arms"""
        abstract = "Randomization was performed to polyhexanide (n = 292), saline (n = 295), or control (n = 102)."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 689

    def test_explicit_total_overrides_arm_sum(self):
        """When explicit total exists, don't use arm sum"""
        abstract = "A total of 1056 eligible patients were enrolled. They were assigned to groups (n = 528) or (n = 528)."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 1056

    def test_no_arm_sum_without_context(self):
        """(n=X) without randomization context should not be summed"""
        abstract = "Grade B (n = 26) and C (n = 5) fistulas occurred. 250 patients were analyzed."
        result = ParticipantExtractor.extract_sample_size(abstract)
        assert result['sample_size'] == 250
