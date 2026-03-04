"""Analyze worst ParticipantExtractor errors from benchmark"""
import json
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from search.services.participant_extractor import ParticipantExtractor

with open('benchmarks/benchmark_articles_200.json', 'r', encoding='utf-8') as f:
    articles = json.load(f)

worst = ['24068158', '27687471', '39969869', '33439221', '34668963', 
         '33760010', '38381428', '31968063', '38630471', '25442065']

for a in articles:
    pmid = a.get('pmid', '')
    if pmid in worst:
        abstract = a.get('abstract', '')
        result = ParticipantExtractor.extract_sample_size(abstract)
        
        print(f"=== PMID {pmid} ===")
        print(f"Predicted: {result['sample_size']} (method: {result['method']}, conf: {result['confidence']})")
        print(f"Matched: '{result['matched_text']}'")
        print(f"Abstract (first 500 chars):")
        print(abstract[:500])
        print()
