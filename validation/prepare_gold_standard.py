#!/usr/bin/env python
"""
prepare_gold_standard.py — Prépare 100 articles pour annotation humaine (Niveau 2)
===================================================================================
Sélectionne 10 articles par spécialité depuis les articles du benchmark multi-
spécialités, et génère :
  1. gold_standard_annotation.json  — fichier d'annotation (à remplir par un humain)
  2. gold_standard_annotation.csv   — version CSV pour annotation dans Excel/Sheets

L'annotateur doit remplir :
  - sample_size_human    : nombre de participants (int ou null)
  - primary_outcome_human: true/false (abstract mentionne un primary outcome?)
  - outcome_text_human   : texte du primary outcome (si applicable)
  - country_human        : pays de l'affiliation du dernier auteur
  - region_human         : region (europe, asia, north_america, south_america, africa, oceania)
  - notes                : commentaires optionnels

Usage:
  python prepare_gold_standard.py [--input benchmark_articles_multispecialty_717.json]
  python prepare_gold_standard.py --validate gold_standard_annotation.json
"""

import json
import csv
import random
import argparse
import os
import sys

# ── Django bootstrap ────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

ARTICLES_PER_SPECIALTY = 10

VALID_REGIONS = {'europe', 'asia', 'north_america', 'south_america', 'africa', 'oceania', ''}


def select_articles(articles: list, per_specialty: int = ARTICLES_PER_SPECIALTY) -> list:
    """Select N articles per specialty, prioritizing those with abstracts."""
    by_specialty = {}
    for art in articles:
        spec = art.get('_specialty', 'unknown')
        if spec not in by_specialty:
            by_specialty[spec] = []
        by_specialty[spec].append(art)

    selected = []
    for spec, arts in sorted(by_specialty.items()):
        # Prioritize articles with abstracts (more useful for annotation)
        with_abstract = [a for a in arts if a.get('abstract', '').strip()]
        without_abstract = [a for a in arts if not a.get('abstract', '').strip()]

        pool = with_abstract + without_abstract
        random.seed(42)  # Reproducible
        random.shuffle(pool)

        n = min(per_specialty, len(pool))
        chosen = pool[:n]
        print(f"  {spec}: {n}/{len(pool)} articles sélectionnés ({len(with_abstract)} avec abstract)")
        selected.extend(chosen)

    return selected


def generate_annotation_json(selected: list, output_path: str):
    """Generate JSON annotation file with pre-filled NLP predictions."""
    annotations = []
    for i, art in enumerate(selected, 1):
        entry = {
            "id": i,
            "pmid": art.get('pmid', ''),
            "specialty": art.get('_specialty', 'unknown'),
            "title": art.get('title', '')[:200],
            "abstract": art.get('abstract', ''),
            "affiliation": art.get('affiliation', '') or art.get('last_author_affiliation', ''),

            # NLP predictions (pre-filled for reference)
            "nlp_sample_size": art.get('sample_size'),
            "nlp_primary_outcome": art.get('primary_outcome') is not None,
            "nlp_outcome_text": str(art.get('primary_outcome', ''))[:200] if art.get('primary_outcome') else None,
            "nlp_region": art.get('region', ''),
            "nlp_country": art.get('country', ''),

            # === HUMAN ANNOTATION (À REMPLIR) ===
            "sample_size_human": None,          # int — nombre exact de participants
            "primary_outcome_human": None,       # bool — l'abstract mentionne-t-il un primary outcome?
            "outcome_text_human": None,          # str — texte du primary outcome (copier-coller)
            "country_human": None,               # str — pays (ex: "france", "united states")
            "region_human": None,                # str — region (europe, asia, north_america, etc.)
            "notes": "",                         # str — commentaires optionnels
        }
        annotations.append(entry)

    with open(output_path, 'w', encoding='utf-8') as f:
        json.dump(annotations, f, indent=2, ensure_ascii=False)
    print(f"\n💾 JSON: {output_path} ({len(annotations)} articles)")


def generate_annotation_csv(selected: list, output_path: str):
    """Generate CSV for annotation in Excel/Google Sheets."""
    fieldnames = [
        'id', 'pmid', 'specialty', 'title',
        'abstract_first_200chars',
        'affiliation',
        'nlp_sample_size', 'nlp_primary_outcome', 'nlp_region',
        'sample_size_human', 'primary_outcome_human', 'outcome_text_human',
        'country_human', 'region_human', 'notes',
    ]

    with open(output_path, 'w', newline='', encoding='utf-8-sig') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames, delimiter=';')
        writer.writeheader()
        for i, art in enumerate(selected, 1):
            writer.writerow({
                'id': i,
                'pmid': art.get('pmid', ''),
                'specialty': art.get('_specialty', ''),
                'title': art.get('title', '')[:200],
                'abstract_first_200chars': art.get('abstract', '')[:200],
                'affiliation': (art.get('affiliation', '') or art.get('last_author_affiliation', ''))[:200],
                'nlp_sample_size': art.get('sample_size', ''),
                'nlp_primary_outcome': 'TRUE' if art.get('primary_outcome') else 'FALSE',
                'nlp_region': art.get('region', ''),
                'sample_size_human': '',
                'primary_outcome_human': '',
                'outcome_text_human': '',
                'country_human': '',
                'region_human': '',
                'notes': '',
            })
    print(f"💾 CSV:  {output_path} ({len(selected)} articles)")


def validate_annotations(annotation_path: str):
    """Validate and score human annotations against NLP predictions."""
    with open(annotation_path, 'r', encoding='utf-8') as f:
        data = json.load(f)

    print(f"\n📋 Validation du gold standard: {annotation_path}")
    print(f"   Articles: {len(data)}")

    # Check completeness
    incomplete = 0
    annotated = 0
    for entry in data:
        if entry.get('sample_size_human') is None and entry.get('primary_outcome_human') is None and entry.get('region_human') is None:
            incomplete += 1
        else:
            annotated += 1

    print(f"   Annotés: {annotated}  |  Non annotés: {incomplete}")

    if annotated == 0:
        print("   ⚠ Aucun article annotée. Remplissez les champs *_human puis re-validez.")
        return

    # Validate regions
    invalid_regions = []
    for entry in data:
        r = entry.get('region_human', '')
        if r and r not in VALID_REGIONS:
            invalid_regions.append((entry['id'], entry['pmid'], r))
    if invalid_regions:
        print(f"\n   ⚠ Régions invalides ({len(invalid_regions)}):")
        for eid, pmid, r in invalid_regions[:5]:
            print(f"     #{eid} PMID {pmid}: '{r}' (valides: {VALID_REGIONS})")

    # ── Score: ParticipantExtractor ──
    pe_tp = pe_fp = pe_fn = 0
    pe_errors = []
    pe_annotated = 0

    for entry in data:
        gs = entry.get('sample_size_human')
        pred = entry.get('nlp_sample_size')
        if gs is None:
            continue
        pe_annotated += 1
        if pred is not None:
            err = abs(pred - gs)
            pe_errors.append(err)
            if err <= max(5, gs * 0.1):
                pe_tp += 1
            else:
                pe_fp += 1
        elif gs > 0:
            pe_fn += 1

    if pe_annotated > 0:
        pe_mae = sum(pe_errors) / len(pe_errors) if pe_errors else 0
        pe_prec = pe_tp / (pe_tp + pe_fp) if (pe_tp + pe_fp) else 0
        pe_rec = pe_tp / (pe_tp + pe_fn) if (pe_tp + pe_fn) else 0
        pe_f1 = 2 * pe_prec * pe_rec / (pe_prec + pe_rec) if (pe_prec + pe_rec) else 0
        print(f"\n   📊 ParticipantExtractor (n={pe_annotated}):")
        print(f"      MAE = {pe_mae:.1f}  |  F1 = {pe_f1*100:.1f}%  |  P = {pe_prec*100:.1f}%  R = {pe_rec*100:.1f}%")

    # ── Score: OutcomeExtractor ──
    oe_tp = oe_fp = oe_fn = oe_tn = 0
    oe_annotated = 0

    for entry in data:
        gs = entry.get('primary_outcome_human')
        if gs is None:
            continue
        oe_annotated += 1
        pred = entry.get('nlp_primary_outcome', False)
        if gs and pred:
            oe_tp += 1
        elif gs and not pred:
            oe_fn += 1
        elif not gs and pred:
            oe_fp += 1
        else:
            oe_tn += 1

    if oe_annotated > 0:
        oe_prec = oe_tp / (oe_tp + oe_fp) if (oe_tp + oe_fp) else 0
        oe_rec = oe_tp / (oe_tp + oe_fn) if (oe_tp + oe_fn) else 0
        oe_f1 = 2 * oe_prec * oe_rec / (oe_prec + oe_rec) if (oe_prec + oe_rec) else 0
        print(f"\n   📊 OutcomeExtractor (n={oe_annotated}):")
        print(f"      F1 = {oe_f1*100:.1f}%  |  P = {oe_prec*100:.1f}%  R = {oe_rec*100:.1f}%")
        print(f"      TP={oe_tp} FP={oe_fp} FN={oe_fn} TN={oe_tn}")

    # ── Score: RegionDetector ──
    rd_tp = rd_fp = 0
    rd_annotated = 0

    for entry in data:
        gs = entry.get('region_human', '')
        if not gs:
            continue
        rd_annotated += 1
        pred = entry.get('nlp_region', '')
        if pred == gs:
            rd_tp += 1
        else:
            rd_fp += 1
            print(f"      RD mismatch #{entry['id']}: GS='{gs}' pred='{pred}' — {entry.get('affiliation', '')[:80]}")

    if rd_annotated > 0:
        rd_acc = rd_tp / rd_annotated
        print(f"\n   📊 RegionDetector (n={rd_annotated}):")
        print(f"      Accuracy = {rd_acc*100:.1f}%  ({rd_tp}/{rd_annotated} correct)")

    # Summary
    print(f"\n   {'═' * 50}")
    print(f"   RÉSUMÉ GOLD STANDARD (annotations humaines)")
    print(f"   {'═' * 50}")
    if pe_annotated:
        print(f"   PE: MAE={pe_mae:.1f}  F1={pe_f1*100:.1f}%  (n={pe_annotated})")
    if oe_annotated:
        print(f"   OE: F1={oe_f1*100:.1f}%  (n={oe_annotated})")
    if rd_annotated:
        print(f"   RD: Acc={rd_acc*100:.1f}%  (n={rd_annotated})")
    print()


def main():
    parser = argparse.ArgumentParser(description="Prepare gold standard for human annotation (Level 2)")
    parser.add_argument('--input', '-i', type=str,
                        default='benchmark_articles_multispecialty_717.json',
                        help='Input articles JSON from Level 1 benchmark')
    parser.add_argument('--output', '-o', type=str,
                        default='gold_standard_annotation',
                        help='Output base name (without extension)')
    parser.add_argument('--per-specialty', '-n', type=int, default=10,
                        help='Articles per specialty (default: 10)')
    parser.add_argument('--validate', '-v', type=str,
                        help='Validate and score a completed annotation file')
    args = parser.parse_args()

    if args.validate:
        validate_annotations(args.validate)
        return

    # Load articles
    if not os.path.exists(args.input):
        print(f"❌ Fichier introuvable: {args.input}")
        print(f"   Lancez d'abord: python benchmark_multispecialty.py --save-articles")
        return

    print(f"\n📂 Chargement: {args.input}")
    with open(args.input, 'r', encoding='utf-8') as f:
        articles = json.load(f)
    print(f"   {len(articles)} articles chargés")

    # Select diverse subset
    print(f"\n🎯 Sélection de {args.per_specialty} articles par spécialité:")
    selected = select_articles(articles, args.per_specialty)

    # Generate annotation files
    generate_annotation_json(selected, f"{args.output}.json")
    generate_annotation_csv(selected, f"{args.output}.csv")

    print(f"\n📋 INSTRUCTIONS D'ANNOTATION:")
    print(f"   1. Ouvrez {args.output}.json (ou .csv dans Excel)")
    print(f"   2. Pour chaque article, remplissez les champs *_human:")
    print(f"      - sample_size_human    : nombre exact de participants (int ou null si pas trouvé)")
    print(f"      - primary_outcome_human: true si l'abstract mentionne un primary outcome, false sinon")
    print(f"      - outcome_text_human   : texte exact du primary outcome (copier-coller de l'abstract)")
    print(f"      - country_human        : pays (lowercase, ex: 'france', 'united states')")
    print(f"      - region_human         : region parmi {VALID_REGIONS}")
    print(f"   3. Validez avec: python prepare_gold_standard.py --validate {args.output}.json")
    print()


if __name__ == '__main__':
    main()
