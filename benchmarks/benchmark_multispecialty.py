#!/usr/bin/env python
"""
benchmark_multispecialty.py — Benchmark NLP sur 1000+ articles, 10 spécialités
==============================================================================
Niveau 1 de validation : tester les modules NLP sur un échantillon diversifié
couvrant chirurgie hépatique, cardiaque, orthopédie, neurochirurgie, pédiatrie,
oncologie chirurgicale, nursing, méta-analyses, études observationnelles, cas rares.

Usage:
  python benchmark_multispecialty.py [--per-query 100] [--output results_multi.json]
  python benchmark_multispecialty.py --load results_multi.json   # re-afficher un rapport

Produit :
  - Rapport console par spécialité + agrégé
  - JSON détaillé avec résultats par spécialité et globaux
  - Articles sauvegardés pour analyse ultérieure (Niveau 2)
"""

import os
import sys
import re
import json
import argparse
import time
from collections import Counter
from datetime import datetime
from typing import Dict, List, Optional

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
# SPECIALTY QUERIES — 10 spécialités médicales / chirurgicales
# ════════════════════════════════════════════════════════════════════════════════

SPECIALTIES = [
    {
        "id": "hepatic_surgery",
        "name": "Chirurgie hépatique",
        "query": "liver resection OR hepatectomy",
        "study_type": "randomized_controlled_trial",
    },
    {
        "id": "cardiac_surgery",
        "name": "Chirurgie cardiaque",
        "query": "cardiac surgery OR coronary artery bypass",
        "study_type": "randomized_controlled_trial",
    },
    {
        "id": "orthopedics",
        "name": "Orthopédie",
        "query": "orthopedic surgery OR joint replacement OR fracture fixation",
        "study_type": "randomized_controlled_trial",
    },
    {
        "id": "neurosurgery",
        "name": "Neurochirurgie",
        "query": "neurosurgery OR brain tumor surgery OR spinal surgery",
        "study_type": "randomized_controlled_trial",
    },
    {
        "id": "pediatric_surgery",
        "name": "Chirurgie pédiatrique",
        "query": "pediatric surgery OR neonatal surgery OR children surgical",
        "study_type": "randomized_controlled_trial",
    },
    {
        "id": "surgical_oncology",
        "name": "Oncologie chirurgicale",
        "query": "surgical oncology OR tumor resection OR cancer surgery",
        "study_type": "randomized_controlled_trial",
    },
    {
        "id": "nursing",
        "name": "Nursing / Soins infirmiers",
        "query": "nursing intervention OR nurse-led OR nursing care",
        "study_type": "randomized_controlled_trial",
    },
    {
        "id": "meta_analysis",
        "name": "Méta-analyses / Revues systématiques",
        "query": "systematic review surgery OR meta-analysis surgical",
        "study_type": "meta_analysis",
    },
    {
        "id": "observational",
        "name": "Études observationnelles",
        "query": "cohort study surgery outcome OR prospective surgical cohort",
        "study_type": "observational_study",
    },
    {
        "id": "case_series",
        "name": "Cas rares / Séries de cas",
        "query": "case series surgery OR rare surgical complication",
        "study_type": "clinical_trial",
    },
]


# ════════════════════════════════════════════════════════════════════════════════
# GOLD STANDARD HEURISTICS (same as benchmark_nlp_v2.py)
# ════════════════════════════════════════════════════════════════════════════════

def _gs_participant_count(abstract: str) -> Optional[int]:
    """GS heuristic for participant count (same logic as benchmark_nlp_v2)."""
    if not abstract:
        return None

    # PRIORITY 0: Screening → Enrollment funnels
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

    # PRIORITY 1: "A total of N patients/participants"
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

    # PRIORITY 2: "N patients were enrolled/randomized"
    m = re.search(
        r'\b(\d[\d,]*)\s+(?:patients?|participants?|subjects?)\s+'
        r'(?:were|was|have been)\s+'
        r'(?:enrolled|randomized|randomised|included|recruited|analyzed|analysed|assigned)',
        abstract, re.IGNORECASE
    )
    if m:
        return int(m.group(1).replace(',', ''))

    # PRIORITY 3: "We enrolled/randomized N patients"
    m = re.search(
        r'(?:we|the study|this trial)\s+'
        r'(?:enrolled|randomized|randomised|included|recruited)\s+'
        r'(\d[\d,]*)\s+(?:patients?|participants?|subjects?)',
        abstract, re.IGNORECASE
    )
    if m:
        return int(m.group(1).replace(',', ''))

    # PRIORITY 4: Multi-arm sum "(n = X) ... (n = Y)"
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

    # PRIORITY 5: "(N = 123)" fallback
    m = re.search(r'\(\s*[Nn]\s*=\s*(\d[\d,]*)\s*\)', abstract)
    if m:
        return int(m.group(1).replace(',', ''))

    return None


def _gs_has_primary_outcome(abstract: str) -> bool:
    """GS: does abstract mention a primary outcome/endpoint?"""
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
    """GS region using explicit country name at end of affiliation."""
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
    if candidate in gs_map:
        return gs_map[candidate]
    return ''


# ════════════════════════════════════════════════════════════════════════════════
# FETCH & EVALUATE
# ════════════════════════════════════════════════════════════════════════════════

def fetch_articles(query: str, n: int, study_type: str = "randomized_controlled_trial",
                   batch_size: int = 50) -> List[Dict]:
    """Fetch N articles from PubMed in batches."""
    articles = []
    start = 0
    while len(articles) < n:
        size = min(batch_size, n - len(articles))
        try:
            total, batch = search_pubmed(
                term=query, start=start, size=size,
                study_type=study_type,
            )
        except Exception as e:
            print(f"    ⚠ Error at offset {start}: {e}")
            break
        if not batch:
            print(f"    ⚠ No more articles at offset {start} (total={total})")
            break
        articles.extend(batch)
        start += size
        time.sleep(0.35)  # Rate limit
    return articles[:n]


def evaluate_pe(articles: List[Dict]) -> Dict:
    """Evaluate ParticipantExtractor."""
    errors = []
    tp = fp = fn = tn = 0
    details = []

    for art in articles:
        abstract = art.get('abstract', '')
        gs = _gs_participant_count(abstract)
        pred = art.get('sample_size')

        if gs is not None and pred is not None:
            errors.append(abs(pred - gs))
            if abs(pred - gs) <= max(5, gs * 0.1):
                tp += 1
            else:
                fp += 1
                details.append({
                    'pmid': art.get('pmid'), 'gs': gs, 'pred': pred,
                    'error': abs(pred - gs),
                })
        elif gs is not None and pred is None:
            fn += 1
        elif gs is None and pred is not None:
            pass
        else:
            tn += 1

    mae = sum(errors) / len(errors) if errors else 0
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        'mae': round(mae, 1), 'f1': round(f1 * 100, 1),
        'precision': round(precision * 100, 1), 'recall': round(recall * 100, 1),
        'evaluated': len(errors), 'tp': tp, 'fp': fp, 'fn': fn,
        'worst_errors': sorted(details, key=lambda x: -x['error'])[:10],
    }


def evaluate_oe(articles: List[Dict]) -> Dict:
    """Evaluate OutcomeExtractor."""
    tp = fp = fn = tn = 0
    for art in articles:
        abstract = art.get('abstract', '')
        gs_has = _gs_has_primary_outcome(abstract)
        pred_has = art.get('primary_outcome') is not None
        if gs_has and pred_has:
            tp += 1
        elif gs_has and not pred_has:
            fn += 1
        elif not gs_has and pred_has:
            fp += 1
        else:
            tn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        'f1': round(f1 * 100, 1),
        'precision': round(precision * 100, 1), 'recall': round(recall * 100, 1),
        'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
        'total': tp + fp + fn + tn,
    }


def evaluate_rd(articles: List[Dict]) -> Dict:
    """Evaluate RegionDetector."""
    tp = fp = fn = 0
    evaluated = 0
    region_counts = Counter()

    for art in articles:
        affiliation = art.get('affiliation', '') or art.get('last_author_affiliation', '')
        gs_region = _gs_region_from_affiliation(affiliation)
        pred_region = art.get('region', '')
        if not gs_region:
            continue
        evaluated += 1
        region_counts[gs_region] += 1
        if pred_region == gs_region:
            tp += 1
        else:
            fp += 1
            fn += 1

    precision = tp / (tp + fp) if (tp + fp) > 0 else 0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0

    return {
        'f1': round(f1 * 100, 1),
        'precision': round(precision * 100, 1), 'recall': round(recall * 100, 1),
        'evaluated': evaluated, 'tp': tp, 'mismatches': fp,
        'region_distribution': dict(region_counts.most_common()),
    }


# ════════════════════════════════════════════════════════════════════════════════
# AGGREGATION
# ════════════════════════════════════════════════════════════════════════════════

def aggregate_results(specialty_results: List[Dict]) -> Dict:
    """Aggregate metrics across all specialties (weighted by sample size)."""
    # PE aggregation
    pe_errors_total = 0
    pe_errors_count = 0
    pe_tp = pe_fp = pe_fn = 0
    pe_worst = []

    # OE aggregation
    oe_tp = oe_fp = oe_fn = oe_tn = 0

    # RD aggregation
    rd_tp = rd_fp = rd_fn = 0
    rd_evaluated = 0
    rd_regions = Counter()

    for sr in specialty_results:
        pe = sr['participant_extractor']
        pe_errors_total += pe['mae'] * pe['evaluated'] if pe['evaluated'] else 0
        pe_errors_count += pe['evaluated']
        pe_tp += pe['tp']
        pe_fp += pe['fp']
        pe_fn += pe['fn']
        pe_worst.extend(pe.get('worst_errors', []))

        oe = sr['outcome_extractor']
        oe_tp += oe['tp']
        oe_fp += oe['fp']
        oe_fn += oe['fn']
        oe_tn += oe['tn']

        rd = sr['region_detector']
        rd_tp += rd['tp']
        rd_fp += rd['mismatches']
        rd_fn += rd['mismatches']
        rd_evaluated += rd['evaluated']
        for region, count in rd.get('region_distribution', {}).items():
            rd_regions[region] += count

    # Compute aggregated metrics
    pe_mae = pe_errors_total / pe_errors_count if pe_errors_count else 0
    pe_prec = pe_tp / (pe_tp + pe_fp) if (pe_tp + pe_fp) else 0
    pe_rec = pe_tp / (pe_tp + pe_fn) if (pe_tp + pe_fn) else 0
    pe_f1 = 2 * pe_prec * pe_rec / (pe_prec + pe_rec) if (pe_prec + pe_rec) else 0

    oe_prec = oe_tp / (oe_tp + oe_fp) if (oe_tp + oe_fp) else 0
    oe_rec = oe_tp / (oe_tp + oe_fn) if (oe_tp + oe_fn) else 0
    oe_f1 = 2 * oe_prec * oe_rec / (oe_prec + oe_rec) if (oe_prec + oe_rec) else 0

    rd_prec = rd_tp / (rd_tp + rd_fp) if (rd_tp + rd_fp) else 0
    rd_rec = rd_tp / (rd_tp + rd_fn) if (rd_tp + rd_fn) else 0
    rd_f1 = 2 * rd_prec * rd_rec / (rd_prec + rd_rec) if (rd_prec + rd_rec) else 0

    return {
        'participant_extractor': {
            'mae': round(pe_mae, 1),
            'f1': round(pe_f1 * 100, 1),
            'precision': round(pe_prec * 100, 1),
            'recall': round(pe_rec * 100, 1),
            'evaluated': pe_errors_count,
            'tp': pe_tp, 'fp': pe_fp, 'fn': pe_fn,
            'worst_errors': sorted(pe_worst, key=lambda x: -x['error'])[:15],
        },
        'outcome_extractor': {
            'f1': round(oe_f1 * 100, 1),
            'precision': round(oe_prec * 100, 1),
            'recall': round(oe_rec * 100, 1),
            'tp': oe_tp, 'fp': oe_fp, 'fn': oe_fn, 'tn': oe_tn,
            'total': oe_tp + oe_fp + oe_fn + oe_tn,
        },
        'region_detector': {
            'f1': round(rd_f1 * 100, 1),
            'precision': round(rd_prec * 100, 1),
            'recall': round(rd_rec * 100, 1),
            'evaluated': rd_evaluated,
            'tp': rd_tp, 'mismatches': rd_fp,
            'region_distribution': dict(rd_regions.most_common()),
        },
    }


# ════════════════════════════════════════════════════════════════════════════════
# REPORT PRINTER
# ════════════════════════════════════════════════════════════════════════════════

def print_specialty_report(spec_name: str, n_articles: int, pe: Dict, oe: Dict, rd: Dict):
    """Print a compact one-specialty report."""
    print(f"\n  ┌── {spec_name} ({n_articles} articles) ──")
    print(f"  │ PE: MAE={pe['mae']:<7} F1={pe['f1']:>5}%  (TP={pe['tp']} FP={pe['fp']} FN={pe['fn']}, eval={pe['evaluated']})")
    print(f"  │ OE: F1={oe['f1']:>5}%  P={oe['precision']}% R={oe['recall']}%  (TP={oe['tp']} FP={oe['fp']} FN={oe['fn']} TN={oe['tn']})")
    print(f"  │ RD: F1={rd['f1']:>5}%  ({rd['tp']}/{rd['evaluated']} correct)")
    print(f"  └{'─' * 60}")


def print_full_report(results: Dict):
    """Print full multi-specialty report."""
    meta = results['meta']
    print("\n" + "═" * 72)
    print("  BENCHMARK MULTI-SPÉCIALITÉS — NIVEAU 1")
    print("═" * 72)
    print(f"  Date:         {meta['date']}")
    print(f"  Spécialités:  {meta['specialty_count']}")
    print(f"  Articles:     {meta['total_articles']}")
    print(f"  Durée:        {meta['duration_sec']}s ({meta['duration_sec']/60:.1f} min)")
    print("═" * 72)

    # Per-specialty table
    print(f"\n{'─' * 72}")
    print(f"  {'Spécialité':<35} {'Articles':>8} {'PE F1':>7} {'OE F1':>7} {'RD F1':>7}")
    print(f"{'─' * 72}")

    for sr in results['specialties']:
        name = sr['name'][:34]
        n = sr['article_count']
        pe_f1 = sr['participant_extractor']['f1']
        oe_f1 = sr['outcome_extractor']['f1']
        rd_f1 = sr['region_detector']['f1']
        print(f"  {name:<35} {n:>8} {pe_f1:>6}% {oe_f1:>6}% {rd_f1:>6}%")

    # Aggregated results
    agg = results['aggregated']
    pe = agg['participant_extractor']
    oe = agg['outcome_extractor']
    rd = agg['region_detector']

    print(f"{'─' * 72}")
    print(f"  {'GLOBAL (agrégé)':<35} {meta['total_articles']:>8} {pe['f1']:>6}% {oe['f1']:>6}% {rd['f1']:>6}%")
    print(f"{'═' * 72}")

    # Detailed aggregated
    print(f"\n📊 RÉSULTATS AGRÉGÉS")
    print(f"   ParticipantExtractor:")
    print(f"     MAE = {pe['mae']}  |  F1 = {pe['f1']}%  |  P = {pe['precision']}%  R = {pe['recall']}%")
    print(f"     TP={pe['tp']}  FP={pe['fp']}  FN={pe['fn']}  (évalués: {pe['evaluated']})")
    print(f"   OutcomeExtractor:")
    print(f"     F1 = {oe['f1']}%  |  P = {oe['precision']}%  R = {oe['recall']}%")
    print(f"     TP={oe['tp']}  FP={oe['fp']}  FN={oe['fn']}  TN={oe['tn']}  (total: {oe['total']})")
    print(f"   RegionDetector:")
    print(f"     F1 = {rd['f1']}%  |  {rd['tp']}/{rd['evaluated']} correct")
    print(f"     Régions: {rd.get('region_distribution', {})}")

    # Worst PE errors across all specialties
    if pe.get('worst_errors'):
        print(f"\n   Top erreurs PE (toutes spécialités):")
        for e in pe['worst_errors'][:10]:
            print(f"     PMID {e['pmid']}: GS={e['gs']} pred={e['pred']} (Δ={e['error']})")

    # Confidence intervals (Wilson score approximation)
    print(f"\n📐 INTERVALLES DE CONFIANCE (95%)")
    for name, metric, n_total in [
        ("PE F1", pe['f1'] / 100, pe['tp'] + pe['fp'] + pe['fn']),
        ("OE F1", oe['f1'] / 100, oe['total']),
        ("RD F1", rd['f1'] / 100, rd['evaluated']),
    ]:
        if n_total > 0 and 0 < metric < 1:
            import math
            se = math.sqrt(metric * (1 - metric) / n_total)
            lo = max(0, metric - 1.96 * se) * 100
            hi = min(1, metric + 1.96 * se) * 100
            print(f"   {name}: {metric*100:.1f}% ± {1.96*se*100:.1f}%  (IC95: [{lo:.1f}%, {hi:.1f}%], n={n_total})")
        else:
            print(f"   {name}: {metric*100:.1f}% (n={n_total})")

    print()


# ════════════════════════════════════════════════════════════════════════════════
# MAIN
# ════════════════════════════════════════════════════════════════════════════════

def main():
    parser = argparse.ArgumentParser(description="Multi-specialty NLP benchmark (Level 1)")
    parser.add_argument('--per-query', '-n', type=int, default=100,
                        help='Articles per specialty (default: 100)')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output JSON file (default: benchmark_multispecialty_{total}.json)')
    parser.add_argument('--load', '-l', type=str,
                        help='Load previous results JSON')
    parser.add_argument('--save-articles', action='store_true',
                        help='Save all fetched articles for Level 2 annotation')
    parser.add_argument('--specialties', '-s', type=str, default=None,
                        help='Comma-separated specialty IDs to run (default: all)')
    args = parser.parse_args()

    if args.load:
        print(f"\n📂 Loading results from {args.load}")
        with open(args.load, 'r', encoding='utf-8') as f:
            results = json.load(f)
        print_full_report(results)
        return

    # Filter specialties if requested
    specs = SPECIALTIES
    if args.specialties:
        ids = [s.strip() for s in args.specialties.split(',')]
        specs = [s for s in SPECIALTIES if s['id'] in ids]
        if not specs:
            print(f"❌ No matching specialties. Available: {[s['id'] for s in SPECIALTIES]}")
            return

    print(f"\n{'═' * 72}")
    print(f"  BENCHMARK MULTI-SPÉCIALITÉS — NIVEAU 1")
    print(f"  {len(specs)} spécialités × {args.per_query} articles = {len(specs) * args.per_query} articles")
    print(f"{'═' * 72}")

    t0_global = time.time()
    all_specialty_results = []
    all_articles = []

    for i, spec in enumerate(specs, 1):
        print(f"\n{'─' * 72}")
        print(f"  [{i}/{len(specs)}] {spec['name']}")
        print(f"  Query: \"{spec['query']}\"  |  Type: {spec['study_type']}")
        print(f"{'─' * 72}")

        # Fetch
        t0 = time.time()
        articles = fetch_articles(spec['query'], args.per_query, spec['study_type'])
        fetch_time = time.time() - t0

        if not articles:
            print(f"  ⚠ Aucun article récupéré pour {spec['name']}, skip")
            continue

        print(f"  ✓ {len(articles)} articles récupérés en {fetch_time:.1f}s")

        # Evaluate
        pe = evaluate_pe(articles)
        oe = evaluate_oe(articles)
        rd = evaluate_rd(articles)

        spec_result = {
            'id': spec['id'],
            'name': spec['name'],
            'query': spec['query'],
            'study_type': spec['study_type'],
            'article_count': len(articles),
            'fetch_time_sec': round(fetch_time, 1),
            'participant_extractor': pe,
            'outcome_extractor': oe,
            'region_detector': rd,
        }
        all_specialty_results.append(spec_result)

        if args.save_articles:
            for art in articles:
                art['_specialty'] = spec['id']
            all_articles.extend(articles)

        print_specialty_report(spec['name'], len(articles), pe, oe, rd)

    if not all_specialty_results:
        print("❌ Aucun résultat. Vérifiez la connexion et la clé NCBI_API_KEY.")
        return

    # Aggregate
    aggregated = aggregate_results(all_specialty_results)
    total_time = time.time() - t0_global
    total_articles = sum(sr['article_count'] for sr in all_specialty_results)

    results = {
        'meta': {
            'date': datetime.now().isoformat(),
            'total_articles': total_articles,
            'specialty_count': len(all_specialty_results),
            'per_query_target': args.per_query,
            'duration_sec': round(total_time, 1),
        },
        'specialties': all_specialty_results,
        'aggregated': aggregated,
    }

    print_full_report(results)

    # Save results
    outfile = args.output or f"benchmark_multispecialty_{total_articles}.json"
    with open(outfile, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"💾 Résultats sauvegardés: {outfile}")

    # Save articles if requested
    if args.save_articles and all_articles:
        art_file = f"benchmark_articles_multispecialty_{total_articles}.json"
        with open(art_file, 'w', encoding='utf-8') as f:
            json.dump(all_articles, f, indent=2, ensure_ascii=False, default=str)
        print(f"💾 Articles sauvegardés: {art_file} (pour annotation Niveau 2)")

    print(f"\n✅ Benchmark terminé en {total_time/60:.1f} minutes\n")


if __name__ == '__main__':
    main()
