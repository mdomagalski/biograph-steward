# Sequence similarity audit of the contextual comparison

**The final source frame contains related fitting sequences despite exact duplicate removal.** A single fixed MMseqs2 search detected qualifying fitting matches for 540 of 3,300 final proteins at reported identity ≥30%, 278 at ≥50%, and 25 at ≥90%, requiring at least 80% coverage of both sequences. These are descriptive source counts; no prediction labels, outcome scores, models or partitions were changed.

The audit covers all 3,300 final source proteins, rather than a subset selected by available outcome labels. Its fractions must not be applied to the 322 proteins in the primary analysis after known annotations are excluded or interpreted as a new performance result. It was specified and run after the prediction reference had already been consumed.

| Directed comparison | Reported identity≥ | Directed hits | Query proteins with a detected hit | Fraction of the complete query frame |
|---|---:|---:|---:|---:|
| Final→fitting |30%|1,239|540/3,300|16.36%|
| Final→fitting |50%|376|278/3,300|8.42%|
| Final→fitting |90%|29|25/3,300|0.76%|
| Final→validation |30%|283|197/3,300|5.97%|
| Final→validation |50%|105|91/3,300|2.76%|
| Final→validation |90%|10|10/3,300|0.30%|
| Validation→fitting |30%|297|140/797|17.57%|
| Validation→fitting |50%|82|64/797|8.03%|
| Validation→fitting |90%|3|3/797|0.38%|

All zero-hit queries remain in these denominators. A directed hit is an alignment between two source proteins; it is not an independent family, study or biological verification.

## Sources and fixed method

The inputs retain the exact 4,040 fitting, 797 validation and 3,300 final amino-acid sequences used by the forecast pipeline. The historical sources for all 6,437 sequences and every role's full-sequence/first 1,022-residue hashes were reverified. Across each role pair, accession, full-sequence and first 1,022-residue exact-hash intersections were zero. No sequence epoch was substituted.

The frozen [plan](sequence_similarity_source_audit_20261115/plan.json) specifies one search with 4,097 queries against 4,837 targets using MMseqs2 release 18-8cc5c, two CPU threads, sensitivity 7.5, E-value ≤0.001, minimum identity 0.3 and bidirectional coverage 0.8. Counts apply the fixed thresholds to reported `fident`, `qcov` and `tcov`. The pinned [official manual](https://github.com/soedinglab/MMseqs2/wiki/Home/67ba9c6637b4b5121a73e5de034dd0c3414d2b81) defines these fractional fields and the explicit identity calculation under `--alignment-mode 3`. The reproducible [command](sequence_similarity_source_audit_20261115/run_command.sh) uses `--alignment-mode 3`; no parameters were tuned.

All 2,843 returned rows met the reported gates; there were no duplicate directed rows. The maximum reported hits per query was 19, below `--max-seqs 5000`, which also exceeded the 4,837 targets. All 797 validation self-matches were observed as a diagnostic; this was not a completeness requirement. Execution took 58.3 seconds, using CPU only. Six invented aggregation/CLI fixtures and separate source review passed before the real search.

## Interpretation and limits

[GO-LTR](https://pmc.ncbi.nlm.nih.gov/articles/PMC11067221/) motivates examining sequence similarity when interpreting protein-function generalization. Its cluster-separated evaluation used 30% identity and 60% coverage. Our retrospective search requiring 80% coverage on both sides is a different descriptive audit and does not reproduce that partitioning protocol.

This result supports retaining a narrow transfer claim. The existing comparison removes exact duplicates but does not establish generalization to sequence-distant proteins. Detected similarity does not itself show label leakage or equivalent function. Heuristic non-detection does not prove absence of homology. Parent predictor training and protein-language-model exposure remain outside this combiner-frame audit. Searching full sequences also does not establish near-homology separation of the truncated first 1,022-residue model inputs.

The original prediction results and success gates remain unchanged. Public artifacts contain only the [aggregate](sequence_similarity_source_audit_20261115/aggregate.json), [receipt](sequence_similarity_source_audit_20261115/receipt.json), plan and command. Exact role FASTAs, synthetic-header mappings, raw matches and logs are retained privately for replay.
