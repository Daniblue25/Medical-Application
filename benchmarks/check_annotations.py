#!/usr/bin/env python
"""Quick check of the human annotations in the CSV."""
import csv
import sys

def main():
    with open('gold_standard_annotation.csv', 'r', encoding='utf-8-sig') as f:
        reader = csv.DictReader(f, delimiter=';')
        rows = list(reader)

    print(f"Total articles: {len(rows)}")
    print(f"Fields: {list(rows[0].keys())}")
    print()

    key_fields = ['sample_size_human', 'primary_outcome_human', 'country_human', 'region_human']
    
    print("=== CHAMPS MANQUANTS (cles) ===")
    missing_count = 0
    for r in rows:
        missing = [k for k in key_fields if r.get(k, '').strip() in ('', 'null', 'None')]
        if missing:
            missing_count += 1
            print(f"  ID {r['id']:>3} PMID {r['pmid']} [{r['specialty']}] manque: {missing}")
    
    if missing_count == 0:
        print("  Aucun champ manquant!")
    print(f"\n  Total: {missing_count} articles avec champs manquants")

    print("\n=== OUTCOME_TEXT ABSENT QUAND PRIMARY_OUTCOME = True ===")
    ot_missing = 0
    for r in rows:
        po = r.get('primary_outcome_human', '').strip().lower()
        ot = r.get('outcome_text_human', '').strip()
        if po in ('true', '1', 'yes', 'oui') and ot in ('', 'null', 'None', 'na', 'NA'):
            ot_missing += 1
            print(f"  ID {r['id']:>3} [{r['specialty']}] primary_outcome=True mais outcome_text manquant")
    if ot_missing == 0:
        print("  Aucun cas!")

    print("\n=== SAMPLE VALUES (premiers 10) ===")
    for r in rows[:10]:
        nlp_ss = r.get('nlp_sample_size', '')
        h_ss = r.get('sample_size_human', '')
        nlp_po = r.get('nlp_primary_outcome', '')
        h_po = r.get('primary_outcome_human', '')
        nlp_r = r.get('nlp_region', '')
        h_r = r.get('region_human', '')
        h_c = r.get('country_human', '')
        print(f"  ID {r['id']:>3}: SS nlp={nlp_ss:>6} human={h_ss:>6} | PO nlp={nlp_po:<6} human={h_po:<6} | Region nlp={nlp_r:<15} human={h_r:<15} | Country={h_c}")

    # Check for data quality issues
    print("\n=== VERIFICATION QUALITE ===")
    
    # Primary outcome should be True/False
    po_values = set()
    for r in rows:
        po = r.get('primary_outcome_human', '').strip()
        if po:
            po_values.add(po)
    print(f"  primary_outcome_human values: {po_values}")
    
    # Region values
    region_values = set()
    for r in rows:
        reg = r.get('region_human', '').strip()
        if reg:
            region_values.add(reg)
    print(f"  region_human values: {region_values}")

    # Sample size should be numeric
    non_numeric_ss = []
    for r in rows:
        ss = r.get('sample_size_human', '').strip()
        if ss and ss not in ('', 'null', 'None', 'na', 'NA'):
            try:
                int(ss.replace(',', ''))
            except ValueError:
                non_numeric_ss.append((r['id'], ss))
    if non_numeric_ss:
        print(f"  sample_size_human non-numerique: {non_numeric_ss}")
    else:
        print(f"  sample_size_human: tous numeriques (OK)")

if __name__ == '__main__':
    main()
