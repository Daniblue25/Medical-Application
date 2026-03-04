"""Analyze benchmark_results_v2_200.json for remaining errors to fix."""
import json
import sys
import os

with open(os.path.join(os.path.dirname(__file__), '..', 'benchmark_results_v2_200.json')) as f:
    data = json.load(f)

# Top PE errors
print("=== TOP ParticipantExtractor ERRORS ===")
pe = data["participant_extractor"]
errors = pe.get("top_errors", [])
for e in errors:
    pmid = e["pmid"]
    gs = e["gs"]
    pred = e["pred"]
    delta = e["delta"]
    print(f"  PMID {pmid}: GS={gs} pred={pred} delta={delta}")

# OE False Negatives
print()
print("=== OutcomeExtractor FALSE NEGATIVES ===")
oe = data["outcome_extractor"]
for fn in oe.get("false_negatives", []):
    pmid = fn["pmid"]
    snippet = fn["abstract_snippet"][:150]
    print(f"  PMID {pmid}: {snippet}")

# OE False Positives
print()
print("=== OutcomeExtractor FALSE POSITIVES ===")
for fp in oe.get("false_positives", []):
    pmid = fp["pmid"]
    extracted = fp["extracted"][:150]
    print(f"  PMID {pmid}: {extracted}")

# Get PMIDs for detailed analysis
print()
print("=== PMIDs for detailed analysis ===")
error_pmids = [str(e["pmid"]) for e in errors]
fn_pmids = [str(fn["pmid"]) for fn in oe.get("false_negatives", [])]
fp_pmids = [str(fp["pmid"]) for fp in oe.get("false_positives", [])]
print(f"PE errors: {', '.join(error_pmids)}")
print(f"OE FN: {', '.join(fn_pmids)}")
print(f"OE FP: {', '.join(fp_pmids)}")
