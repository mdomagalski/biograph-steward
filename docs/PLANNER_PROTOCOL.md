# Optional bounded question planner

The planner selects **one existing read-only query or abstains**. Application code validates the plan, executes the query over a saved graph and produces its deterministic cited answer. The planner cannot retrieve new evidence, change review states or infer an unsupported clinical conclusion.

## Supported scope

The two query families are protein interaction/shared-pathway inspection within a retrieved cohort, and supported CIViC molecular-profile/therapy evidence inspection. The request must identify a supported source scope and evidence view. Candidate inspection is explicit; accepted-only queries can correctly return no evidence.

The resolver binds exact case-insensitive catalogue names, symbols and IDs, allowing whitespace variation. Complete AND/OR/NOT molecular profiles stay intact; ambiguous and incomplete identities are not silently simplified. It does not perform fuzzy biological identity mapping.

The current Brev overlay selects `BIOGRAPH_PLANNER_PROTOCOL=scoped_targets_v4`. Its conservative application checks distinguish requested entities from some background/excluded mentions, enforce tool-specific fields and bounded clause polarity, and reject unsupported scope. These are limited lexical checks, not comprehensive language understanding or scientific validation. Supported wording can still be declined.

The runtime retains `catalogue_v1`, `entity_tools_v2` and `tool_shapes_v3` compatibility contracts; the default outside the Brev overlay remains `catalogue_v1`. Their comparative research runners have been archived. This consolidation does not silently change existing model defaults or reinterpret old saved plans.

## Configuration and use

Use the model settings in [portability](PORTABILITY.md), or the tested [local Nemotron configuration](LOCAL_MODEL.md). Set the protocol explicitly in the running process:

```sh
export BIOGRAPH_PLANNER_PROTOCOL=scoped_targets_v4
python3 app.py runtime-check
python3 app.py
```

These commands do not configure a model by themselves. Once a provider is available, open a saved graph and use **Plan a research question with one model agent**. Deterministic guided questions require no model configuration.

The CLI also exposes `plan-question`; use `python3 app.py plan-question --help` for its source, question and output arguments. The optional [NeMo wrapper](PORTABILITY.md#optional-nemo-agent-toolkit-workflow) calls the same bounded planner/query path.

## Trace and limitations

There is one model request, at most one validated query, and no repair call or automatic retry. Traces preserve protocol, selected scope, exact-resolution output, request/schema hashes, model metadata, configured budgets and returned usage. Credentials and private reasoning are not saved. A provider that ignores the schema still faces application validation.

Previous development comparisons helped repair entity/tool-scope errors, but did not establish independent biomedical accuracy or graph improvement. The v4 regression matched 26/32 already exposed draft scope plans with zero wrong-scope queries and six unnecessary declines. Original results, failures, references and code are in the [experiment archive](EXPERIMENT_HISTORY.md); those questions cannot become an unseen test again.

For deployment integration, use `deployment-smoke --with-planner` with a new output directory. It runs an explicitly synthetic case, not a scientific evaluation. Further quality claims require a separately justified reference population and frozen comparison.
