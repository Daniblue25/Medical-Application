#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
score_gold_standard.py -- Level 2 Validation: Score NLP vs Human Annotations
============================================================================
Reads the annotated CSV, normalizes formats, and produces detailed scoring
for all 3 NLP modules (PE, OE, RD) with per-specialty breakdown.

With --rerun-nlp, re-runs NLP modules using the latest code on the full
abstracts from the JSON file (instead of using pre-computed CSV values).

Usage:
    python score_gold_standard.py
    python score_gold_standard.py --csv gold_standard_annotation.csv
    python score_gold_standard.py --rerun-nlp
    python score_gold_standard.py --output results_gold_standard.json
"""

import os
import sys
import csv
import json
import re
import argparse
from collections import Counter, defaultdict
from typing import Dict, List, Optional, Tuple

# ==============================================================================
# NORMALIZATION
# ==============================================================================

REGION_NORMALIZE = {
    'asia': 'asia',
    'europe': 'europe',
    'north america': 'north_america',
    'north_america': 'north_america',
    'south america': 'south_america',
    'south_america': 'south_america',
    'oceania': 'oceania',
    'africa': 'africa',
    'middle east': 'asia',        # Middle East is part of Asia in our model
    'global': '',                   # Multi-country, can't score
}

COUNTRY_NORMALIZE = {
    'united state': 'usa',
    'united states': 'usa',
    'usa': 'usa',
    'u.s.a': 'usa',
    'u.s.a.': 'usa',
    'u.s': 'usa',
    'uk': 'united kingdom',
    'u.k': 'united kingdom',
    'u.k.': 'united kingdom',
    'england': 'united kingdom',
    'scotland': 'united kingdom',
    'china': 'china',
    'p.r. china': 'china',
    'japan': 'japan',
    'canada': 'canada',
    'australia': 'australia',
    'austalia': 'australia',      # Typo fix
    'germany': 'germany',
    'german': 'germany',          # Typo fix
    'italy': 'italy',
    'spain': 'spain',
    'france': 'france',
    'netherlands': 'netherlands',
    'switzerland': 'switzerland',
    'switzeland': 'switzerland',  # Typo fix
    'sweden': 'sweden',
    'norway': 'norway',
    'south korea': 'south korea',
    'iran': 'iran',
    'israel': 'israel',
    'brazil': 'brazil',
    'india': 'india',
    'turkey': 'turkey',
}


def normalize_region(val: str) -> str:
    """Normalize region string to lowercase key."""
    if not val:
        return ''
    return REGION_NORMALIZE.get(val.strip().lower(), val.strip().lower())


def normalize_country(val: str) -> str:
    """Normalize country string."""
    if not val:
        return ''
    return COUNTRY_NORMALIZE.get(val.strip().lower(), val.strip().lower())


def parse_bool(val: str) -> Optional[bool]:
    """Parse boolean from CSV string."""
    if not val or val.strip().lower() in ('', 'null', 'none'):
        return None
    return val.strip().lower() in ('true', '1', 'yes', 'oui')


def parse_int(val: str) -> Optional[int]:
    """Parse integer from CSV, handling non-breaking spaces and commas."""
    if not val or val.strip().lower() in ('', 'null', 'none', 'na'):
        return None
    # Remove non-breaking spaces (U+202F, U+00A0) and regular spaces
    cleaned = val.strip().replace('\u202f', '').replace('\u00a0', '').replace(' ', '').replace(',', '')
    try:
        return int(cleaned)
    except ValueError:
        return None


# ==============================================================================
# CSV READER
# ==============================================================================

def read_annotations(csv_path: str) -> List[Dict]:
    """Read and normalize annotations from CSV."""
    with open(csv_path, 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        rows = list(reader)

    articles = []
    for r in rows:
        art = {
            'id': int(r['id']),
            'pmid': r['pmid'],
            'specialty': r['specialty'],
            'title': r.get('title', ''),
            'affiliation': r.get('affiliation', ''),
            # NLP predictions
            'nlp_sample_size': parse_int(r.get('nlp_sample_size', '')),
            'nlp_primary_outcome': parse_bool(r.get('nlp_primary_outcome', '')),
            'nlp_region': r.get('nlp_region', '').strip().lower(),
            # Human annotations
            'human_sample_size': parse_int(r.get('sample_size_human', '')),
            'human_primary_outcome': parse_bool(r.get('primary_outcome_human', '')),
            'human_outcome_text': r.get('outcome_text_human', '').strip(),
            'human_country': normalize_country(r.get('country_human', '')),
            'human_region': normalize_region(r.get('region_human', '')),
            'notes': r.get('notes', ''),
        }
        articles.append(art)

    return articles


# ==============================================================================
# SCORING
# ==============================================================================

def score_pe(articles: List[Dict]) -> Dict:
    """Score ParticipantExtractor: NLP vs human sample_size."""
    tp = fp = fn = 0
    errors = []
    details = []

    for a in articles:
        gs = a['human_sample_size']
        pred = a['nlp_sample_size']
        if gs is None:
            continue  # Not annotated

        if pred is not None and gs is not None:
            err = abs(pred - gs)
            errors.append(err)
            tolerance = max(5, gs * 0.1)
            if err <= tolerance:
                tp += 1
            else:
                fp += 1
                details.append({
                    'id': a['id'], 'pmid': a['pmid'], 'specialty': a['specialty'],
                    'type': 'FP', 'nlp': pred, 'human': gs, 'error': err,
                    'notes': a['notes'],
                })
        elif pred is None and gs is not None and gs > 0:
            fn += 1
            details.append({
                'id': a['id'], 'pmid': a['pmid'], 'specialty': a['specialty'],
                'type': 'FN', 'nlp': None, 'human': gs, 'error': None,
                'notes': a['notes'],
            })

    n = tp + fp + fn
    mae = sum(errors) / len(errors) if errors else 0
    prec = tp / (tp + fp) if (tp + fp) else 0
    rec = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0

    return {
        'n': n, 'tp': tp, 'fp': fp, 'fn': fn,
        'mae': round(mae, 1),
        'precision': round(prec * 100, 1),
        'recall': round(rec * 100, 1),
        'f1': round(f1 * 100, 1),
        'details': details,
    }


def score_oe(articles: List[Dict]) -> Dict:
    """Score OutcomeExtractor: NLP vs human primary_outcome detection."""
    tp = fp = fn = tn = 0
    details = []

    for a in articles:
        gs = a['human_primary_outcome']
        if gs is None:
            continue

        pred = a['nlp_primary_outcome'] or False

        if gs and pred:
            tp += 1
        elif gs and not pred:
            fn += 1
            details.append({
                'id': a['id'], 'pmid': a['pmid'], 'specialty': a['specialty'],
                'type': 'FN', 'nlp': pred, 'human': gs,
                'human_text': a['human_outcome_text'][:100] if a['human_outcome_text'] else '',
                'notes': a['notes'],
            })
        elif not gs and pred:
            fp += 1
            details.append({
                'id': a['id'], 'pmid': a['pmid'], 'specialty': a['specialty'],
                'type': 'FP', 'nlp': pred, 'human': gs,
                'notes': a['notes'],
            })
        else:
            tn += 1

    n = tp + fp + fn + tn
    prec = tp / (tp + fp) if (tp + fp) else 0
    rec = tp / (tp + fn) if (tp + fn) else 0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0

    return {
        'n': n, 'tp': tp, 'fp': fp, 'fn': fn, 'tn': tn,
        'precision': round(prec * 100, 1),
        'recall': round(rec * 100, 1),
        'f1': round(f1 * 100, 1),
        'details': details,
    }


def score_rd(articles: List[Dict]) -> Dict:
    """Score RegionDetector: NLP region vs human region."""
    tp = fp = 0
    details = []

    for a in articles:
        gs = a['human_region']
        if not gs:
            continue  # Not annotated or 'global'

        pred = a['nlp_region']

        if pred == gs:
            tp += 1
        else:
            fp += 1
            details.append({
                'id': a['id'], 'pmid': a['pmid'], 'specialty': a['specialty'],
                'type': 'mismatch',
                'nlp_region': pred, 'human_region': gs,
                'human_country': a['human_country'],
                'affiliation': a['affiliation'][:100],
                'notes': a['notes'],
            })

    n = tp + fp
    acc = tp / n * 100 if n else 0

    return {
        'n': n, 'tp': tp, 'fp': fp,
        'accuracy': round(acc, 1),
        'details': details,
    }


def score_by_specialty(articles: List[Dict]) -> Dict:
    """Score per specialty."""
    by_spec = defaultdict(list)
    for a in articles:
        by_spec[a['specialty']].append(a)

    results = {}
    for spec, arts in sorted(by_spec.items()):
        pe = score_pe(arts)
        oe = score_oe(arts)
        rd = score_rd(arts)
        results[spec] = {
            'count': len(arts),
            'pe_f1': pe['f1'], 'pe_mae': pe['mae'],
            'oe_f1': oe['f1'],
            'rd_accuracy': rd['accuracy'],
        }
    return results


# ==============================================================================
# REPORT
# ==============================================================================

def print_report(articles: List[Dict], pe: Dict, oe: Dict, rd: Dict, by_spec: Dict):
    """Print detailed scoring report."""
    print(f"\n{'=' * 70}")
    print(f"  LEVEL 2 — GOLD STANDARD VALIDATION (Human Annotations)")
    print(f"{'=' * 70}")
    print(f"  Articles: {len(articles)}")
    print(f"  Specialties: {len(set(a['specialty'] for a in articles))}")
    print(f"{'=' * 70}")

    # -- PE
    print(f"\n  [PE] ParticipantExtractor (n={pe['n']} annotated)")
    print(f"       F1 = {pe['f1']}%  |  Precision = {pe['precision']}%  |  Recall = {pe['recall']}%")
    print(f"       MAE = {pe['mae']}  |  TP={pe['tp']}  FP={pe['fp']}  FN={pe['fn']}")
    if pe['details']:
        print(f"       Errors ({len(pe['details'])}):")
        for d in pe['details'][:10]:
            notes = (d['notes'][:60] if d['notes'] else '').encode('ascii', 'replace').decode()
            print(f"         #{d['id']} [{d['specialty']}] {d['type']}: nlp={d['nlp']} human={d['human']} "
                  f"{'err='+str(d['error']) if d['error'] else ''} {notes}")
        if len(pe['details']) > 10:
            print(f"         ... +{len(pe['details'])-10} more")

    # -- OE
    print(f"\n  [OE] OutcomeExtractor (n={oe['n']} annotated)")
    print(f"       F1 = {oe['f1']}%  |  Precision = {oe['precision']}%  |  Recall = {oe['recall']}%")
    print(f"       TP={oe['tp']}  FP={oe['fp']}  FN={oe['fn']}  TN={oe['tn']}")
    if oe['details']:
        print(f"       Errors ({len(oe['details'])}):")
        for d in oe['details']:
            txt = (d.get('human_text', '')[:60] if d.get('human_text') else '').encode('ascii', 'replace').decode()
            print(f"         #{d['id']} [{d['specialty']}] {d['type']}: nlp={d['nlp']} human={d['human']} {txt}")

    # -- RD
    print(f"\n  [RD] RegionDetector (n={rd['n']} annotated)")
    print(f"       Accuracy = {rd['accuracy']}%  ({rd['tp']}/{rd['n']} correct)")
    if rd['details']:
        print(f"       Mismatches ({len(rd['details'])}):")
        for d in rd['details']:
            aff = d['affiliation'][:60].encode('ascii', 'replace').decode()
            print(f"         #{d['id']} [{d['specialty']}] nlp={d['nlp_region']} human={d['human_region']} "
                  f"(country={d['human_country']}) {aff}")

    # -- By specialty
    print(f"\n  {'Specialty':<25} {'N':>3} {'PE F1':>7} {'PE MAE':>8} {'OE F1':>7} {'RD Acc':>7}")
    print(f"  {'-' * 61}")
    for spec, m in by_spec.items():
        print(f"  {spec:<25} {m['count']:>3} {m['pe_f1']:>6}% {m['pe_mae']:>7} {m['oe_f1']:>6}% {m['rd_accuracy']:>6}%")
    print(f"  {'-' * 61}")
    print(f"  {'GLOBAL':<25} {len(articles):>3} {pe['f1']:>6}% {pe['mae']:>7} {oe['f1']:>6}% {rd['accuracy']:>6}%")

    print(f"\n{'=' * 70}")
    print(f"  VERDICT:")
    verdict_ok = True
    if pe['f1'] >= 80:
        print(f"    [OK] PE F1 = {pe['f1']}% (seuil >= 80%)")
    else:
        print(f"    [!!] PE F1 = {pe['f1']}% (SOUS seuil 80%)")
        verdict_ok = False
    if oe['f1'] >= 85:
        print(f"    [OK] OE F1 = {oe['f1']}% (seuil >= 85%)")
    else:
        print(f"    [!!] OE F1 = {oe['f1']}% (SOUS seuil 85%)")
        verdict_ok = False
    if rd['accuracy'] >= 90:
        print(f"    [OK] RD Accuracy = {rd['accuracy']}% (seuil >= 90%)")
    else:
        print(f"    [!!] RD Accuracy = {rd['accuracy']}% (SOUS seuil 90%)")
        verdict_ok = False

    if verdict_ok:
        print(f"\n    >>> LEVEL 2 VALIDATION: PASSED <<<")
    else:
        print(f"\n    >>> LEVEL 2 VALIDATION: NEEDS IMPROVEMENT <<<")
    print(f"{'=' * 70}\n")

    return verdict_ok


# ==============================================================================
# MAIN
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(description="Level 2 Gold Standard Scoring")
    parser.add_argument('--csv', default='gold_standard_annotation.csv',
                        help='Path to annotated CSV')
    parser.add_argument('--json', default='gold_standard_annotation.json',
                        help='Path to JSON with full abstracts (for --rerun-nlp)')
    parser.add_argument('--rerun-nlp', action='store_true',
                        help='Re-run NLP modules using latest code on full abstracts')
    parser.add_argument('--output', '-o', default=None,
                        help='Output JSON results file')
    args = parser.parse_args()

    csv_path = args.csv
    if not os.path.exists(csv_path):
        print(f"[ERROR] File not found: {csv_path}")
        sys.exit(1)

    # Read and normalize from CSV (human annotations)
    articles = read_annotations(csv_path)
    print(f"Read {len(articles)} articles from {csv_path}")

    # ── Re-run NLP if requested ──────────────────────────────────────────
    if args.rerun_nlp:
        json_path = args.json
        if not os.path.exists(json_path):
            print(f"[ERROR] JSON file not found: {json_path}")
            sys.exit(1)

        # Setup Django
        sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))
        os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
        import django
        django.setup()

        from search.services.participant_extractor import ParticipantExtractor
        from search.services.outcome_extractor import OutcomeExtractor
        from search.services.region_detector import (
            get_region_from_affiliation,
            extract_country_from_affiliation,
        )

        with open(json_path, 'r', encoding='utf-8') as f:
            json_data = json.load(f)
        pmid_to_json = {str(a['pmid']): a for a in json_data}

        n_updated = 0
        for art in articles:
            jart = pmid_to_json.get(art['pmid'])
            if not jart:
                continue
            abstract = jart.get('abstract', '')
            affiliation = jart.get('affiliation', '')

            # Re-run PE
            pe_result = ParticipantExtractor.extract_sample_size(abstract)
            art['nlp_sample_size'] = pe_result.get('sample_size')

            # Re-run OE
            oe_result = OutcomeExtractor.extract_outcomes(abstract)
            art['nlp_primary_outcome'] = bool(oe_result.get('primary_outcome'))

            # Re-run RD
            art['nlp_region'] = get_region_from_affiliation(affiliation) or ''
            art['nlp_country'] = extract_country_from_affiliation(affiliation) or ''

            n_updated += 1

        print(f"[RERUN-NLP] Updated {n_updated}/{len(articles)} articles with latest NLP code")

    # Data quality report
    n_ss = sum(1 for a in articles if a['human_sample_size'] is not None)
    n_po = sum(1 for a in articles if a['human_primary_outcome'] is not None)
    n_rg = sum(1 for a in articles if a['human_region'])
    print(f"Annotated: sample_size={n_ss} primary_outcome={n_po} region={n_rg}")

    # Score
    pe = score_pe(articles)
    oe = score_oe(articles)
    rd = score_rd(articles)
    by_spec = score_by_specialty(articles)

    # Report
    verdict = print_report(articles, pe, oe, rd, by_spec)

    # Save JSON
    outfile = args.output or 'results_gold_standard.json'
    from datetime import datetime
    results = {
        'meta': {
            'date': datetime.now().isoformat(),
            'csv_file': csv_path,
            'total_articles': len(articles),
            'annotated_ss': n_ss,
            'annotated_po': n_po,
            'annotated_region': n_rg,
        },
        'global': {
            'pe': {k: v for k, v in pe.items() if k != 'details'},
            'oe': {k: v for k, v in oe.items() if k != 'details'},
            'rd': {k: v for k, v in rd.items() if k != 'details'},
        },
        'by_specialty': by_spec,
        'errors': {
            'pe': pe['details'],
            'oe': oe['details'],
            'rd': rd['details'],
        },
        'verdict': 'PASSED' if verdict else 'NEEDS_IMPROVEMENT',
    }

    with open(outfile, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"[SAVE] {outfile}")


if __name__ == '__main__':
    main()
