"""Deep analysis of worst ParticipantExtractor errors"""
import json, re, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from search.services.participant_extractor import ParticipantExtractor

with open('benchmarks/benchmark_articles_200.json', 'r', encoding='utf-8') as f:
    articles = json.load(f)

worst = {
    '24068158': 80, '27687471': 4908, '39969869': 3971,
    '33439221': 1645, '34668963': 528, '33760010': 481,
    '38381428': 292, '31968063': 418, '38630471': 301,
    '25442065': 26
}

for a in articles:
    pmid = a.get('pmid', '')
    if pmid in worst:
        abstract = a.get('abstract', '')
        result = ParticipantExtractor.extract_sample_size(abstract)
        gs = worst[pmid]
        pred = result['sample_size']
        
        # Find ALL numbers with patient/participant context
        all_nums = re.findall(
            r'(\d[\d,]*)\s+(?:patients?|participants?|subjects?|individuals?)',
            abstract, re.IGNORECASE
        )
        total_refs = re.findall(
            r'total\s+of\s+(\d[\d,]*)',
            abstract, re.IGNORECASE
        )
        n_refs = re.findall(
            r'[Nn]\s*=\s*(\d[\d,]*)',
            abstract
        )
        
        print(f"=== PMID {pmid} ===")
        print(f"GS={gs}, Pred={pred}, Delta={abs(gs-pred) if pred else 'N/A'}")
        print(f"Method: {result['method']}, Matched: '{result['matched_text']}'")
        print(f"All number+patient refs: {all_nums}")
        print(f"Total-of refs: {total_refs}")
        print(f"N= refs: {n_refs}")
        print(f"Abstract:")
        print(abstract[:1200])
        print()
        print("="*80)
        print()
