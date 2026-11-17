# Native paper retrieval: original and transport-corrected development runs

The original native-tool run recovered no listed reference papers. Nine fresh
abstract fetches were unavailable; one paired probe established default Mac
system-proxy refusal. That original result and every old cache entry remain intact.

One unchanged-profile repeat used per-process `NO_PROXY=*` and `no_proxy=*` with
normal TLS and a new cache seeded by fixed execution status, without selecting
sources by relevance. All 12 requested abstracts then resolved with nonempty
text (9 fresh, 3 cache hits). Its 12 valid final lists were all nonempty, compared
with 8 nonempty + 4 empty originally. Twelve API/parser handoffs still failed:
10 no-tool-call and 2 empty-parsed-call results. Discarded model content is not
available to distinguish model and parser causes.

Corrected mean reference-paper Recall@10 was **4.17%**, versus **6.25%** for the
retained JSON agent and **17.26%** for deterministic PubMed search. Native minus
JSON was −2.08 percentage points, paired95% interval[−14.58,+10.42]. Native minus
direct was −13.09 points,[−26.29,−2.78]. Neither predeclared adoption gate passed;
deterministic source search remains the maintained default. These are recovery
measurements, not scientific claim or whole-graph biological accuracy.

All results use the same previously consumed24 public BioASQ11 questions
(12factoid+12list; DOI10.5281/zenodo.7655130;CC-BY-2.5). This targeted post-hoc
transport repair is DEVELOPMENT reuse, not fresh confirmatory evidence. Reference
lists are incomplete positive judgments; unlisted papers are not biological
negatives. Model/public training overlap is unaudited. Retained controls were
not rerun. Source retrieval/cache histories and full conditional intervals remain
in the unchanged aggregate assessments.

Source/runtime: BioMCP0.9.3 PubMed search plus the existing exact-PMID XML parser;
existing NVIDIA Nano8B revision54641c…/vLLM0.8.5 V0; source-qualified first-provider-
parsed-entry policy and named finish only in finish-only states. Budgets stayed
4model calls/2searches/1abstract/10final IDs/1200output tokens per call. No further
prompt/model/strategy sweep, graph change or default promotion followed.

Historical source is retained on LOCAL Git ref
`codex/archive-native-tools-v3-20261114`, commit
`0ecd9ab86ae388e375cabb5849a9c03b4b26a995`.
The failed earlier manual profiles, frozen source capture and original proxy-
confounded run remain preserved. The maintained `tools/source_search` operator
utility is separate; see `docs/SOURCE_PAPER_INSPECTION.md` in the repository for
its native default and verified process-level proxy troubleshooting. No public
remote release or model success is inferred from an archive pointer.

This capsule contains unchanged aggregate assessments, independent guard/numeric
reviews, technical transport proofs and a path-free repair-protocol projection.
No raw questions, queries, PMIDs, reference cases, weights, model bodies or
operator paths are included. The publisher made no source/model calls.
