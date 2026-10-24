# BMC Reproducibility Package - Calculation Method

This folder contains the minimum files needed to reproduce benchmark calculations.

## Calculation Pipeline

### N1 benchmark metrics
Source: benchmarks/benchmark_results_v2_200.json

For each module:
- participant_extractor
- outcome_extractor
- region_detector

The package exports all scalar metrics (e.g., precision, recall, f1, mae, accuracy, n, tp, fp, fn) to N1_benchmark_results.csv with run metadata (date, article_count).

### N2 scoring metrics (two experts)
Sources:
- Expert 1 annotations: benchmarks/gold_standard_annotation.csv
- Expert 2 annotations: benchmarks/gold_standard_annotation_2.csv
- Scoring summary: benchmarks/results_dual_experts.json

N2_scoring_results.csv is built by flattening four comparison blocks from results_dual_experts.json:
- inter_rater_agreement
- nlp_vs_expert1
- nlp_vs_expert2
- nlp_vs_consensus

For each block and each task (pe, oe, rd), all scalar metrics are exported.

### Metric definitions used
- Precision = TP / (TP + FP)
- Recall = TP / (TP + FN)
- F1 = 2 * (Precision * Recall) / (Precision + Recall)
- Accuracy (RD) = correct region predictions / evaluated cases
- MAE (PE) = mean absolute error between predicted and annotated sample size
- Kappa = Cohen's kappa for inter-rater agreement (as provided in scoring source)

### Consensus principle
When expert-level consensus is available in scoring outputs, consensus scores compare NLP outputs only on records where consensus is defined.

## Generated tables
published_tables_source.xlsx contains:
- N1_summary
- N2_inter_rater
- N2_vs_expert1
- N2_vs_expert2
- N2_vs_consensus
