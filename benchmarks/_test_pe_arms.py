#!/usr/bin/env python
"""Quick test: examine multi-arm abstracts for PE errors."""
import json, re

with open('gold_standard_annotation.json', 'r', encoding='utf-8') as f:
    data = json.load(f)

for a in data:
    aid = a['id']
    if aid in [4, 41, 72, 25, 8]:
        abstract = a.get('abstract', '')
        arms = re.findall(r'[\(\[]\s*[Nn]\s*=\s*(\d[\d,]*)\s*[\)\]]', abstract)
        simple = re.findall(r'(\d+)\s+(?:patients?|participants?)', abstract)
        pmid = a['pmid']
        print(f"Article {aid} (pmid={pmid}):")
        print(f"  (n=X) arms: {arms}")
        print(f"  X patients: {simple[:5]}")
        for m in re.finditer(r'(?:randomiz|assigned|group)', abstract, re.IGNORECASE):
            s = max(0, m.start() - 20)
            e = min(len(abstract), m.end() + 150)
            print(f"  >>> {abstract[s:e]}")
            break
        print()
