# Planning protocols for exact entity binding and tool use

`BIOGRAPH_PLANNER_PROTOCOL` selects `catalogue_v1`, `entity_tools_v2`, `tool_shapes_v3` or `scoped_targets_v4`. The current Brev overlay explicitly selects v4. The compatibility default outside that overlay remains v1. Every protocol retains one model request and at most one validated read-only graph query.

## What changed

The first Nemotron run produced valid plan JSON but declined all 24 development questions. Its returned explanations confused the two tools, demanded IDs instead of resolving supplied names, and treated candidate inspection as unsupported. Those observations motivate this revision; they do not establish a hardware fault or prove how the model internally reached its decisions.

The model previously received the application policy, plan schema and flat entity catalogue. It did not receive standalone skills or fetch instructions dynamically. Version 2 supplies a small, versioned planning playbook through `tool_contracts()` in `planning.py`: each tool has its own purpose, required and irrelevant fields, source disease, supported evidence views and unsupported conditions. No third-party skill loader, extra agent loop or autonomous source retrieval is introduced.

Before the model call, `entity_resolution.py` binds case-insensitive exact names, symbols and identifiers from the frozen catalogue. It permits whitespace variation but does not use fuzzy matching, external aliases, ontology equivalence or reference answers. Complete molecular profiles take precedence over contained shorter profiles; AND/OR/NOT remain part of the identity. Duplicate labels stay ambiguous. Explicit incomplete compound expressions are flagged rather than converted into simpler profiles. This is a limited catalogue resolver, not a general biological expression parser.

The input contains the question, matched identities and per-tool instructions. The planner still selects the tool, evidence view, relation and whether to abstain. It must distinguish supported inspection from unsupported clinical advice, causality and additional filters. Both `candidates` and `accepted` are valid views; a valid accepted-only query may return no evidence.

Version 2 narrows JSON identifier/therapy enums to exact mentions. After generation, the application rechecks source scope and mention bindings; it rejects unmentioned IDs, silent therapy broadening, ambiguous entities and an unrequested all-profiles selection. It does not repair a wrong plan or retry a model. Exact binding alone does not establish correct intent, source support or biomedical truth.

## Protocol v3: tool-specific shapes and capability checks

The v2 [full comparison](evaluations/ENTITY_TOOLS_V2_20261019.md) exposed wrong null/irrelevant fields and scope regressions despite its successful synthetic preflight. V3 preserves that failed run and adds disjoint JSON object shapes for abstention, protein queries and CIViC queries. Irrelevant fields are fixed to null/empty, and a brief public explanation precedes the plan choice. The installed XGrammar backend compiled all 24 development schemas before inference; other serving implementations require their own schema-capability check.

The application also computes conservative lexical request-scope signals: the requested family, candidate versus accepted view, explicit relations, and clearly unsupported causal/clinical/write/prediction/filter conditions. Whitespace is normalized for these checks. Complete profile identities still come from the exact resolver. The selected view/relations are constrained, and explicitly unsupported requests receive only an abstention shape. The application rechecks those constraints after generation, including for a provider that ignores its output schema.

For this development set, application checks force an abstention shape on eight requests; on the other 16, the model can choose a supported query or abstain. This is a **hybrid workflow**, not an independent test of a model's unconstrained tool selection. Neither rules nor prompts receive case IDs or reference plans. The capability checks are deliberately conservative lexical rules; unfamiliar wording, synonyms and complex negation can still produce false declines or missed conditions. They are not a complete natural-language understanding or scientific-validity system.

## Audit and experiment boundaries

Traces record protocol, policy, exact-resolution output, instructions/tool-contract hashes, schema and request hashes, model metadata, latency and returned token usage. Source statements, reviewer labels and evaluation reference plans remain excluded from the model input. The query engines and scientific-review state are unchanged.

The new experiment keeps the model revision, image, reasoning-off profile, inference budgets, source bytes, review events, 24 development questions, draft references and display budgets fixed. It freezes a new engine fingerprint and retains the initial all-abstention result. All 24 legacy request payload hashes were checked offline against that first experiment and matched, without making model requests.

The changed component is a **hybrid planning protocol**: deterministic lexical binding, focused catalogue, tool instructions, constrained output choices and post-generation checks. V3 additionally changes the output shapes and request-scope checks. Any improvement belongs to that package; it is not evidence that the model learned new knowledge, that a graph was biologically improved or that these development cases form an unseen benchmark. New held-out questions and source review are still needed.

The completed [v3 comparison](evaluations/TOOL_SHAPES_V3_20261019.md) records the successful development result alongside both earlier failures, with a machine-readable per-case summary.

The [prospective planning packet](PROSPECTIVE_PLANNING.md) retains that exact planner implementation while preparing new scope cases, negative tests and review criteria locally. Its offline constraint audit can expose a reference/schema conflict without making a model call. Do not repair the v3 policy using those cases and still call their later evaluation unseen.

## Protocol v4: requested targets and bounded clause polarity

The [first prospective v3 run](evaluations/PLANNING_CHALLENGE_LIVE_20261020.md) matched 22/32 draft scope plans and executed seven queries with the wrong scope. V4 addresses observed application constraints as well as model instructions. `target_scope.py` retains raw catalogue mentions in the audit, then distinguishes requested entities from explicit background or excluded mentions. It handles bounded negation for relations, evidence views and all-profile requests; rejects contradictory scopes and unsupported exclusion filters; and checks exact source disease identities. Unknown compound-profile extensions are detected case-insensitively before a contained known profile can become a query target. Whole known AND/OR/NOT profiles remain intact.

Only simple standalone negative disclaimers such as “Do not recommend a drug” are removed from capability detection. Positive unsupported instructions and coordinated or ambiguous negative clauses remain visible and can require abstention. These are conservative lexical rules, not a general language parser or a clinical safety classifier. Unfamiliar phrasing can still be declined or misinterpreted. Model instructions continue to permit supported queries with no evidence, and require a short explanation consistent with the returned plan. A provider that ignores the schema still faces the same post-generation scope checks.

V1–v3 payload contracts are retained. The offline check compares all 168 contracts across the original 24 and subsequent 32 cases. On the 32 reused cases, the v4 application forces nine abstentions and leaves 23 query-or-abstain choices to the model. These diagnostics describe constraints, not model accuracy.

The [completed v4 comparison](evaluations/SCOPED_TARGETS_V4_20261020.md) is explicitly a **paired regression after tuning**, using the exact 32 questions, draft references, submitted AI engineering review, source bytes, graph-review events and display budgets from the v3 control. It matched 26/32 scope plans with zero wrong-scope queries, while unnecessarily declining six supported requests. They are no longer unseen cases. Preparation verifies the historical control result and source hashes, records its identity, and freezes a new engine fingerprint. Running it requires the exact same review worksheet; a differently edited or approved worksheet is rejected before constructing a live planner.

```sh
python app.py planning-regression-prepare \
  --control-result runs/brev_planning_challenge_20261020/live/planning_challenge_live_20261020 \
  --source-suite runs/planning_challenge_20261020/suite \
  --scope-reviews runs/planning_challenge_review_20261020/scope_reviews_ai_engineering.tsv \
  --out runs/scoped_targets_v4_20261020/packet
python app.py planning-compare \
  --packet runs/scoped_targets_v4_20261020/packet \
  --scope-reviews runs/planning_challenge_review_20261020/scope_reviews_ai_engineering.tsv \
  --out runs/scoped_targets_v4_20261020/deterministic
```

Preparation and the default comparison above make no model requests. For live inference, configure `scoped_targets_v4` and add `--planner live` with a new output directory. Retain the first result without retries or repair. The submitted review is AI-assisted engineering scope review, not human or independent biomedical validation. A subsequent generalization claim requires a genuinely new, separately reviewed packet.
