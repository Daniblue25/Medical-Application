# Validation & reproducibility

This folder contains the scripts and tests used to validate MedLitSearch in the
accompanying article. The annotation data are archived on Zenodo
(DOI [10.5281/zenodo.21873453](https://doi.org/10.5281/zenodo.21873453)) and are
**not** stored in this repository. The PubMed abstracts are not redistributed
(publisher copyright). They are downloaded again by PMID with `fetch_corpus.py`.

All extractors are deterministic: the same abstract always yields the same value.

## Contents

| File | Purpose |
| --- | --- |
| `test_search_retrieval.py` | PubMed retrieval validation: 251 tests (query building, journal and publication-type filters, PMID lookup, keyword retrieval) |
| `test_end_to_end.py` | End-to-end pipeline: PubMed fetch → extraction → API → Excel export (live PubMed) |
| `test_regression_nlp.py` | Non-regression floors for the extractors, computed on a saved corpus (skipped if no corpus is present) |
| `fetch_corpus.py` | Rebuilds the N1 and N2 corpora from PubMed, by PMID |
| `n1_pmids.txt` | The 200 PMIDs of the N1 benchmark corpus |
| `benchmark_nlp_v2.py` | N1 benchmark: extractors vs an automatic heuristic reference |
| `score_dual_experts.py` | N2 scoring: extractors vs two blinded experts, inter-rater κ, consensus |
| `score_gold_standard.py` | Earlier single-expert N2 scoring (superseded by `score_dual_experts.py`) |
| `prepare_gold_standard.py` | How the N2 annotation sample was drawn (needs the 717-article multi-specialty corpus, which is not distributed) |

## 1. Setup

```bash
pip install -r requirements.txt
cp .env.example .env      # then set NCBI_API_KEY and NCBI_EMAIL
```

Everything that calls PubMed (`fetch_corpus.py` and the tests marked `network`)
needs network access, `NCBI_API_KEY` and `NCBI_EMAIL`. You can get an NCBI API
key from your NCBI account settings.

On Windows, set `PYTHONIOENCODING=utf-8` before redirecting script output to a file.

## 2. Data

Download the nine files of the Zenodo record into `validation/data/`. This
folder is git-ignored. `10.5281/zenodo.21873453` is the concept DOI, which
covers all versions. The files below come from version 1,
`10.5281/zenodo.21873892`.

```bash
mkdir -p validation/data
for f in N1_benchmark_results.csv N2_expert1_annotations.csv N2_expert2_annotations.csv \
         N2_system_outputs.csv N2_scoring_results.csv published_tables_source.xlsx \
         data_dictionary.md metadata.json LICENSE_DATA.txt; do
  curl -L -o "validation/data/$f" "https://zenodo.org/records/21873892/files/$f?download=1"
done
```

Then rebuild the two corpora from PubMed:

```bash
python validation/fetch_corpus.py n1 --pmids validation/n1_pmids.txt \
    --out validation/data/benchmark_articles_200.json
python validation/fetch_corpus.py n2 --annotations validation/data/N2_expert1_annotations.csv \
    --out validation/data/gold_standard_annotation.json
```

On 2026-10-23, the rebuilt corpora were identical to the ones used for the
article: same abstracts and same last-author affiliations for all 300 PMIDs.

## 3. Reproducing the article figures

### PubMed retrieval: 251/251 tests

```bash
pytest -m network validation/test_search_retrieval.py
```

These tests query live PubMed, and PubMed's index keeps changing. A test that
checks the content of the result list can therefore fail even though the code
has not changed. On 2026-10-23, one test failed for this reason: a newly indexed
article in *J Child Health Care*, which is in the nursing journal list. Its
journal-name check was then made more robust.

### N1 benchmark (Table 2): 200 abstracts, heuristic reference (not independent)

```bash
python validation/benchmark_nlp_v2.py --rescore validation/data/benchmark_articles_200.json \
    --output validation/data/n1_results.json
```

`--rescore` re-runs the current extractors on the saved abstracts and scores them
against the heuristic reference. No PubMed call is made. Compare the output with
`N1_benchmark_results.csv`:

| Module | Published | Current code |
| --- | --- | --- |
| Outcome Extractor (primary outcome detection) | P 98.2 %, R 99.1 %, F1 98.7 % | identical |
| Region Detector (122 affiliations) | accuracy 100 % | identical |
| Participant Extractor (n evaluated) | F1 92.4 %, MAE 16.2 (n = 112) | F1 91.3 %, MAE 38.7 (n = 113) |

**Note on the Participant Extractor N1 figures.** The published N1 values were
produced on 2026-02-27 with `search/services/participant_extractor.py` as of
commit `281ece2`. Later rule changes (commit `0fc2f5e`, made for the N2
annotation round, and `d860cf1`) shifted the N1 result. Re-running with
`participant_extractor.py` from `281ece2` gives exactly F1 92.4 %, MAE 16.2,
n = 112.

### N2 dual-expert annotation (Tables 3, 4 and 5): 100 articles, 10 categories

```bash
python validation/score_dual_experts.py \
    --csv1 validation/data/N2_expert1_annotations.csv \
    --csv2 validation/data/N2_expert2_annotations.csv \
    --json validation/data/gold_standard_annotation.json \
    --rerun-nlp --output validation/data/n2_results.json
```

The current code reproduces every value of `N2_scoring_results.csv` exactly:

| Figure | Value |
| --- | --- |
| Inter-rater κ, primary outcome / region | 0.761 / 0.966 |
| Outcome F1 vs consensus / expert 1 / expert 2 | 100 % / 91.3 % / 96.7 % |
| Participant F1 vs consensus | 88.0 % |
| Region accuracy vs consensus | 91.8 % |

Always pass `--rerun-nlp`. Without it, the script uses the `nlp_*` columns of
the expert 1 file, which are the same values as `N2_system_outputs.csv`. Those
columns were recorded when the annotation sheet was prepared, before the
extractor revisions that preceded the published scoring. They give different
scores.

## 4. Unit tests

```bash
pytest             # offline: unit tests + offline validation tests (network tests excluded)
pytest -m network  # live PubMed tests only
```

`test_regression_nlp.py` looks for a saved corpus in `validation/data/` (or in
the folder given by the `MEDLITSEARCH_VALIDATION_DATA` environment variable). If
it finds none, its tests are skipped.

## Scope of the validation

- **Outcome Extractor**: validated only for *binary detection* of an explicit
  primary outcome. The extracted text is not semantically validated. The
  adverse events, efficacy, results and safety fields are not validated.
- **Participant Extractor**: validated for detecting a sample size. The number
  is unreliable when an abstract reports several competing counts (arms,
  sub-populations, registries, large observational cohorts).
- **Region Detector**: the region is that of the **last author's affiliation**,
  not the recruitment location.
- **Multicenter Detector**: developed but **not validated**.
- Extraction rules target English and French abstracts only.
- Time savings were not measured.
