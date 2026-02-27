#!/usr/bin/env python
"""
benchmark_nlp_v2.py — Benchmark des 3 modules NLP de MedSearch
================================================================
Récupère N articles réels depuis PubMed, extrait les métriques NLP,
calcule des gold-standard heuristiques, et évalue la précision.

Modules testés:
  1. ParticipantExtractor  → MAE (Mean Absolute Error)
  2. OutcomeExtractor      → F1-score (primary outcome detection)
  3. RegionDetector        → F1-score (country/region detection)

Usage:
  python benchmark_nlp_v2.py [--articles 150] [--query "liver resection"]
  python benchmark_nlp_v2.py --load results.json   # re-score from saved results

Résultats sauvegardés dans benchmark_results_v2_{N}.json
"""

import os
import sys
import re
import json
import argparse
import time
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional, Tuple

# ── Django bootstrap ────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from search.services.participant_extractor import ParticipantExtractor
from search.services.outcome_extractor import OutcomeExtractor
from search.services.region_detector import (
    get_region_from_affiliation, get_country_code, get_country_name,
    COUNTRY_TO_REGION, TLD_TO_COUNTRY, CITY_TO_COUNTRY,
)
from search.services.pubmed_client import search_pubmed


# ════════════════════════════════════════════════════════════════════════════════
# GOLD STANDARD HEURISTICS
# ════════════════════════════════════════════════════════════════════════════════

def _gs_participant_count(abstract: str) -> Optional[int]:
    """
    Heuristic gold-standard for participant count.
    Uses very conservative regex to avoid false positives.
    Distinguishes screening/assessment counts from actual enrollment.
    Returns None if uncertain.
    """
    if not abstract:
        return None

    # ── PRIORITY 0: Screening → Enrollment funnels ──
    # "total of 3971 patients were assessed, and 217 were enrolled"
    m = re.search(
        r'(?:total\s+of\s+)?\d[\d,]*\s+(?:patients?|participants?|subjects?)\s+[\w\s]*?(?:screened|assessed)[^.]*?(?:and\s+)?(\d[\d,]*)\s+(?:patients?\s+)?(?:were\s+)?(?:included|enrolled|recruited|randomized|randomised)',
        abstract, re.IGNORECASE
    )
    if m:
        return int(m.group(1).replace(',', ''))

    # "screened X patients, of whom Y were included/enrolled"
    m = re.search(
        r'(?:screened|assessed)\s+\d[\d,\s]*\s+\w+[^.]*?(?:of\s+(?:whom|these|which))\s*,?\s*(\d[\d,]*)\s+(?:\w+\s+)?(?:were\s+)?(?:included|enrolled|recruited|randomized|randomised|eligible)',
        abstract, re.IGNORECASE
    )
    if m:
        return int(m.group(1).replace(',', ''))

    # ── PRIORITY 1: "A total of N patients/participants" ──
    # But NOT if followed by "were screened/assessed"
    m = re.search(
        r'(?:a\s+)?total\s+of\s+(\d[\d,]*)\s+(?:patients?|participants?|subjects?|individuals?|people|persons?|women|men|children|adults?|infants?|neonates?)',
        abstract, re.IGNORECASE
    )
    if m:
        # Check if this is a screening number
        post = abstract[m.end():m.end() + 80].lower()
        if not re.search(r'(?:were\s+)?(?:screened|assessed|evaluated\s+for\s+eligibility)', post):
            return int(m.group(1).replace(',', ''))

    # ── PRIORITY 2: "N patients were enrolled/randomized/included" ──
    # Exclude "were screened"
    m = re.search(
        r'\b(\d[\d,]*)\s+(?:patients?|participants?|subjects?)\s+(?:were|was|have been)\s+(?:enrolled|randomized|randomised|included|recruited|analyzed|analysed|assigned)',
        abstract, re.IGNORECASE
    )
    if m:
        return int(m.group(1).replace(',', ''))

    # ── PRIORITY 3: "We enrolled/randomized N patients" ──
    m = re.search(
        r'(?:we|the study|this trial)\s+(?:enrolled|randomized|randomised|included|recruited)\s+(\d[\d,]*)\s+(?:patients?|participants?|subjects?)',
        abstract, re.IGNORECASE
    )
    if m:
        return int(m.group(1).replace(',', ''))

    # ── PRIORITY 4: Multi-arm sum "(n = X) ... (n = Y)" ──
    arm_matches = list(re.finditer(r'[\(\[]\s*[Nn]\s*=\s*(\d[\d,]*)\s*[\)\]]', abstract))
    if len(arm_matches) >= 2:
        # Check if arms are close together and in randomization context
        m1, m2 = arm_matches[0], arm_matches[1]
        if m2.start() - m1.end() < 200:
            ctx = abstract[max(0, m1.start()-100):m2.end()+50].lower()
            if any(kw in ctx for kw in ['randomiz', 'randomis', 'assigned', 'allocated', 'group', 'arm']):
                total = sum(int(am.group(1).replace(',', '')) for am in arm_matches
                            if am.start() - m1.start() < 300)
                if total >= 10:
                    return total

    # ── PRIORITY 5: "(N = 123)" fallback ──
    m = re.search(r'\(\s*[Nn]\s*=\s*(\d[\d,]*)\s*\)', abstract)
    if m:
        return int(m.group(1).replace(',', ''))

    return None


def _gs_has_primary_outcome(abstract: str) -> bool:
    """
    Gold-standard: does this abstract explicitly mention a primary outcome/endpoint?
    Very strict matching to minimize false positives in the GS itself.
    """
    if not abstract:
        return False
    lower = abstract.lower()
    return bool(re.search(
        r'primary\s+(?:out\s*come|endpoint|end\s*point|efficacy\s+endpoint)',
        lower
    ))


def _gs_region_from_affiliation(affiliation: str) -> str:
    """
    Gold-standard region using explicit country name at end of affiliation.
    Uses strict end-of-string matching to avoid ambiguity.
    Returns region code or '' if unknown.
    """
    if not affiliation:
        return ''

    # Try to extract country from the last part after the last comma
    parts = affiliation.split(',')
    if len(parts) < 2:
        return ''

    candidate = parts[-1].strip().rstrip('.').strip().lower()
    candidate = re.sub(r'[.,;]', '', candidate)

    # Direct lookup in COUNTRY_TO_REGION
    if candidate in COUNTRY_TO_REGION:
        return COUNTRY_TO_REGION[candidate]

    # Common abbreviations
    gs_map = {
        'u.s.a': 'north_america', 'u.s.a.': 'north_america',
        'u.s': 'north_america', 'u.s.': 'north_america',
        'usa': 'north_america',
        'u.k': 'europe', 'u.k.': 'europe',
        'england': 'europe', 'scotland': 'europe', 'wales': 'europe',
        'p.r. china': 'asia', 'p.r.china': 'asia', 'pr china': 'asia',
        'republic of korea': 'asia',
    }
    if candidate in gs_map:
        return gs_map[candidate]

    return ''


# ════════════════════════════════════════════════════════════════════════════════
# BENCHMARK ENGINE
# ════════════════════════════════════════════════════════════════════════════════

def fetch_articles(query: str, n: int, batch_size: int = 50) -> List[Dict]:
    """Fetch N articles from PubMed in batches."""
    articles = []
    start = 0
    print(f"\n📡 Fetching {n} articles from PubMed: \"{query}\"")
    while len(articles) < n:
        size = min(batch_size, n - len(articles))
        try:
            total, batch = search_pubmed(
                term=query, start=start, size=size,
                study_type="randomized_controlled_trial",
            )
        except Exception as e:
            print(f"  ⚠ Error at offset {start}: {e}")
            break

        if not batch:
            print(f"  ⚠ No more articles at offset {start} (total={total})")
            break

        articles.extend(batch)
        start += size
        pct = min(100, len(articles) * 100 // n)
        print(f"  [{pct:3d}%] Got {len(articles)}/{n} articles (PubMed total: {total})")
        time.sleep(0.35)  # Respect rate limits

    return articles[:n]


def evaluate_participant_extractor(articles: List[Dict]) -> Dict:
    """Evaluate ParticipantExtractor against GS heuristic."""
    errors = []
    tp = fp = fn = tn = 0
    details = []

    for art in articles:
        abstract = art.get('abstract', '')
        gs = _gs_participant_count(abstract)
        pred = art.get('sample_size')

        if gs is not None and pred is not None:
            errors.append(abs(pred - gs))
            if abs(pred - gs) <= max(5, gs * 0.1):  # Within 10% or 5
                tp += 1
            else:
                fp += 1
                details.append({
                    'pmid': art.get('pmid'),
                    'gs': gs, 'pred': pred,
                    'error': abs(pred - gs),
                    'snippet': abstract[:120],
                })
        elif gs is not None and pred is None:
            fn += 1
        elif gs is None and pred is not None:
            # Can't evaluate — GS unsure
            pass
        else:
            tn += 1

    mae = sum(errors) / len(errors) if errors else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        'mae': round(mae, 1),
        'precision': round(precision * 100, 1),
        'recall': round(recall * 100, 1),
        'f1': round(f1 * 100, 1),
        'evaluated': len(errors),
        'tp': tp, 'fp': fp, 'fn': fn,
        'worst_errors': sorted(details, key=lambda x: -x['error'])[:10],
    }


def evaluate_outcome_extractor(articles: List[Dict]) -> Dict:
    """Evaluate OutcomeExtractor primary outcome detection against GS."""
    tp = fp = fn = tn = 0
    details_fp = []
    details_fn = []

    for art in articles:
        abstract = art.get('abstract', '')
        gs_has = _gs_has_primary_outcome(abstract)
        pred_has = art.get('primary_outcome') is not None

        if gs_has and pred_has:
            tp += 1
        elif gs_has and not pred_has:
            fn += 1
            details_fn.append({
                'pmid': art.get('pmid'),
                'snippet': abstract[:200],
            })
        elif not gs_has and pred_has:
            fp += 1
            details_fp.append({
                'pmid': art.get('pmid'),
                'prediction': str(art.get('primary_outcome', ''))[:150],
                'snippet': abstract[:200],
            })
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        'precision': round(precision * 100, 1),
        'recall': round(recall * 100, 1),
        'f1': round(f1 * 100, 1),
        'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
        'total': tp + fp + fn + tn,
        'false_positives': details_fp[:10],
        'false_negatives': details_fn[:10],
    }


def evaluate_region_detector(articles: List[Dict]) -> Dict:
    """Evaluate RegionDetector against GS from affiliation end-of-string."""
    tp = fp = fn = 0
    evaluated = 0
    region_counts = Counter()
    details = []

    for art in articles:
        affiliation = art.get('affiliation', '') or art.get('last_author_affiliation', '')
        gs_region = _gs_region_from_affiliation(affiliation)
        pred_region = art.get('region', '')

        if not gs_region:
            continue  # Can't evaluate without GS

        evaluated += 1
        region_counts[gs_region] += 1

        if pred_region == gs_region:
            tp += 1
        else:
            fp += 1
            fn += 1
            details.append({
                'pmid': art.get('pmid'),
                'gs_region': gs_region,
                'pred_region': pred_region or '(empty)',
                'affiliation': affiliation[:150],
            })

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        'precision': round(precision * 100, 1),
        'recall': round(recall * 100, 1),
        'f1': round(f1 * 100, 1),
        'evaluated': evaluated,
        'tp': tp, 'mismatches': fp,
        'region_distribution': dict(region_counts.most_common()),
        'errors': details[:15],
    }


def print_report(results: Dict):
    """Print a formatted benchmark report."""
    print("\n" + "=" * 70)
    print("  BENCHMARK NLP v2 — RÉSULTATS")
    print("=" * 70)
    print(f"  Date:     {results['meta']['date']}")
    print(f"  Articles: {results['meta']['article_count']}")
    print(f"  Query:    {results['meta']['query']}")
    print(f"  Duration: {results['meta']['duration_sec']}s")
    print("=" * 70)

    # Participant Extractor
    pe = results['participant_extractor']
    print(f"\n📊 ParticipantExtractor")
    print(f"   MAE:       {pe['mae']}")
    print(f"   F1:        {pe['f1']}%")
    print(f"   Precision: {pe['precision']}%  |  Recall: {pe['recall']}%")
    print(f"   Evaluated: {pe['evaluated']} (TP={pe['tp']} FP={pe['fp']} FN={pe['fn']})")
    if pe.get('worst_errors'):
        print(f"   Top errors:")
        for e in pe['worst_errors'][:5]:
            print(f"     PMID {e['pmid']}: GS={e['gs']} pred={e['pred']} (Δ={e['error']})")

    # Outcome Extractor
    oe = results['outcome_extractor']
    print(f"\n📊 OutcomeExtractor")
    print(f"   F1:        {oe['f1']}%")
    print(f"   Precision: {oe['precision']}%  |  Recall: {oe['recall']}%")
    print(f"   TP={oe['tp']} FP={oe['fp']} FN={oe['fn']} TN={oe['tn']} (total={oe['total']})")
    if oe.get('false_positives'):
        print(f"   False positives:")
        for e in oe['false_positives'][:3]:
            print(f"     PMID {e['pmid']}: {e['prediction'][:80]}")
    if oe.get('false_negatives'):
        print(f"   False negatives:")
        for e in oe['false_negatives'][:3]:
            print(f"     PMID {e['pmid']}: {e['snippet'][:80]}...")

    # Region Detector
    rd = results['region_detector']
    print(f"\n📊 RegionDetector")
    print(f"   F1:         {rd['f1']}%")
    print(f"   Precision:  {rd['precision']}%  |  Recall: {rd['recall']}%")
    print(f"   Evaluated:  {rd['evaluated']} (correct={rd['tp']} mismatches={rd['mismatches']})")
    print(f"   Regions:    {rd.get('region_distribution', {})}")
    if rd.get('errors'):
        print(f"   Mismatches:")
        for e in rd['errors'][:5]:
            print(f"     PMID {e['pmid']}: GS={e['gs_region']} pred={e['pred_region']}")
            print(f"       {e['affiliation'][:100]}")

    # Summary
    print(f"\n{'─' * 70}")
    print(f"  RÉSUMÉ:")
    print(f"    ParticipantExtractor  MAE = {pe['mae']:<8}  F1 = {pe['f1']}%")
    print(f"    OutcomeExtractor      F1  = {oe['f1']}%")
    print(f"    RegionDetector        F1  = {rd['f1']}%")
    print(f"{'─' * 70}\n")


# ════════════════════════════════════════════════════════════════════════════════
# DICTIONARIES STATS
# ════════════════════════════════════════════════════════════════════════════════

def print_dict_stats():
    """Print current dictionary sizes."""
    print("\n📦 Dictionaries:")
    print(f"   COUNTRY_TO_REGION:    {len(COUNTRY_TO_REGION)} entries")
    print(f"   TLD_TO_COUNTRY:       {len(TLD_TO_COUNTRY)} entries")
    print(f"   CITY_TO_COUNTRY:      {len(CITY_TO_COUNTRY)} entries")
    regions = Counter(COUNTRY_TO_REGION.values())
    for r in sorted(regions):
        print(f"     {r}: {regions[r]}")
    

    pe = ParticipantExtractor()
    print(f"   NUMERIC_PATTERNS:     {len(pe.NUMERIC_PATTERNS)}")
    print(f"   WRITTEN_PATTERNS:     {len(pe.WRITTEN_PATTERNS)}")
    
    oe = OutcomeExtractor()
    print(f"   PRIMARY_PATTERNS:     {len(oe.PRIMARY_PATTERNS)}")


# ════════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Benchmark NLP modules on real PubMed articles")
    parser.add_argument('--articles', '-n', type=int, default=150, help='Number of articles to fetch (default: 150)')
    parser.add_argument('--query', '-q', type=str, default='liver resection OR hepatectomy',
                        help='PubMed search query')
    parser.add_argument('--load', '-l', type=str, help='Load previous results JSON instead of fetching')
    parser.add_argument('--save-articles', action='store_true', help='Also save raw article data')
    parser.add_argument('--stats-only', action='store_true', help='Only show dictionary stats')
    args = parser.parse_args()

    print_dict_stats()

    if args.stats_only:
        return

    if args.load:
        print(f"\n📂 Loading results from {args.load}")
        with open(args.load, 'r', encoding='utf-8') as f:
            results = json.load(f)
        print_report(results)
        return

    # Fetch articles
    t0 = time.time()
    articles = fetch_articles(args.query, args.articles)
    fetch_time = time.time() - t0

    if not articles:
        print("❌ No articles fetched. Check your NCBI_API_KEY and network connection.")
        return

    print(f"\n⏱  Fetched {len(articles)} articles in {fetch_time:.1f}s")

    # Evaluate
    t0 = time.time()
    pe_results = evaluate_participant_extractor(articles)
    oe_results = evaluate_outcome_extractor(articles)
    rd_results = evaluate_region_detector(articles)
    eval_time = time.time() - t0

    results = {
        'meta': {
            'date': datetime.now().isoformat(),
            'article_count': len(articles),
            'query': args.query,
            'duration_sec': round(fetch_time + eval_time, 1),
            'dictionaries': {
                'COUNTRY_TO_REGION': len(COUNTRY_TO_REGION),
                'TLD_TO_COUNTRY': len(TLD_TO_COUNTRY),
                'CITY_TO_COUNTRY': len(CITY_TO_COUNTRY),
            },
        },
        'participant_extractor': pe_results,
        'outcome_extractor': oe_results,
        'region_detector': rd_results,
    }

    # Print report
    print_report(results)

    # Save results
    outfile = f"benchmark_results_v2_{len(articles)}.json"
    with open(outfile, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"💾 Results saved to {outfile}")

    # Optionally save raw articles
    if args.save_articles:
        art_file = f"benchmark_articles_{len(articles)}.json"
        with open(art_file, 'w', encoding='utf-8') as f:
            json.dump(articles, f, indent=2, ensure_ascii=False, default=str)
        print(f"💾 Articles saved to {art_file}")


if __name__ == '__main__':
    main()
