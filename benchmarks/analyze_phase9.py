"""Detailed analysis of PE errors and OE FN/FP using stored articles."""
import json, sys, os, re

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ['DJANGO_SETTINGS_MODULE'] = 'config.settings'

import django
django.setup()

from search.services.participant_extractor import ParticipantExtractor
from search.services.outcome_extractor import OutcomeExtractor

# Load articles
arts = json.load(open('benchmarks/benchmark_articles_200.json', encoding='utf-8'))
art_map = {str(a.get('pmid', '')): a for a in arts}

# Load benchmark results for GS
results = json.load(open('benchmark_results_v2_200.json', encoding='utf-8'))

pe = ParticipantExtractor()
oe = OutcomeExtractor()

# ==================== PE ERRORS ====================
print("=" * 80)
print("PARTICIPANT EXTRACTOR — TOP ERRORS (pred ~ 2*GS = multi-arm doubling?)")
print("=" * 80)

pe_errors = results['participant_extractor']['worst_errors']
for err in pe_errors[:8]:
    pmid = err['pmid']
    gs = err['gs']
    pred_from_result = err['pred']
    
    art = art_map.get(pmid)
    if not art:
        continue
    abstract = art.get('abstract', '')
    
    # Re-extract to get details
    result = pe.extract_sample_size(abstract)
    count = result.get('count')
    confidence = result.get('confidence', 0)
    if isinstance(confidence, str):
        try:
            confidence = float(confidence)
        except:
            confidence = 0.0
    
    ratio = pred_from_result / gs if gs else 0
    
    print(f"\n{'='*70}")
    print(f"PMID {pmid}: GS={gs}, pred={pred_from_result}, delta={err['error']}, ratio={ratio:.2f}")
    print(f"  Re-extracted: count={count}, confidence={confidence:.3f}")
    print(f"{'='*70}")
    
    # Find all numbers in abstract with participant words
    num_matches = re.findall(r'(\d[\d,]*)\s*(?:patients?|participants?|subjects?|individuals?|women|men|children|adults)', abstract, re.I)
    if num_matches:
        print(f"  Numbers near participant words: {num_matches}")
    
    # Find (n=X) patterns
    nequals = re.findall(r'\(n\s*=\s*(\d+)\)', abstract, re.I)
    if nequals:
        nums = [int(x) for x in nequals]
        print(f"  (n=X) values: {nequals} -> sum={sum(nums)}")
    
    # Find "randomized to" patterns
    rand_to = re.findall(r'(?:randomized|assigned|allocated)\s+(?:to\s+)?(?:receive\s+)?[^.]{0,50}?\(n\s*=\s*(\d+)\)', abstract, re.I)
    if rand_to:
        nums = [int(x) for x in rand_to]
        print(f"  Randomized-to (n=X): {rand_to} -> sum={sum(nums)}")
    
    # Find "total of X"
    total_of = re.findall(r'(?:total\s+of|altogether)\s+(\d[\d,]*)', abstract, re.I)
    if total_of:
        print(f"  'total of X' matches: {total_of}")
    
    were_rand = re.findall(r'(\d[\d,]*)\s+(?:patients?|participants?|subjects?)\s+(?:were\s+)?(?:randomized|randomly\s+assigned|enrolled)', abstract, re.I)
    if were_rand:
        print(f"  'X were randomized' matches: {were_rand}")
    
    # Print key sentences
    sentences = abstract.split('. ')
    for i, s in enumerate(sentences):
        s_lower = s.lower()
        if any(w in s_lower for w in ['randomiz', 'enroll', 'assign', 'allocat', 'recruit', 'n=', 'n =']):
            print(f"  KEY [{i}]: {s.strip()}")
    print()


# ==================== OE FALSE NEGATIVES ====================
print("\n" + "=" * 80)
print("OUTCOME EXTRACTOR --- FALSE NEGATIVES")
print("=" * 80)

oe_fns = results['outcome_extractor']['false_negatives']
for fn_item in oe_fns:
    pmid = fn_item['pmid']
    art = art_map.get(pmid)
    if not art:
        continue
    abstract = art.get('abstract', '')
    
    result = oe.extract_outcomes(abstract)
    
    print(f"\n{'='*70}")
    print(f"PMID {pmid}: has_outcome={result.get('has_primary_outcome')}, conf={result.get('confidence', 0):.2f}")
    print(f"  Primary: {(result.get('primary_outcome') or 'NONE')[:200]}")
    print(f"{'='*70}")
    
    sentences = abstract.split('. ')
    for i, s in enumerate(sentences):
        s_lower = s.lower()
        if any(w in s_lower for w in ['primary', 'outcome', 'endpoint', 'end point', 'end-point', 'objective', 'aim', 'purpose', 'assess', 'evaluate', 'efficacy', 'main']):
            print(f"  >>> [{i}]: {s.strip()}")
    print()


# ==================== OE FALSE POSITIVES ====================
print("\n" + "=" * 80)
print("OUTCOME EXTRACTOR --- FALSE POSITIVES")
print("=" * 80)

oe_fps = results['outcome_extractor']['false_positives']
for fp_item in oe_fps:
    pmid = fp_item['pmid']
    art = art_map.get(pmid)
    if not art:
        continue
    abstract = art.get('abstract', '')
    
    result = oe.extract_outcomes(abstract)
    
    print(f"\n{'='*70}")
    print(f"PMID {pmid}: has_outcome={result.get('has_primary_outcome')}, conf={result.get('confidence', 0):.2f}")
    print(f"  Extracted: {(result.get('primary_outcome') or 'NONE')[:200]}")
    print(f"{'='*70}")
    
    sentences = abstract.split('. ')
    for i, s in enumerate(sentences):
        s_lower = s.lower()
        if any(w in s_lower for w in ['primary', 'outcome', 'endpoint', 'end point', 'main outcome', 'end-point']):
            print(f"  >>> [{i}]: {s.strip()}")
    print()