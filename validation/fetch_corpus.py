#!/usr/bin/env python
"""
fetch_corpus.py — Rebuild the N1 and N2 validation corpora from PubMed
======================================================================
The abstracts used in the article are not redistributed (publisher copyright).
This script downloads them again by PMID through NCBI efetch and parses them
with the application's own parser (search.services.pubmed_client), so the
abstract and last-author affiliation are exactly what MedLitSearch sees.

Usage:
  python validation/fetch_corpus.py n1 --pmids validation/n1_pmids.txt \
      --out validation/data/benchmark_articles_200.json
  python validation/fetch_corpus.py n2 --annotations validation/data/N2_expert1_annotations.csv \
      --out validation/data/gold_standard_annotation.json

Requires network access, NCBI_API_KEY and NCBI_EMAIL (read from .env).
"""

import os
import sys
import csv
import json
import time
import argparse
from typing import Dict, List

# ── Django bootstrap ────────────────────────────────────────────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")
import django
django.setup()

from search.services.pubmed_client import _request, _parse_article_xml

BATCH_SIZE = 100


def fetch_by_pmids(pmids: List[str]) -> Dict[str, Dict]:
    """Fetch and parse PubMed records for the given PMIDs, keyed by PMID."""
    articles = {}
    for i in range(0, len(pmids), BATCH_SIZE):
        batch = pmids[i:i + BATCH_SIZE]
        response = _request("efetch.fcgi", {"db": "pubmed", "id": ",".join(batch), "retmode": "xml"})
        for art in _parse_article_xml(response.text):
            articles[str(art["pmid"])] = art
        print(f"  fetched {min(i + BATCH_SIZE, len(pmids))}/{len(pmids)}")
        time.sleep(0.4)  # Respect NCBI rate limits
    missing = [p for p in pmids if p not in articles]
    if missing:
        print(f"[ERROR] {len(missing)} PMIDs not returned by PubMed: {missing}")
        sys.exit(1)
    return articles


def build_n1(pmids_path: str) -> List[Dict]:
    """N1 corpus: full article dictionaries, in the order of the PMID list."""
    with open(pmids_path, "r", encoding="utf-8") as f:
        pmids = [line.strip() for line in f if line.strip() and not line.startswith("#")]
    fetched = fetch_by_pmids(pmids)
    return [fetched[p] for p in pmids]


def build_n2(annotations_path: str) -> List[Dict]:
    """N2 corpus: id, pmid, abstract and last-author affiliation, as read by score_dual_experts.py."""
    with open(annotations_path, "r", encoding="utf-8-sig") as f:
        rows = list(csv.DictReader(f, delimiter=";"))
    fetched = fetch_by_pmids([r["pmid"].strip() for r in rows])
    corpus = []
    for r in rows:
        art = fetched[r["pmid"].strip()]
        corpus.append({
            "id": int(r["id"]),
            "pmid": art["pmid"],
            "specialty": r.get("specialty", ""),
            "title": art["title"],
            "abstract": art["abstract"],
            "affiliation": art["last_author_affiliation"],
        })
    return corpus


def main():
    parser = argparse.ArgumentParser(description="Rebuild N1/N2 validation corpora from PubMed by PMID")
    sub = parser.add_subparsers(dest="corpus", required=True)
    p1 = sub.add_parser("n1", help="N1 benchmark corpus (200 RCT abstracts)")
    p1.add_argument("--pmids", required=True, help="Text file with one PMID per line")
    p1.add_argument("--out", required=True, help="Output JSON path")
    p2 = sub.add_parser("n2", help="N2 expert-annotated corpus (100 articles)")
    p2.add_argument("--annotations", required=True, help="N2_expert1_annotations.csv (Zenodo)")
    p2.add_argument("--out", required=True, help="Output JSON path")
    args = parser.parse_args()

    corpus = build_n1(args.pmids) if args.corpus == "n1" else build_n2(args.annotations)

    os.makedirs(os.path.dirname(os.path.abspath(args.out)), exist_ok=True)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(corpus, f, indent=2, ensure_ascii=False, default=str)
    print(f"[SAVE] {len(corpus)} articles -> {args.out}")


if __name__ == "__main__":
    main()
