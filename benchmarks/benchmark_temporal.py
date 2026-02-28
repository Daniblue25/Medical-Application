#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
benchmark_temporal.py — Benchmark NLP par décennie (2000-2025)
===============================================================
Vérifie que les modules NLP fonctionnent aussi bien sur des articles
anciens que récents. Le style d'écriture des abstracts PubMed évolue
avec le temps, ce test détecte un éventuel biais temporel.

Usage:
  python benchmark_temporal.py [--per-period 30] [--output results_temporal.json]

Produit :
  - Rapport console par période + agrégé
  - JSON avec résultats par période
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

# -- Django bootstrap -----------------------------------------------------------------
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from search.services.participant_extractor import ParticipantExtractor
from search.services.outcome_extractor import OutcomeExtractor
from search.services.region_detector import (
    get_region_from_affiliation, COUNTRY_TO_REGION,
)
from search.services.pubmed_client import search_pubmed

# ==============================================================================
# TIME PERIODS
# ==============================================================================

TIME_PERIODS = [
    {"id": "2000-2005", "name": "2000-2005", "year_from": "2000", "year_to": "2005"},
    {"id": "2006-2010", "name": "2006-2010", "year_from": "2006", "year_to": "2010"},
    {"id": "2011-2015", "name": "2011-2015", "year_from": "2011", "year_to": "2015"},
    {"id": "2016-2020", "name": "2016-2020", "year_from": "2016", "year_to": "2020"},
    {"id": "2021-2025", "name": "2021-2025", "year_from": "2021", "year_to": "2025"},
]

QUERY = "surgery OR clinical trial OR randomized"


# ==============================================================================
# GS HEURISTICS (same as benchmark_multispecialty.py -- no duplication)
# ==============================================================================

def _gs_participant_count(abstract: str) -> Optional[int]:
    if not abstract:
        return None
    m = re.search(
        r'(?:total\s+of\s+)?\d[\d,]*\s+(?:patients?|participants?|subjects?)\s+[\w\s]*?'
        r'(?:screened|assessed)[^.]*?(?:and\s+)?(\d[\d,]*)\s+(?:patients?\s+)?'
        r'(?:were\s+)?(?:included|enrolled|recruited|randomized|randomised)',
        abstract, re.IGNORECASE)
    if m: return int(m.group(1).replace(',', ''))
    m = re.search(
        r'(?:screened|assessed)\s+\d[\d,\s]*\s+\w+[^.]*?'
        r'(?:of\s+(?:whom|these|which))\s*,?\s*(\d[\d,]*)\s+(?:\w+\s+)?'
        r'(?:were\s+)?(?:included|enrolled|recruited|randomized|randomised|eligible)',
        abstract, re.IGNORECASE)
    if m: return int(m.group(1).replace(',', ''))
    m = re.search(
        r'(?:a\s+)?total\s+of\s+(\d[\d,]*)\s+(?:\w+\s+)?'
        r'(?:patients?|participants?|subjects?|individuals?|people|persons?|'
        r'women|men|children|adults?|infants?|neonates?)',
        abstract, re.IGNORECASE)
    if m:
        post = abstract[m.end():m.end() + 80].lower()
        if not re.search(r'(?:were\s+)?(?:screened|assessed|evaluated\s+for\s+eligibility)', post):
            return int(m.group(1).replace(',', ''))
    m = re.search(
        r'\b(\d[\d,]*)\s+(?:patients?|participants?|subjects?)\s+'
        r'(?:were|was|have been)\s+'
        r'(?:enrolled|randomized|randomised|included|recruited|analyzed|analysed|assigned)',
        abstract, re.IGNORECASE)
    if m: return int(m.group(1).replace(',', ''))
    m = re.search(
        r'(?:we|the study|this trial)\s+'
        r'(?:enrolled|randomized|randomised|included|recruited)\s+'
        r'(\d[\d,]*)\s+(?:patients?|participants?|subjects?)',
        abstract, re.IGNORECASE)
    if m: return int(m.group(1).replace(',', ''))
    arm_matches = list(re.finditer(r'[\(\[]\s*[Nn]\s*=\s*(\d[\d,]*)\s*[\)\]]', abstract))
    if len(arm_matches) >= 2:
        m1, m2 = arm_matches[0], arm_matches[1]
        if m2.start() - m1.end() < 200:
            ctx = abstract[max(0, m1.start()-100):m2.end()+50].lower()
            if any(kw in ctx for kw in ['randomiz', 'randomis', 'assigned', 'allocated', 'group', 'arm']):
                total = sum(int(am.group(1).replace(',', '')) for am in arm_matches
                            if am.start() - m1.start() < 300)
                if total >= 10: return total
    m = re.search(r'\(\s*[Nn]\s*=\s*(\d[\d,]*)\s*\)', abstract)
    if m: return int(m.group(1).replace(',', ''))
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
        abstract, re.IGNORECASE))


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


# ==============================================================================
# FETCH & EVALUATE
# ==============================================================================

def fetch_articles(query: str, n: int, year_from: str, year_to: str,
                   batch_size: int = 50) -> List[Dict]:
    """Fetch N articles from PubMed for a specific year range."""
    articles = []
    start = 0
    while len(articles) < n:
        size = min(batch_size, n - len(articles))
        try:
            total, batch = search_pubmed(
                term=query, start=start, size=size,
                study_type="randomized_controlled_trial",
                year_from=year_from, year_to=year_to,
            )
        except Exception as e:
            print(f"    [!] Error at offset {start}: {e}")
            break
        if not batch:
            break
        articles.extend(batch)
        start += size
        time.sleep(0.35)
    return articles[:n]


def evaluate_period(articles: List[Dict]) -> Dict:
    """Evaluate all 3 NLP modules on a set of articles."""
    # PE
    pe_errors, pe_tp, pe_fp, pe_fn = [], 0, 0, 0
    for art in articles:
        abstract = art.get('abstract', '')
        gs = _gs_participant_count(abstract)
        pred = art.get('sample_size')
        if gs is not None and pred is not None:
            pe_errors.append(abs(pred - gs))
            if abs(pred - gs) <= max(5, gs * 0.1):
                pe_tp += 1
            else:
                pe_fp += 1
        elif gs is not None and pred is None:
            pe_fn += 1

    pe_mae = sum(pe_errors) / len(pe_errors) if pe_errors else 0
    pe_prec = pe_tp / (pe_tp + pe_fp) if (pe_tp + pe_fp) else 0
    pe_rec = pe_tp / (pe_tp + pe_fn) if (pe_tp + pe_fn) else 0
    pe_f1 = 2 * pe_prec * pe_rec / (pe_prec + pe_rec) if (pe_prec + pe_rec) else 0

    # OE
    oe_tp = oe_fp = oe_fn = oe_tn = 0
    for art in articles:
        abstract = art.get('abstract', '')
        gs_has = _gs_has_primary_outcome(abstract)
        pred_has = art.get('primary_outcome') is not None
        if gs_has and pred_has: oe_tp += 1
        elif gs_has and not pred_has: oe_fn += 1
        elif not gs_has and pred_has: oe_fp += 1
        else: oe_tn += 1

    oe_prec = oe_tp / (oe_tp + oe_fp) if (oe_tp + oe_fp) else 0
    oe_rec = oe_tp / (oe_tp + oe_fn) if (oe_tp + oe_fn) else 0
    oe_f1 = 2 * oe_prec * oe_rec / (oe_prec + oe_rec) if (oe_prec + oe_rec) else 0

    # RD
    rd_tp = rd_fp = 0
    rd_evaluated = 0
    for art in articles:
        aff = art.get('affiliation', '') or art.get('last_author_affiliation', '')
        gs_region = _gs_region_from_affiliation(aff)
        if not gs_region:
            continue
        rd_evaluated += 1
        if art.get('region', '') == gs_region:
            rd_tp += 1
        else:
            rd_fp += 1

    rd_f1 = rd_tp / rd_evaluated * 100 if rd_evaluated else 0

    return {
        'pe': {'mae': round(pe_mae, 1), 'f1': round(pe_f1 * 100, 1),
               'precision': round(pe_prec * 100, 1), 'recall': round(pe_rec * 100, 1),
               'evaluated': len(pe_errors), 'tp': pe_tp, 'fp': pe_fp, 'fn': pe_fn},
        'oe': {'f1': round(oe_f1 * 100, 1), 'precision': round(oe_prec * 100, 1),
               'recall': round(oe_rec * 100, 1),
               'tp': oe_tp, 'fp': oe_fp, 'fn': oe_fn, 'tn': oe_tn},
        'rd': {'f1': round(rd_f1, 1), 'tp': rd_tp, 'mismatches': rd_fp, 'evaluated': rd_evaluated},
    }


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Temporal NLP Benchmark")
    parser.add_argument('--per-period', '-n', type=int, default=30,
                        help='Articles per time period (default: 30)')
    parser.add_argument('--output', '-o', type=str, default=None,
                        help='Output JSON file')
    parser.add_argument('--load', '-l', type=str, help='Load previous results')
    args = parser.parse_args()

    if args.load:
        with open(args.load, 'r', encoding='utf-8') as f:
            results = json.load(f)
        print_report(results)
        return

    print(f"\n{'=' * 65}")
    print(f"  BENCHMARK TEMPOREL - NLP par decennie")
    print(f"  {len(TIME_PERIODS)} periodes x {args.per_period} articles")
    print(f"  Query: \"{QUERY}\"")
    print(f"{'=' * 65}")

    t0 = time.time()
    period_results = []

    for i, period in enumerate(TIME_PERIODS, 1):
        print(f"\n  [{i}/{len(TIME_PERIODS)}] {period['name']} ({period['year_from']}-{period['year_to']})")

        articles = fetch_articles(QUERY, args.per_period,
                                  period['year_from'], period['year_to'])

        if not articles:
            print(f"    [!] Aucun article pour cette periode")
            continue

        print(f"    [OK] {len(articles)} articles recuperes")
        metrics = evaluate_period(articles)

        result = {
            'id': period['id'],
            'name': period['name'],
            'year_from': period['year_from'],
            'year_to': period['year_to'],
            'article_count': len(articles),
            **metrics,
        }
        period_results.append(result)

        pe, oe, rd = metrics['pe'], metrics['oe'], metrics['rd']
        print(f"    PE: F1={pe['f1']}% MAE={pe['mae']} | OE: F1={oe['f1']}% | RD: F1={rd['f1']}%")

    total_time = time.time() - t0
    total_articles = sum(r['article_count'] for r in period_results)

    results = {
        'meta': {
            'date': datetime.now().isoformat(),
            'total_articles': total_articles,
            'periods': len(period_results),
            'per_period_target': args.per_period,
            'query': QUERY,
            'duration_sec': round(total_time, 1),
        },
        'periods': period_results,
    }

    print_report(results)

    # Save
    outfile = args.output or f"benchmark_temporal_{total_articles}.json"
    with open(outfile, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"[SAVE] Resultats: {outfile}")
    print(f"[DONE] Termine en {total_time:.1f}s\n")


def print_report(results: Dict):
    """Print temporal benchmark report."""
    meta = results['meta']
    print(f"\n{'=' * 65}")
    print(f"  BENCHMARK TEMPOREL - RESULTATS")
    print(f"{'=' * 65}")
    print(f"  Date:     {meta['date']}")
    print(f"  Articles: {meta['total_articles']} ({meta['periods']} periodes)")
    print(f"  Duree:    {meta['duration_sec']}s")
    print(f"{'=' * 65}")

    print(f"\n  {'Periode':<15} {'Articles':>8} {'PE F1':>7} {'PE MAE':>8} {'OE F1':>7} {'RD F1':>7}")
    print(f"  {'-' * 58}")

    pe_f1_values = []
    oe_f1_values = []

    for pr in results['periods']:
        pe, oe, rd = pr['pe'], pr['oe'], pr['rd']
        pe_f1_values.append(pe['f1'])
        oe_f1_values.append(oe['f1'])
        print(f"  {pr['name']:<15} {pr['article_count']:>8} {pe['f1']:>6}% {pe['mae']:>7} {oe['f1']:>6}% {rd['f1']:>6}%")

    print(f"  {'-' * 58}")

    # Detect temporal bias
    if len(pe_f1_values) >= 3:
        pe_range = max(pe_f1_values) - min(pe_f1_values)
        oe_range = max(oe_f1_values) - min(oe_f1_values)

        print(f"\n  ANALYSE DE BIAIS TEMPOREL:")
        print(f"     PE F1 range: {min(pe_f1_values):.1f}% - {max(pe_f1_values):.1f}% (delta={pe_range:.1f}pp)")
        print(f"     OE F1 range: {min(oe_f1_values):.1f}% - {max(oe_f1_values):.1f}% (delta={oe_range:.1f}pp)")

        if pe_range > 15:
            print(f"     [!] PE: biais temporel significatif (delta > 15pp)")
        elif pe_range > 8:
            print(f"     [!] PE: biais temporel modere (delta > 8pp)")
        else:
            print(f"     [OK] PE: pas de biais temporel significatif")

        if oe_range > 15:
            print(f"     [!] OE: biais temporel significatif (delta > 15pp)")
        elif oe_range > 8:
            print(f"     [!] OE: biais temporel modere (delta > 8pp)")
        else:
            print(f"     [OK] OE: pas de biais temporel significatif")

        # Trend: are newer articles easier or harder?
        if len(pe_f1_values) >= 3:
            trend = pe_f1_values[-1] - pe_f1_values[0]
            if abs(trend) > 5:
                direction = "meilleurs" if trend > 0 else "moins bons"
                print(f"     Tendance PE: articles recents {direction} ({trend:+.1f}pp)")

            trend = oe_f1_values[-1] - oe_f1_values[0]
            if abs(trend) > 5:
                direction = "meilleurs" if trend > 0 else "moins bons"
                print(f"     Tendance OE: articles recents {direction} ({trend:+.1f}pp)")

    print()


if __name__ == '__main__':
    main()
