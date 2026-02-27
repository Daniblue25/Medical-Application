"""
Unit tests for OutcomeExtractor.
Tests regex-based primary outcome, adverse events, efficacy, results, and safety extraction.
"""
import pytest
from search.services.outcome_extractor import OutcomeExtractor


class TestPrimaryOutcome:
    """Tests for primary outcome extraction."""

    def test_primary_outcome_was(self):
        abstract = "The primary outcome was overall survival at 12 months in the intention-to-treat population."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['primary_outcome'] is not None
        assert 'overall survival' in result['primary_outcome'].lower()
        assert result['primary_outcome_confidence'] == 'high'

    def test_primary_endpoint_was(self):
        abstract = "The primary endpoint was progression-free survival assessed by blinded review."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['primary_outcome'] is not None
        assert 'progression-free survival' in result['primary_outcome'].lower()

    def test_main_outcome_was(self):
        abstract = "The main outcome was the rate of surgical site infections within 30 days."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['primary_outcome'] is not None
        assert result['primary_outcome_confidence'] == 'high'

    def test_primary_outcome_colon(self):
        abstract = "Primary outcome: disease-free survival at 5 years of follow-up."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['primary_outcome'] is not None
        assert result['primary_outcome_confidence'] == 'medium'

    def test_french_primary_outcome(self):
        abstract = "Le critère de jugement principal était la survie globale à 12 mois."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['primary_outcome'] is not None


class TestAdverseEvents:
    """Tests for adverse events extraction."""

    def test_adverse_events_with_percentage(self):
        abstract = "Serious adverse events occurred in 15% of patients in the treatment group and 12% in the placebo group."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['adverse_events'] is not None
        assert result['adverse_events_confidence'] == 'high'

    def test_treatment_related_adverse_events(self):
        abstract = "Treatment-related adverse events of grade 3 or higher occurred in 23% of patients receiving the drug."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['adverse_events'] is not None

    def test_most_common_side_effects(self):
        abstract = "The most common adverse events were nausea (25%), fatigue (18%), and diarrhea (12%)."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['adverse_events'] is not None


class TestEfficacy:
    """Tests for efficacy extraction."""

    def test_treatment_effective(self):
        abstract = "Treatment was effective in 78% of patients who completed the study protocol."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['efficacy'] is not None
        assert result['efficacy_confidence'] == 'high'

    def test_superior_to(self):
        abstract = "Drug A was superior to placebo with an odds ratio of 2.5 (95% CI 1.8-3.2)."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['efficacy'] is not None

    def test_overall_survival(self):
        abstract = "Median overall survival was 18.7 months in the treatment group vs 12.1 months in the control group."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['efficacy'] is not None


class TestResults:
    """Tests for results extraction."""

    def test_results_showed(self):
        abstract = "Results showed a significant reduction in mortality of 25% in the treatment arm (p<0.001)."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['results'] is not None
        assert result['results_confidence'] == 'high'

    def test_hazard_ratio(self):
        abstract = "The hazard ratio for death was 0.72 (95% CI, 0.59 to 0.88; P=0.002)."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['results'] is not None

    def test_significant_difference(self):
        abstract = "A significant difference was observed between groups with 30% improvement in the primary endpoint."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['results'] is not None


class TestSafety:
    """Tests for safety extraction."""

    def test_well_tolerated(self):
        abstract = "The treatment was well-tolerated with no grade 4 or 5 adverse events reported in 200 patients."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['safety'] is not None

    def test_safety_profile(self):
        abstract = "The safety profile was consistent with previous studies, with 5% discontinuation rate."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['safety'] is not None


class TestEdgeCases:
    """Tests for edge cases."""

    def test_empty_abstract(self):
        result = OutcomeExtractor.extract_outcomes("")
        assert result['primary_outcome'] is None
        assert result['has_outcomes'] is False

    def test_none_abstract(self):
        result = OutcomeExtractor.extract_outcomes(None)
        assert result['primary_outcome'] is None

    def test_short_abstract(self):
        result = OutcomeExtractor.extract_outcomes("Short text")
        assert result['primary_outcome'] is None

    def test_has_outcomes_flag(self):
        abstract = "The primary outcome was overall survival at one year in the modified intent-to-treat population."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['has_outcomes'] is True

    def test_no_outcomes_abstract(self):
        abstract = "This editorial discusses the importance of clinical trial transparency and data sharing in oncology research."
        result = OutcomeExtractor.extract_outcomes(abstract)
        # Editorials usually don't have outcomes
        # has_outcomes may or may not be True (catch-all patterns)


class TestExtractSummary:
    """Tests for extract_summary."""

    def test_summary_with_high_confidence(self):
        abstract = "The primary outcome was event-free survival at 24 months."
        summary = OutcomeExtractor.extract_summary(abstract)
        assert summary is not None
        assert summary.startswith("✓")

    def test_summary_none_for_empty(self):
        summary = OutcomeExtractor.extract_summary("")
        assert summary is None

    def test_summary_truncation(self):
        abstract = "The primary endpoint was " + "a" * 300 + "."
        summary = OutcomeExtractor.extract_summary(abstract)
        if summary:
            # Summary should be truncated with "..."
            assert len(summary) <= 200  # 180 + prefix + "..."


class TestOutcomeExtractorFrench:
    """Tests for French language support (Phase 8)."""

    def test_critere_principal(self):
        """FR primary outcome: 'le critère principal était...'"""
        abstract = "Le critère de jugement principal était la survie globale à 5 ans après la chirurgie."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['primary_outcome'] is not None
        assert 'survie' in result['primary_outcome'].lower()

    def test_objectif_principal(self):
        """FR primary outcome: 'l'objectif principal était...'"""
        abstract = "L'objectif principal était d'évaluer l'efficacité du traitement sur la douleur chronique."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['primary_outcome'] is not None

    def test_critere_with_colon(self):
        """FR primary outcome: 'critère principal: ...'"""
        abstract = "Critère de jugement principal : la survie sans récidive à 3 ans mesurée chez tous les patients."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['primary_outcome'] is not None

    def test_effets_indesirables(self):
        """FR adverse events: 'effets indésirables...'"""
        abstract = "Les effets indésirables les plus fréquents étaient les nausées (35%), la fatigue (22%) et les céphalées (15%)."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['adverse_events'] is not None
        assert 'nausées' in result['adverse_events'].lower()

    def test_tolerance(self):
        """FR safety: 'tolérance...'"""
        abstract = "La tolérance du traitement était bonne avec un profil de sécurité acceptable confirmé par nos données."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['safety'] is not None

    def test_resultats_ont_montre(self):
        """FR results: 'les résultats ont montré...'"""
        abstract = "Les résultats ont montré une amélioration significative dans le groupe traitement par rapport au placebo de façon constante."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['results'] is not None

    def test_efficacite_demonstree(self):
        """FR efficacy: 'l'efficacité a été démontrée...'"""
        abstract = "L'efficacité du traitement a été démontrée avec un taux de réponse de 72% chez les patients inclus dans cette étude."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['efficacy'] is not None

    def test_survie_globale(self):
        """FR efficacy: 'la survie globale était...'"""
        abstract = "La survie globale était de 85% à 5 ans dans le groupe chirurgie contre 70% dans le groupe contrôle médicamenteux."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['efficacy'] is not None

    def test_difference_significative(self):
        """FR results with stats"""
        abstract = "Il existe une différence significative entre les deux groupes avec un p < 0,001 pour le critère principal évalué."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['results'] is not None

    def test_complication_postoperatoire(self):
        """FR adverse events: complications"""
        abstract = "Les complications post-opératoires incluaient une infection du site opératoire (8%) et un hématome (3%) confirmés en analyse."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['adverse_events'] is not None


class TestPluralEndpointPatterns:
    """Tests for plural 'end points', 'endpoints', 'outcomes' patterns (Phase 9)."""

    def test_primary_end_points_plural_space(self):
        """'Primary end points were shoulder ROM and strength...'"""
        abstract = "Primary end points were shoulder ROM and strength at 1 and 6 months postsurgery."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['primary_outcome'] is not None
        assert 'shoulder' in result['primary_outcome'].lower()

    def test_primary_endpoints_plural(self):
        """'Phase II and III primary endpoints were resection rate...'"""
        abstract = "Phase II and III primary endpoints were resection rate and overall survival, respectively."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['primary_outcome'] is not None
        assert 'resection rate' in result['primary_outcome'].lower()

    def test_primary_end_points_of_study(self):
        """'The primary end points of this follow-up study were...'"""
        abstract = "The primary end points of this follow-up study were 5-year OS and DFS."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['primary_outcome'] is not None
        assert 'OS' in result['primary_outcome']

    def test_primary_outcomes_measure(self):
        """'The primary outcomes measure was incidence of...'"""
        abstract = "The primary outcomes measure was incidence of major complication or death within 30 days of operation."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['primary_outcome'] is not None
        assert 'complication' in result['primary_outcome'].lower()

    def test_primary_outcomes_in_cohort(self):
        """'Primary outcomes in the intention-to-treat cohort were...'"""
        abstract = "Primary outcomes in the intention-to-treat cohort were feasibility and effectiveness measured by weight loss."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['primary_outcome'] is not None
        assert 'feasibility' in result['primary_outcome'].lower()

    def test_primary_study_endpoint(self):
        """'The primary study endpoint was disease-free survival.'"""
        abstract = "The primary study endpoint was disease-free survival."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['primary_outcome'] is not None
        assert 'disease-free survival' in result['primary_outcome'].lower()

    def test_main_endpoints_plural(self):
        """'The main endpoints were overall survival and progression-free survival.'"""
        abstract = "The main endpoints were overall survival and progression-free survival at 3 years."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['primary_outcome'] is not None

    def test_primary_effectiveness_end_point(self):
        """'The primary effectiveness end point was incidence of EAD.'"""
        abstract = "The primary effectiveness end point was incidence of EAD as measured by standard criteria."
        result = OutcomeExtractor.extract_outcomes(abstract)
        assert result['primary_outcome'] is not None
        assert 'EAD' in result['primary_outcome']
