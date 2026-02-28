#!/usr/bin/env python
"""
test_regression_nlp.py — Tests de non-régression NLP (Niveau 3)
================================================================
Vérifie que les scores NLP ne régressent pas en-dessous de seuils minimaux.
Utilise les résultats sauvegardés du benchmark multi-spécialités comme baseline.

Usage dans pytest :
  pytest benchmarks/test_regression_nlp.py -v

Usage standalone :
  python test_regression_nlp.py [--baseline benchmark_multispecialty_717.json]

Ce test :
  1. Charge un baseline de résultats (le dernier benchmark multi-spécialités)
  2. Re-évalue les modules NLP sur les articles déjà récupérés
  3. Vérifie que les scores sont >= baseline - marge de tolérance

Note : Ce test ne contacte PAS PubMed. Il utilise les articles déjà stockés.
"""

import os
import sys
import json
import pytest
import re
from typing import Dict, Optional
from collections import Counter

# ── Django bootstrap ────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from search.services.participant_extractor import ParticipantExtractor
from search.services.outcome_extractor import OutcomeExtractor
from search.services.region_detector import get_region_from_affiliation, COUNTRY_TO_REGION

# ════════════════════════════════════════════════════════════════════════════════
# SEUILS MINIMAUX (ne doivent JAMAIS régresser en-dessous)
# ════════════════════════════════════════════════════════════════════════════════

# These are conservative floors based on multi-specialty benchmark results
THRESHOLDS = {
    'pe_f1_min': 80.0,          # ParticipantExtractor F1 >= 80%
    'pe_mae_max': 300.0,        # ParticipantExtractor MAE <= 300
    'pe_recall_min': 90.0,      # ParticipantExtractor Recall >= 90%
    'oe_f1_min': 90.0,          # OutcomeExtractor F1 >= 90%
    'oe_precision_min': 93.0,   # OutcomeExtractor Precision >= 93%
    'oe_recall_min': 85.0,      # OutcomeExtractor Recall >= 85%
    'rd_f1_min': 98.0,          # RegionDetector F1 >= 98%
    'rd_accuracy_min': 98.0,    # RegionDetector accuracy >= 98%
}

# Tolerance for comparing against a saved baseline (allow small fluctuations)
REGRESSION_TOLERANCE = 2.0  # percentage points

# ════════════════════════════════════════════════════════════════════════════════
# FILE PATHS
# ════════════════════════════════════════════════════════════════════════════════

BENCHMARKS_DIR = os.path.dirname(os.path.abspath(__file__))

def _find_latest_articles_file() -> Optional[str]:
    """Find the most recent benchmark articles JSON file."""
    candidates = []
    for f in os.listdir(BENCHMARKS_DIR):
        if f.startswith('benchmark_articles_multispecialty_') and f.endswith('.json'):
            path = os.path.join(BENCHMARKS_DIR, f)
            candidates.append((os.path.getmtime(path), path))
    if not candidates:
        # Try single-specialty articles
        for f in os.listdir(BENCHMARKS_DIR):
            if f.startswith('benchmark_articles_') and f.endswith('.json'):
                path = os.path.join(BENCHMARKS_DIR, f)
                candidates.append((os.path.getmtime(path), path))
    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][1]
    return None


def _find_latest_results_file() -> Optional[str]:
    """Find the most recent benchmark results JSON file."""
    candidates = []
    for f in os.listdir(BENCHMARKS_DIR):
        if f.startswith('benchmark_multispecialty_') and f.endswith('.json'):
            path = os.path.join(BENCHMARKS_DIR, f)
            candidates.append((os.path.getmtime(path), path))
    if candidates:
        candidates.sort(reverse=True)
        return candidates[0][1]
    return None


# ════════════════════════════════════════════════════════════════════════════════
# GS HEURISTICS (identical to benchmark_multispecialty.py)
# ════════════════════════════════════════════════════════════════════════════════

def _gs_participant_count(abstract: str) -> Optional[int]:
    if not abstract:
        return None
    m = re.search(
        r'(?:total\s+of\s+)?\d[\d,]*\s+(?:patients?|participants?|subjects?)\s+[\w\s]*?'
        r'(?:screened|assessed)[^.]*?(?:and\s+)?(\d[\d,]*)\s+(?:patients?\s+)?'
        r'(?:were\s+)?(?:included|enrolled|recruited|randomized|randomised)',
        abstract, re.IGNORECASE
    )
    if m:
        return int(m.group(1).replace(',', ''))
    m = re.search(
        r'(?:screened|assessed)\s+\d[\d,\s]*\s+\w+[^.]*?'
        r'(?:of\s+(?:whom|these|which))\s*,?\s*(\d[\d,]*)\s+(?:\w+\s+)?'
        r'(?:were\s+)?(?:included|enrolled|recruited|randomized|randomised|eligible)',
        abstract, re.IGNORECASE
    )
    if m:
        return int(m.group(1).replace(',', ''))
    m = re.search(
        r'(?:a\s+)?total\s+of\s+(\d[\d,]*)\s+(?:\w+\s+)?'
        r'(?:patients?|participants?|subjects?|individuals?|people|persons?|'
        r'women|men|children|adults?|infants?|neonates?)',
        abstract, re.IGNORECASE
    )
    if m:
        post = abstract[m.end():m.end() + 80].lower()
        if not re.search(r'(?:were\s+)?(?:screened|assessed|evaluated\s+for\s+eligibility)', post):
            return int(m.group(1).replace(',', ''))
    m = re.search(
        r'\b(\d[\d,]*)\s+(?:patients?|participants?|subjects?)\s+'
        r'(?:were|was|have been)\s+'
        r'(?:enrolled|randomized|randomised|included|recruited|analyzed|analysed|assigned)',
        abstract, re.IGNORECASE
    )
    if m:
        return int(m.group(1).replace(',', ''))
    m = re.search(
        r'(?:we|the study|this trial)\s+'
        r'(?:enrolled|randomized|randomised|included|recruited)\s+'
        r'(\d[\d,]*)\s+(?:patients?|participants?|subjects?)',
        abstract, re.IGNORECASE
    )
    if m:
        return int(m.group(1).replace(',', ''))
    arm_matches = list(re.finditer(r'[\(\[]\s*[Nn]\s*=\s*(\d[\d,]*)\s*[\)\]]', abstract))
    if len(arm_matches) >= 2:
        m1, m2 = arm_matches[0], arm_matches[1]
        if m2.start() - m1.end() < 200:
            ctx = abstract[max(0, m1.start()-100):m2.end()+50].lower()
            if any(kw in ctx for kw in ['randomiz', 'randomis', 'assigned', 'allocated', 'group', 'arm']):
                total = sum(int(am.group(1).replace(',', '')) for am in arm_matches
                            if am.start() - m1.start() < 300)
                if total >= 10:
                    return total
    m = re.search(r'\(\s*[Nn]\s*=\s*(\d[\d,]*)\s*\)', abstract)
    if m:
        return int(m.group(1).replace(',', ''))
    return None


def _gs_has_primary_outcome(abstract: str) -> bool:
    if not abstract:
        return False
    return bool(re.search(
        r'(?:primary|main)\s+(?:'
        r'out\s*comes?\b|outcomes?\b|'
        r'end\s*points?\b|endpoints?\b|'
        r'efficacy\s+end\s*points?\b|'
        r'effectiveness\s+end\s*points?\b|'
        r'safety\s+end\s*points?\b|'
        r'study\s+end\s*points?\b'
        r')',
        abstract, re.IGNORECASE
    ))


def _gs_region_from_affiliation(affiliation: str) -> str:
    if not affiliation:
        return ''
    parts = affiliation.split(',')
    if len(parts) < 2:
        return ''
    candidate = parts[-1].strip().rstrip('.').strip().lower()
    candidate = re.sub(r'[.,;]', '', candidate)
    if candidate in COUNTRY_TO_REGION:
        return COUNTRY_TO_REGION[candidate]
    gs_map = {
        'u.s.a': 'north_america', 'u.s.a.': 'north_america',
        'u.s': 'north_america', 'u.s.': 'north_america', 'usa': 'north_america',
        'u.k': 'europe', 'u.k.': 'europe',
        'england': 'europe', 'scotland': 'europe', 'wales': 'europe',
        'p.r. china': 'asia', 'p.r.china': 'asia', 'pr china': 'asia',
        'republic of korea': 'asia',
    }
    return gs_map.get(candidate, '')


# ════════════════════════════════════════════════════════════════════════════════
# EVALUATION FUNCTIONS
# ════════════════════════════════════════════════════════════════════════════════

def evaluate_pe_on_articles(articles: list) -> Dict:
    """Evaluate ParticipantExtractor on stored articles."""
    pe = ParticipantExtractor()
    errors = []
    tp = fp = fn = 0

    for art in articles:
        abstract = art.get('abstract', '')
        gs = _gs_participant_count(abstract)

        # Re-extract (not using cached value, testing CURRENT code)
        result = pe.extract_sample_size(abstract)
        pred = result.get('sample_size') if result else None

        if gs is not None and pred is not None:
            errors.append(abs(pred - gs))
            if abs(pred - gs) <= max(5, gs * 0.1):
                tp += 1
            else:
                fp += 1
        elif gs is not None and pred is None:
            fn += 1

    mae = sum(errors) / len(errors) if errors else 0
    precision = tp / (tp + fp) if (tp + fp) else 0
    recall = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0
    return {'mae': mae, 'f1': f1 * 100, 'precision': precision * 100, 'recall': recall * 100,
            'tp': tp, 'fp': fp, 'fn': fn}


def evaluate_oe_on_articles(articles: list) -> Dict:
    """Evaluate OutcomeExtractor on stored articles."""
    oe = OutcomeExtractor()
    tp = fp = fn = tn = 0

    for art in articles:
        abstract = art.get('abstract', '')
        gs_has = _gs_has_primary_outcome(abstract)
        result = oe.extract_outcomes(abstract)
        pred_has = result.get('primary_outcome') is not None if result else False

        if gs_has and pred_has:
            tp += 1
        elif gs_has and not pred_has:
            fn += 1
        elif not gs_has and pred_has:
            fp += 1
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) else 0
    recall = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) else 0
    return {'f1': f1 * 100, 'precision': precision * 100, 'recall': recall * 100,
            'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn, 'total': tp + fp + fn + tn}


def evaluate_rd_on_articles(articles: list) -> Dict:
    """Evaluate RegionDetector on stored articles."""
    tp = fp = 0
    evaluated = 0

    for art in articles:
        affiliation = art.get('affiliation', '') or art.get('last_author_affiliation', '')
        gs_region = _gs_region_from_affiliation(affiliation)
        if not gs_region:
            continue
        evaluated += 1

        # Re-extract
        pred_region = get_region_from_affiliation(affiliation)

        if pred_region == gs_region:
            tp += 1
        else:
            fp += 1

    accuracy = tp / evaluated if evaluated else 0
    f1 = accuracy * 100  # For single-class, accuracy ≈ F1
    return {'f1': f1, 'accuracy': accuracy * 100, 'tp': tp, 'mismatches': fp, 'evaluated': evaluated}


# ════════════════════════════════════════════════════════════════════════════════
# PYTEST FIXTURES & TESTS
# ════════════════════════════════════════════════════════════════════════════════

@pytest.fixture(scope="session")
def articles():
    """Load stored articles for regression testing."""
    path = _find_latest_articles_file()
    if not path:
        pytest.skip("No benchmark articles file found. Run benchmark_multispecialty.py --save-articles first.")
    with open(path, 'r', encoding='utf-8') as f:
        data = json.load(f)
    return data


@pytest.fixture(scope="session")
def baseline_results():
    """Load baseline results for comparison."""
    path = _find_latest_results_file()
    if not path:
        return None
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


class TestParticipantExtractorRegression:
    """Verify PE scores don't regress below thresholds."""

    def test_pe_f1_above_threshold(self, articles):
        result = evaluate_pe_on_articles(articles)
        assert result['f1'] >= THRESHOLDS['pe_f1_min'], \
            f"PE F1 = {result['f1']:.1f}% < threshold {THRESHOLDS['pe_f1_min']}%"

    def test_pe_mae_below_threshold(self, articles):
        result = evaluate_pe_on_articles(articles)
        assert result['mae'] <= THRESHOLDS['pe_mae_max'], \
            f"PE MAE = {result['mae']:.1f} > threshold {THRESHOLDS['pe_mae_max']}"

    def test_pe_recall_above_threshold(self, articles):
        result = evaluate_pe_on_articles(articles)
        assert result['recall'] >= THRESHOLDS['pe_recall_min'], \
            f"PE Recall = {result['recall']:.1f}% < threshold {THRESHOLDS['pe_recall_min']}%"

    def test_pe_no_major_regression_vs_baseline(self, articles, baseline_results):
        if not baseline_results:
            pytest.skip("No baseline results to compare against")
        result = evaluate_pe_on_articles(articles)
        baseline_f1 = baseline_results.get('aggregated', {}).get('participant_extractor', {}).get('f1', 0)
        assert result['f1'] >= baseline_f1 - REGRESSION_TOLERANCE, \
            f"PE F1 regressed: {result['f1']:.1f}% < baseline {baseline_f1}% - {REGRESSION_TOLERANCE}%"


class TestOutcomeExtractorRegression:
    """Verify OE scores don't regress below thresholds."""

    def test_oe_f1_above_threshold(self, articles):
        result = evaluate_oe_on_articles(articles)
        assert result['f1'] >= THRESHOLDS['oe_f1_min'], \
            f"OE F1 = {result['f1']:.1f}% < threshold {THRESHOLDS['oe_f1_min']}%"

    def test_oe_precision_above_threshold(self, articles):
        result = evaluate_oe_on_articles(articles)
        assert result['precision'] >= THRESHOLDS['oe_precision_min'], \
            f"OE Precision = {result['precision']:.1f}% < threshold {THRESHOLDS['oe_precision_min']}%"

    def test_oe_recall_above_threshold(self, articles):
        result = evaluate_oe_on_articles(articles)
        assert result['recall'] >= THRESHOLDS['oe_recall_min'], \
            f"OE Recall = {result['recall']:.1f}% < threshold {THRESHOLDS['oe_recall_min']}%"

    def test_oe_no_major_regression_vs_baseline(self, articles, baseline_results):
        if not baseline_results:
            pytest.skip("No baseline results to compare against")
        result = evaluate_oe_on_articles(articles)
        baseline_f1 = baseline_results.get('aggregated', {}).get('outcome_extractor', {}).get('f1', 0)
        assert result['f1'] >= baseline_f1 - REGRESSION_TOLERANCE, \
            f"OE F1 regressed: {result['f1']:.1f}% < baseline {baseline_f1}% - {REGRESSION_TOLERANCE}%"


class TestRegionDetectorRegression:
    """Verify RD scores don't regress below thresholds."""

    def test_rd_f1_above_threshold(self, articles):
        result = evaluate_rd_on_articles(articles)
        assert result['f1'] >= THRESHOLDS['rd_f1_min'], \
            f"RD F1 = {result['f1']:.1f}% < threshold {THRESHOLDS['rd_f1_min']}%"

    def test_rd_accuracy_above_threshold(self, articles):
        result = evaluate_rd_on_articles(articles)
        assert result['accuracy'] >= THRESHOLDS['rd_accuracy_min'], \
            f"RD Accuracy = {result['accuracy']:.1f}% < threshold {THRESHOLDS['rd_accuracy_min']}%"

    def test_rd_no_major_regression_vs_baseline(self, articles, baseline_results):
        if not baseline_results:
            pytest.skip("No baseline results to compare against")
        result = evaluate_rd_on_articles(articles)
        baseline_f1 = baseline_results.get('aggregated', {}).get('region_detector', {}).get('f1', 0)
        assert result['f1'] >= baseline_f1 - REGRESSION_TOLERANCE, \
            f"RD F1 regressed: {result['f1']:.1f}% < baseline {baseline_f1}% - {REGRESSION_TOLERANCE}%"


class TestDictionarySizes:
    """Verify dictionary sizes don't shrink (accidental deletion)."""

    def test_country_to_region_size(self):
        assert len(COUNTRY_TO_REGION) >= 220, \
            f"COUNTRY_TO_REGION has only {len(COUNTRY_TO_REGION)} entries (expected >= 220)"

    def test_primary_patterns_size(self):
        oe = OutcomeExtractor()
        assert len(oe.PRIMARY_PATTERNS) >= 40, \
            f"PRIMARY_PATTERNS has only {len(oe.PRIMARY_PATTERNS)} entries (expected >= 40)"

    def test_numeric_patterns_size(self):
        pe = ParticipantExtractor()
        assert len(pe.NUMERIC_PATTERNS) >= 35, \
            f"NUMERIC_PATTERNS has only {len(pe.NUMERIC_PATTERNS)} entries (expected >= 35)"


# ════════════════════════════════════════════════════════════════════════════════
# STANDALONE MODE
# ════════════════════════════════════════════════════════════════════════════════

def main():
    """Run regression checks standalone (without pytest)."""
    import argparse
    parser = argparse.ArgumentParser(description="NLP Regression Tests (Level 3)")
    parser.add_argument('--baseline', '-b', type=str, help='Baseline results JSON')
    parser.add_argument('--articles', '-a', type=str, help='Articles JSON file')
    args = parser.parse_args()

    # Find files
    art_path = args.articles or _find_latest_articles_file()
    if not art_path:
        print("❌ Aucun fichier d'articles trouvé. Lancez d'abord benchmark_multispecialty.py --save-articles")
        return

    baseline_path = args.baseline or _find_latest_results_file()

    print(f"\n🔄 Test de non-régression NLP (Niveau 3)")
    print(f"   Articles: {art_path}")
    if baseline_path:
        print(f"   Baseline: {baseline_path}")

    # Load data
    with open(art_path, 'r', encoding='utf-8') as f:
        articles = json.load(f)
    print(f"   {len(articles)} articles chargés\n")

    baseline = None
    if baseline_path:
        with open(baseline_path, 'r', encoding='utf-8') as f:
            baseline = json.load(f)

    # Evaluate
    print("   ⏳ Évaluation ParticipantExtractor...")
    pe = evaluate_pe_on_articles(articles)
    print("   ⏳ Évaluation OutcomeExtractor...")
    oe = evaluate_oe_on_articles(articles)
    print("   ⏳ Évaluation RegionDetector...")
    rd = evaluate_rd_on_articles(articles)

    # Check thresholds
    print(f"\n{'═' * 60}")
    print(f"  RÉSULTATS — Test de non-régression")
    print(f"{'═' * 60}")

    all_pass = True
    checks = [
        ("PE F1", pe['f1'], '>=', THRESHOLDS['pe_f1_min']),
        ("PE MAE", pe['mae'], '<=', THRESHOLDS['pe_mae_max']),
        ("PE Recall", pe['recall'], '>=', THRESHOLDS['pe_recall_min']),
        ("OE F1", oe['f1'], '>=', THRESHOLDS['oe_f1_min']),
        ("OE Precision", oe['precision'], '>=', THRESHOLDS['oe_precision_min']),
        ("OE Recall", oe['recall'], '>=', THRESHOLDS['oe_recall_min']),
        ("RD F1", rd['f1'], '>=', THRESHOLDS['rd_f1_min']),
        ("RD Accuracy", rd['accuracy'], '>=', THRESHOLDS['rd_accuracy_min']),
    ]

    for name, value, op, threshold in checks:
        if op == '>=':
            passed = value >= threshold
        else:
            passed = value <= threshold
        status = "✅ PASS" if passed else "❌ FAIL"
        if not passed:
            all_pass = False
        print(f"  {status}  {name:<15} = {value:>7.1f}  ({op} {threshold})")

    # Baseline comparison
    if baseline:
        agg = baseline.get('aggregated', {})
        print(f"\n{'─' * 60}")
        print(f"  Comparaison avec baseline (tolérance ±{REGRESSION_TOLERANCE}%)")
        print(f"{'─' * 60}")

        comparisons = [
            ("PE F1", pe['f1'], agg.get('participant_extractor', {}).get('f1', 0)),
            ("OE F1", oe['f1'], agg.get('outcome_extractor', {}).get('f1', 0)),
            ("RD F1", rd['f1'], agg.get('region_detector', {}).get('f1', 0)),
        ]
        for name, current, base_val in comparisons:
            diff = current - base_val
            passed = current >= base_val - REGRESSION_TOLERANCE
            status = "✅" if passed else "❌"
            if not passed:
                all_pass = False
            arrow = "↑" if diff > 0 else "↓" if diff < 0 else "="
            print(f"  {status}  {name:<15} = {current:>6.1f}%  (baseline: {base_val:.1f}%  {arrow} {diff:+.1f}pp)")

    # Final verdict
    print(f"\n{'═' * 60}")
    if all_pass:
        print(f"  ✅ TOUS LES TESTS PASSENT — pas de régression détectée")
    else:
        print(f"  ❌ RÉGRESSION DÉTECTÉE — vérifiez les modifications récentes")
    print(f"{'═' * 60}\n")

    return 0 if all_pass else 1


if __name__ == '__main__':
    sys.exit(main() or 0)
