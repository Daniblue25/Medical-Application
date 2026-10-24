# Data Dictionary

This dictionary describes the files included in this reproducibility package.

## N1_benchmark_results.csv
- source_file: benchmarks/benchmark_results_v2_200.json
- level: N1 benchmark summary
- columns:
  - section
  - metric
  - value
  - run_date
  - article_count

## N2_expert1_annotations.csv
- source_file: benchmarks/gold_standard_annotation.csv
- level: N2 human annotations (Expert 1)

## N2_expert2_annotations.csv
- source_file: benchmarks/gold_standard_annotation_2.csv (Excel content)
- level: N2 human annotations (Expert 2)
- note: converted to semicolon CSV for package consistency

## N2_system_outputs.csv
- source_file: benchmarks/gold_standard_annotation.csv
- level: N2 NLP outputs aligned by record
- columns:
  - id, pmid, specialty
  - nlp_sample_size
  - nlp_primary_outcome
  - nlp_region

## N2_scoring_results.csv
- source_file: benchmarks/results_dual_experts.json
- level: N2 scoring summary (dual-expert)
- columns:
  - comparison (inter_rater_agreement, nlp_vs_expert1, nlp_vs_expert2, nlp_vs_consensus)
  - scope (pe, oe, rd)
  - metric
  - value

## published_tables_source.xlsx
- generated from N1 benchmark summary and dual-expert N2 scoring summary
- sheets:
  - N1_summary
  - N2_inter_rater
  - N2_vs_expert1
  - N2_vs_expert2
  - N2_vs_consensus

## metadata.json
- package metadata for traceability.

## LICENSE_DATA.txt
- data usage and citation notice.
