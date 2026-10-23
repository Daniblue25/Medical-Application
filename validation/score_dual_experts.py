#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""
score_dual_experts.py -- Level 2 Validation: NLP vs Two Human Experts
=====================================================================
Reads Expert 1 (CSV) and Expert 2 (XLSX disguised as .csv), normalizes
formats, and produces:
  - NLP vs Expert 1
  - NLP vs Expert 2
  - Inter-rater agreement (Cohen's kappa, % agreement)
  - NLP vs Consensus (where both experts agree)

Usage:
    python score_dual_experts.py
    python score_dual_experts.py --rerun-nlp
    python score_dual_experts.py --output results_dual_experts.json
"""

import os
import sys
import csv
import json
import shutil
import argparse
from collections import defaultdict
from datetime import datetime
from typing import Dict, List, Optional

# ---------------------------------------------------------------------------
# NORMALIZATION
# ---------------------------------------------------------------------------

REGION_NORMALIZE = {
    'asia': 'asia', 'asie': 'asia',
    'europe': 'europe',
    'north america': 'north_america', 'north_america': 'north_america',
    'nord america': 'north_america', 'nord amérique': 'north_america',
    'nord amérique': 'north_america',
    'south america': 'south_america', 'south_america': 'south_america',
    'oceania': 'oceania', 'océanie': 'oceania',
    'africa': 'africa', 'afrique': 'africa',
    'middle east': 'asia',
    'global': '',
}

COUNTRY_NORMALIZE = {
    # English forms
    'united state': 'usa', 'united states': 'usa', 'usa': 'usa',
    'u.s.a': 'usa', 'u.s.a.': 'usa', 'u.s': 'usa',
    'uk': 'united kingdom', 'u.k': 'united kingdom', 'u.k.': 'united kingdom',
    'england': 'united kingdom', 'scotland': 'united kingdom',
    'china': 'china', 'p.r. china': 'china',
    'japan': 'japan', 'canada': 'canada', 'australia': 'australia',
    'austalia': 'australia',
    'germany': 'germany', 'german': 'germany',
    'italy': 'italy', 'spain': 'spain', 'france': 'france',
    'netherlands': 'netherlands', 'switzerland': 'switzerland',
    'switzeland': 'switzerland',
    'sweden': 'sweden', 'norway': 'norway',
    'south korea': 'south korea', 'iran': 'iran', 'israel': 'israel',
    'brazil': 'brazil', 'india': 'india', 'turkey': 'turkey',
    # French forms (Expert 2)
    'chine': 'china', 'sichuan chine': 'china', 'hong kong chine': 'china',
    'italie': 'italy', 'allemagne': 'germany', 'espagne': 'spain',
    'japon': 'japan', 'norvège': 'norway', 'suisse': 'switzerland',
    'pays bas': 'netherlands', 'corée': 'south korea',
    'australie': 'australia', 'canda': 'canada',
    # US cities/states → USA
    'texas': 'usa', 'boston': 'usa', 'californie': 'usa', 'california': 'usa',
    'colorado': 'usa', 'cleveland': 'usa', 'houston': 'usa',
    'maryland': 'usa', 'miami': 'usa', 'michigan': 'usa', 'ny': 'usa',
    'pennsylvanie': 'usa', 'pennsylvania': 'usa',
    'philadelphia': 'usa', 'philadelphie': 'usa',
    'settle': 'usa', 'seattle': 'usa', 'standford': 'usa', 'stanford': 'usa',
    'faifax': 'usa', 'fairfax': 'usa',
    'caroline du nord': 'usa', 'north carolina': 'usa',
    'toronto': 'canada',
}


def normalize_region(val: str) -> str:
    if not val:
        return ''
    return REGION_NORMALIZE.get(val.strip().lower(), val.strip().lower())


def normalize_country(val: str) -> str:
    if not val:
        return ''
    return COUNTRY_NORMALIZE.get(val.strip().lower(), val.strip().lower())


def parse_bool(val) -> Optional[bool]:
    if val is None:
        return None
    if isinstance(val, bool):
        return val
    s = str(val).strip().lower()
    if s in ('', 'null', 'none'):
        return None
    return s in ('true', '1', 'yes', 'oui')


def parse_int(val) -> Optional[int]:
    if val is None:
        return None
    if isinstance(val, (int, float)):
        return int(val)
    s = str(val).strip()
    if s.lower() in ('', 'null', 'none', 'na'):
        return None
    cleaned = s.replace('\u202f', '').replace('\u00a0', '').replace(' ', '').replace(',', '')
    try:
        return int(cleaned)
    except ValueError:
        return None


# ---------------------------------------------------------------------------
# READERS
# ---------------------------------------------------------------------------

def read_expert1(csv_path: str) -> List[Dict]:
    """Read Expert 1 annotations from semicolon-delimited CSV."""
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
            'nlp_sample_size': parse_int(r.get('nlp_sample_size', '')),
            'nlp_primary_outcome': parse_bool(r.get('nlp_primary_outcome', '')),
            'nlp_region': r.get('nlp_region', '').strip().lower(),
            'e1_sample_size': parse_int(r.get('sample_size_human', '')),
            'e1_primary_outcome': parse_bool(r.get('primary_outcome_human', '')),
            'e1_outcome_text': r.get('outcome_text_human', '').strip(),
            'e1_country': normalize_country(r.get('country_human', '')),
            'e1_region': normalize_region(r.get('region_human', '')),
            'e1_notes': r.get('notes', ''),
        }
        articles.append(art)
    return articles


def _is_xlsx(path: str) -> bool:
    """XLSX files are ZIP archives: detect them by their magic bytes, not their extension."""
    with open(path, 'rb') as f:
        return f.read(4) == b'PK\x03\x04'


def read_expert2(xlsx_path: str) -> List[Dict]:
    """Read Expert 2 annotations.

    Accepts either the original XLSX file (disguised as .csv) or the
    semicolon-delimited CSV published on Zenodo (N2_expert2_annotations.csv).
    """
    if not _is_xlsx(xlsx_path):
        with open(xlsx_path, 'r', encoding='utf-8-sig') as f:
            rows = [r for r in csv.DictReader(f, delimiter=';') if (r.get('id') or '').strip()]
    else:
        import openpyxl

        tmp_path = xlsx_path + '.tmp.xlsx'
        shutil.copy2(xlsx_path, tmp_path)
        try:
            wb = openpyxl.load_workbook(tmp_path, read_only=True)
            ws = wb.active
            headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]

            rows = []
            for row in ws.iter_rows(min_row=2, values_only=True):
                data = dict(zip(headers, row))
                rows.append(data)
            wb.close()
        finally:
            try:
                os.remove(tmp_path)
            except OSError:
                pass

    articles = []
    for r in rows:
        art = {
            'id': int(r['id']),
            'pmid': str(r['pmid']),
            'e2_sample_size': parse_int(r.get('sample_size_human')),
            'e2_primary_outcome': parse_bool(r.get('primary_outcome_human')),
            'e2_outcome_text': (r.get('outcome_text_human') or '').strip() if r.get('outcome_text_human') else '',
            'e2_country': normalize_country(str(r.get('country_human') or '')),
            'e2_region': normalize_region(str(r.get('region_human') or '')),
            'e2_notes': r.get('notes') or '',
        }
        articles.append(art)
    return articles


def merge_experts(e1_list: List[Dict], e2_list: List[Dict]) -> List[Dict]:
    """Merge expert 1 and expert 2 annotations by id."""
    e2_by_id = {a['id']: a for a in e2_list}
    merged = []
    for a1 in e1_list:
        a2 = e2_by_id.get(a1['id'], {})
        combined = {**a1}
        combined['e2_sample_size'] = a2.get('e2_sample_size')
        combined['e2_primary_outcome'] = a2.get('e2_primary_outcome')
        combined['e2_outcome_text'] = a2.get('e2_outcome_text', '')
        combined['e2_country'] = a2.get('e2_country', '')
        combined['e2_region'] = a2.get('e2_region', '')
        combined['e2_notes'] = a2.get('e2_notes', '')
        merged.append(combined)
    return merged


# ---------------------------------------------------------------------------
# SCORING FUNCTIONS
# ---------------------------------------------------------------------------

def score_pe(articles: List[Dict], human_key: str) -> Dict:
    """Score ParticipantExtractor: NLP vs human sample_size."""
    tp = fp = fn = 0
    errors = []
    details = []

    for a in articles:
        gs = a[human_key]
        pred = a['nlp_sample_size']
        if gs is None:
            continue

        if pred is not None:
            err = abs(pred - gs)
            errors.append(err)
            tolerance = max(5, gs * 0.1)
            if err <= tolerance:
                tp += 1
            else:
                fp += 1
                details.append({
                    'id': a['id'], 'pmid': a['pmid'],
                    'specialty': a.get('specialty', ''),
                    'type': 'FP', 'nlp': pred, 'human': gs, 'error': err,
                })
        elif gs > 0:
            fn += 1
            details.append({
                'id': a['id'], 'pmid': a['pmid'],
                'specialty': a.get('specialty', ''),
                'type': 'FN', 'nlp': None, 'human': gs,
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


def score_oe(articles: List[Dict], human_key: str) -> Dict:
    """Score OutcomeExtractor: NLP vs human primary_outcome detection."""
    tp = fp = fn = tn = 0
    details = []

    for a in articles:
        gs = a[human_key]
        if gs is None:
            continue
        pred = a['nlp_primary_outcome'] or False

        if gs and pred:
            tp += 1
        elif gs and not pred:
            fn += 1
            details.append({
                'id': a['id'], 'pmid': a['pmid'],
                'specialty': a.get('specialty', ''),
                'type': 'FN', 'nlp': pred, 'human': gs,
            })
        elif not gs and pred:
            fp += 1
            details.append({
                'id': a['id'], 'pmid': a['pmid'],
                'specialty': a.get('specialty', ''),
                'type': 'FP', 'nlp': pred, 'human': gs,
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


def score_rd(articles: List[Dict], human_key: str) -> Dict:
    """Score RegionDetector: NLP region vs human region."""
    tp = fp = 0
    details = []

    for a in articles:
        gs = a[human_key]
        if not gs:
            continue
        pred = a['nlp_region']

        if pred == gs:
            tp += 1
        else:
            fp += 1
            details.append({
                'id': a['id'], 'pmid': a['pmid'],
                'specialty': a.get('specialty', ''),
                'type': 'mismatch',
                'nlp_region': pred, 'human_region': gs,
            })

    n = tp + fp
    acc = tp / n * 100 if n else 0
    return {
        'n': n, 'tp': tp, 'fp': fp,
        'accuracy': round(acc, 1),
        'details': details,
    }


# ---------------------------------------------------------------------------
# INTER-RATER AGREEMENT
# ---------------------------------------------------------------------------

def cohens_kappa(list1: List, list2: List) -> float:
    """Compute Cohen's kappa for two lists of categorical labels."""
    assert len(list1) == len(list2)
    n = len(list1)
    if n == 0:
        return 0.0

    categories = sorted(set(list1) | set(list2))
    # Build confusion matrix
    matrix = defaultdict(int)
    for a, b in zip(list1, list2):
        matrix[(a, b)] += 1

    po = sum(matrix[(c, c)] for c in categories) / n  # observed agreement

    # Expected agreement
    pe = 0.0
    for c in categories:
        row_sum = sum(matrix[(c, c2)] for c2 in categories) / n
        col_sum = sum(matrix[(c2, c)] for c2 in categories) / n
        pe += row_sum * col_sum

    if pe >= 1.0:
        return 1.0
    return (po - pe) / (1.0 - pe)


def compute_inter_rater(articles: List[Dict]) -> Dict:
    """Compute inter-rater agreement between Expert 1 and Expert 2."""
    results = {}

    # -- Sample Size (PE): agreement within tolerance
    pe_pairs = []
    pe_agree = 0
    pe_disagree_details = []
    for a in articles:
        e1 = a['e1_sample_size']
        e2 = a['e2_sample_size']
        if e1 is None or e2 is None:
            continue
        pe_pairs.append((e1, e2))
        reference = max(e1, e2)
        tolerance = max(5, reference * 0.1)
        if abs(e1 - e2) <= tolerance:
            pe_agree += 1
        else:
            pe_disagree_details.append({
                'id': a['id'], 'pmid': a['pmid'],
                'e1': e1, 'e2': e2, 'diff': abs(e1 - e2),
            })

    n_pe = len(pe_pairs)
    pe_pct = round(pe_agree / n_pe * 100, 1) if n_pe else 0
    # MAE between experts
    pe_mae = round(sum(abs(a - b) for a, b in pe_pairs) / n_pe, 1) if n_pe else 0

    results['pe'] = {
        'n': n_pe,
        'agreement_pct': pe_pct,
        'agree': pe_agree,
        'disagree': n_pe - pe_agree,
        'mae_between_experts': pe_mae,
        'disagree_details': pe_disagree_details,
    }

    # -- Primary Outcome (OE): Cohen's kappa
    oe_e1, oe_e2 = [], []
    for a in articles:
        e1 = a['e1_primary_outcome']
        e2 = a['e2_primary_outcome']
        if e1 is None or e2 is None:
            continue
        oe_e1.append(e1)
        oe_e2.append(e2)

    n_oe = len(oe_e1)
    oe_agree = sum(1 for a, b in zip(oe_e1, oe_e2) if a == b)
    oe_pct = round(oe_agree / n_oe * 100, 1) if n_oe else 0
    oe_kappa = round(cohens_kappa(oe_e1, oe_e2), 3) if n_oe else 0

    results['oe'] = {
        'n': n_oe,
        'agreement_pct': oe_pct,
        'agree': oe_agree,
        'disagree': n_oe - oe_agree,
        'kappa': oe_kappa,
    }

    # -- Region (RD): Cohen's kappa
    rd_e1, rd_e2 = [], []
    for a in articles:
        e1 = a['e1_region']
        e2 = a['e2_region']
        if not e1 or not e2:
            continue
        rd_e1.append(e1)
        rd_e2.append(e2)

    n_rd = len(rd_e1)
    rd_agree = sum(1 for a, b in zip(rd_e1, rd_e2) if a == b)
    rd_pct = round(rd_agree / n_rd * 100, 1) if n_rd else 0
    rd_kappa = round(cohens_kappa(rd_e1, rd_e2), 3) if n_rd else 0

    results['rd'] = {
        'n': n_rd,
        'agreement_pct': rd_pct,
        'agree': rd_agree,
        'disagree': n_rd - rd_agree,
        'kappa': rd_kappa,
    }

    return results


# ---------------------------------------------------------------------------
# CONSENSUS SCORING
# ---------------------------------------------------------------------------

def build_consensus(articles: List[Dict]) -> List[Dict]:
    """Build consensus annotations: only where both experts agree."""
    for a in articles:
        # PE consensus: use value if both agree within tolerance
        e1_ss = a['e1_sample_size']
        e2_ss = a['e2_sample_size']
        if e1_ss is not None and e2_ss is not None:
            ref = max(e1_ss, e2_ss)
            tolerance = max(5, ref * 0.1)
            if abs(e1_ss - e2_ss) <= tolerance:
                a['consensus_sample_size'] = e1_ss  # use expert 1 as reference
            else:
                a['consensus_sample_size'] = None  # disagreement → excluded
        else:
            a['consensus_sample_size'] = e1_ss if e1_ss is not None else e2_ss

        # OE consensus
        e1_po = a['e1_primary_outcome']
        e2_po = a['e2_primary_outcome']
        if e1_po is not None and e2_po is not None:
            if e1_po == e2_po:
                a['consensus_primary_outcome'] = e1_po
            else:
                a['consensus_primary_outcome'] = None  # disagreement
        else:
            a['consensus_primary_outcome'] = e1_po if e1_po is not None else e2_po

        # RD consensus
        e1_rg = a['e1_region']
        e2_rg = a['e2_region']
        if e1_rg and e2_rg:
            if e1_rg == e2_rg:
                a['consensus_region'] = e1_rg
            else:
                a['consensus_region'] = ''  # disagreement
        else:
            a['consensus_region'] = e1_rg or e2_rg

    return articles


# ---------------------------------------------------------------------------
# REPORT
# ---------------------------------------------------------------------------

def print_section(title: str, scores: Dict, label: str):
    """Print one scoring section."""
    pe, oe, rd = scores['pe'], scores['oe'], scores['rd']
    print(f"\n  --- {title} ---")
    print(f"  [PE] n={pe['n']}  F1={pe['f1']}%  P={pe['precision']}%  R={pe['recall']}%  MAE={pe['mae']}")
    print(f"       TP={pe['tp']}  FP={pe['fp']}  FN={pe['fn']}")
    print(f"  [OE] n={oe['n']}  F1={oe['f1']}%  P={oe['precision']}%  R={oe['recall']}%")
    print(f"       TP={oe['tp']}  FP={oe['fp']}  FN={oe['fn']}  TN={oe['tn']}")
    print(f"  [RD] n={rd['n']}  Accuracy={rd['accuracy']}%  ({rd['tp']}/{rd['n']})")


def print_full_report(articles, vs_e1, vs_e2, vs_consensus, inter_rater):
    """Print the full dual-expert report."""
    sep = '=' * 72
    print(f"\n{sep}")
    print(f"  LEVEL 2 — DUAL-EXPERT GOLD STANDARD VALIDATION")
    print(f"{sep}")
    print(f"  Articles: {len(articles)}")
    print(f"  Specialties: {len(set(a.get('specialty', '') for a in articles))}")

    # Inter-rater agreement
    print(f"\n{sep}")
    print(f"  INTER-RATER AGREEMENT (Expert 1 vs Expert 2)")
    print(f"{sep}")
    ir = inter_rater
    print(f"  [PE] Sample Size:       {ir['pe']['agreement_pct']}% agreement ({ir['pe']['agree']}/{ir['pe']['n']})")
    print(f"       MAE between experts: {ir['pe']['mae_between_experts']}")
    if ir['pe']['disagree_details']:
        print(f"       Disagreements ({len(ir['pe']['disagree_details'])}):")
        for d in ir['pe']['disagree_details'][:10]:
            print(f"         #{d['id']} (PMID {d['pmid']}): E1={d['e1']} vs E2={d['e2']} (diff={d['diff']})")
        if len(ir['pe']['disagree_details']) > 10:
            print(f"         ... +{len(ir['pe']['disagree_details'])-10} more")

    print(f"  [OE] Primary Outcome:   {ir['oe']['agreement_pct']}% agreement ({ir['oe']['agree']}/{ir['oe']['n']})  κ={ir['oe']['kappa']}")
    print(f"  [RD] Region:            {ir['rd']['agreement_pct']}% agreement ({ir['rd']['agree']}/{ir['rd']['n']})  κ={ir['rd']['kappa']}")

    # Kappa interpretation
    for module, key in [('OE', 'oe'), ('RD', 'rd')]:
        k = ir[key]['kappa']
        if k >= 0.81:
            interp = 'Almost perfect'
        elif k >= 0.61:
            interp = 'Substantial'
        elif k >= 0.41:
            interp = 'Moderate'
        elif k >= 0.21:
            interp = 'Fair'
        else:
            interp = 'Slight/Poor'
        print(f"       {module} κ interpretation: {interp} (Landis & Koch)")

    # NLP vs each expert
    print(f"\n{sep}")
    print(f"  NLP PERFORMANCE")
    print(f"{sep}")
    print_section("NLP vs Expert 1", vs_e1, "E1")
    print_section("NLP vs Expert 2", vs_e2, "E2")
    print_section("NLP vs Consensus (both agree)", vs_consensus, "Consensus")

    # Summary table
    print(f"\n  {'Metric':<25} {'vs E1':>8} {'vs E2':>8} {'vs Cons.':>8}")
    print(f"  {'-' * 52}")
    print(f"  {'PE F1':<25} {vs_e1['pe']['f1']:>7}% {vs_e2['pe']['f1']:>7}% {vs_consensus['pe']['f1']:>7}%")
    print(f"  {'PE MAE':<25} {vs_e1['pe']['mae']:>8} {vs_e2['pe']['mae']:>8} {vs_consensus['pe']['mae']:>8}")
    print(f"  {'OE F1':<25} {vs_e1['oe']['f1']:>7}% {vs_e2['oe']['f1']:>7}% {vs_consensus['oe']['f1']:>7}%")
    print(f"  {'RD Accuracy':<25} {vs_e1['rd']['accuracy']:>7}% {vs_e2['rd']['accuracy']:>7}% {vs_consensus['rd']['accuracy']:>7}%")

    # Verdict
    print(f"\n{sep}")
    print(f"  VERDICT (thresholds: PE F1≥80%, OE F1≥85%, RD Acc≥90%)")
    print(f"{sep}")
    all_ok = True
    for label, scores in [('Expert 1', vs_e1), ('Expert 2', vs_e2), ('Consensus', vs_consensus)]:
        pe_ok = scores['pe']['f1'] >= 80
        oe_ok = scores['oe']['f1'] >= 85
        rd_ok = scores['rd']['accuracy'] >= 90
        ok = pe_ok and oe_ok and rd_ok
        status = 'PASSED' if ok else 'NEEDS IMPROVEMENT'
        mark_pe = 'OK' if pe_ok else '!!'
        mark_oe = 'OK' if oe_ok else '!!'
        mark_rd = 'OK' if rd_ok else '!!'
        print(f"  vs {label:<12} [{mark_pe}] PE F1={scores['pe']['f1']}%  [{mark_oe}] OE F1={scores['oe']['f1']}%  [{mark_rd}] RD={scores['rd']['accuracy']}%  → {status}")
        if not ok:
            all_ok = False

    if all_ok:
        print(f"\n    >>> DUAL-EXPERT VALIDATION: PASSED <<<")
    else:
        print(f"\n    >>> DUAL-EXPERT VALIDATION: PARTIALLY PASSED <<<")
    print(f"{sep}\n")

    return all_ok


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="Level 2 Dual-Expert Gold Standard Scoring")
    parser.add_argument('--csv1', default='gold_standard_annotation.csv',
                        help='Path to Expert 1 CSV (semicolon-delimited)')
    parser.add_argument('--csv2', default='gold_standard_annotation_2.csv',
                        help='Path to Expert 2 file (XLSX format with .csv extension)')
    parser.add_argument('--json', default='gold_standard_annotation.json',
                        help='Path to JSON with full abstracts (for --rerun-nlp)')
    parser.add_argument('--rerun-nlp', action='store_true',
                        help='Re-run NLP modules using latest code')
    parser.add_argument('--output', '-o', default=None,
                        help='Output JSON results file')
    args = parser.parse_args()

    # Validate inputs
    for path, label in [(args.csv1, 'Expert 1'), (args.csv2, 'Expert 2')]:
        if not os.path.exists(path):
            print(f"[ERROR] {label} file not found: {path}")
            sys.exit(1)

    # Read both experts
    e1_articles = read_expert1(args.csv1)
    e2_articles = read_expert2(args.csv2)
    print(f"Expert 1: {len(e1_articles)} articles from {args.csv1}")
    print(f"Expert 2: {len(e2_articles)} articles from {args.csv2}")

    # Merge
    articles = merge_experts(e1_articles, e2_articles)
    print(f"Merged: {len(articles)} articles")

    # Re-run NLP if requested
    if args.rerun_nlp:
        json_path = args.json
        if not os.path.exists(json_path):
            print(f"[ERROR] JSON file not found: {json_path}")
            sys.exit(1)

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

            art['nlp_sample_size'] = ParticipantExtractor.extract_sample_size(abstract).get('sample_size')
            art['nlp_primary_outcome'] = bool(OutcomeExtractor.extract_outcomes(abstract).get('primary_outcome'))
            art['nlp_region'] = get_region_from_affiliation(affiliation) or ''
            n_updated += 1

        print(f"[RERUN-NLP] Updated {n_updated}/{len(articles)} articles")

    # Data quality
    for prefix, label in [('e1', 'Expert 1'), ('e2', 'Expert 2')]:
        n_ss = sum(1 for a in articles if a.get(f'{prefix}_sample_size') is not None)
        n_po = sum(1 for a in articles if a.get(f'{prefix}_primary_outcome') is not None)
        n_rg = sum(1 for a in articles if a.get(f'{prefix}_region'))
        print(f"{label} annotated: sample_size={n_ss}  primary_outcome={n_po}  region={n_rg}")

    # Score NLP vs Expert 1
    vs_e1 = {
        'pe': score_pe(articles, 'e1_sample_size'),
        'oe': score_oe(articles, 'e1_primary_outcome'),
        'rd': score_rd(articles, 'e1_region'),
    }

    # Score NLP vs Expert 2
    vs_e2 = {
        'pe': score_pe(articles, 'e2_sample_size'),
        'oe': score_oe(articles, 'e2_primary_outcome'),
        'rd': score_rd(articles, 'e2_region'),
    }

    # Inter-rater agreement
    inter_rater = compute_inter_rater(articles)

    # Consensus scoring
    articles = build_consensus(articles)
    vs_consensus = {
        'pe': score_pe(articles, 'consensus_sample_size'),
        'oe': score_oe(articles, 'consensus_primary_outcome'),
        'rd': score_rd(articles, 'consensus_region'),
    }

    # Report
    verdict = print_full_report(articles, vs_e1, vs_e2, vs_consensus, inter_rater)

    # Save JSON
    def strip_details(d):
        return {k: v for k, v in d.items() if k != 'details'}

    outfile = args.output or 'results_dual_experts.json'
    results = {
        'meta': {
            'date': datetime.now().isoformat(),
            'expert1_file': args.csv1,
            'expert2_file': args.csv2,
            'total_articles': len(articles),
            'rerun_nlp': args.rerun_nlp,
        },
        'inter_rater_agreement': {
            'pe': {k: v for k, v in inter_rater['pe'].items() if k != 'disagree_details'},
            'oe': inter_rater['oe'],
            'rd': inter_rater['rd'],
        },
        'nlp_vs_expert1': {k: strip_details(v) for k, v in vs_e1.items()},
        'nlp_vs_expert2': {k: strip_details(v) for k, v in vs_e2.items()},
        'nlp_vs_consensus': {k: strip_details(v) for k, v in vs_consensus.items()},
        'errors': {
            'pe_vs_e1': vs_e1['pe']['details'],
            'pe_vs_e2': vs_e2['pe']['details'],
            'oe_vs_e1': vs_e1['oe']['details'],
            'oe_vs_e2': vs_e2['oe']['details'],
            'rd_vs_e1': vs_e1['rd']['details'],
            'rd_vs_e2': vs_e2['rd']['details'],
            'pe_inter_rater_disagree': inter_rater['pe']['disagree_details'],
        },
        'verdict': 'PASSED' if verdict else 'PARTIALLY_PASSED',
    }

    with open(outfile, 'w', encoding='utf-8') as f:
        json.dump(results, f, indent=2, ensure_ascii=False)
    print(f"[SAVE] {outfile}")


if __name__ == '__main__':
    main()
