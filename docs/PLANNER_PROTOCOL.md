# Entity binding and tool selection: planning protocol v2

`BIOGRAPH_PLANNER_PROTOCOL=entity_tools_v2` enables a bounded identity resolver and separate application-controlled tool contracts. `catalogue_v1` remains the default outside the explicit Brev overlay so the original experiment can be reproduced. Both protocols retain one model request and at most one validated read-only graph query.

## What changed

The first Nemotron run produced valid plan JSON but declined all 24 development questions. Its returned explanations confused the two tools, demanded IDs instead of resolving supplied names, and treated candidate inspection as unsupported. Those observations motivate this revision; they do not establish a hardware fault or prove how the model internally reached its decisions.

The model previously received the application policy, plan schema and flat entity catalogue. It did not receive standalone skills or fetch instructions dynamically. Version 2 supplies a small, versioned planning playbook through `tool_contracts()` in `planning.py`: each tool has its own purpose, required and irrelevant fields, source disease, supported evidence views and unsupported conditions. No third-party skill loader, extra agent loop or autonomous source retrieval is introduced.

Before the model call, `entity_resolution.py` binds case-insensitive exact names, symbols and identifiers from the frozen catalogue. It permits whitespace variation but does not use fuzzy matching, external aliases, ontology equivalence or reference answers. Complete molecular profiles take precedence over contained shorter profiles; AND/OR/NOT remain part of the identity. Duplicate labels stay ambiguous. Explicit incomplete compound expressions are flagged rather than converted into simpler profiles. This is a limited catalogue resolver, not a general biological expression parser.

The input contains the question, matched identities and per-tool instructions. The planner still selects the tool, evidence view, relation and whether to abstain. It must distinguish supported inspection from unsupported clinical advice, causality and additional filters. Both `candidates` and `accepted` are valid views; a valid accepted-only query may return no evidence.

Version 2 narrows JSON identifier/therapy enums to exact mentions. After generation, the application rechecks source scope and mention bindings; it rejects unmentioned IDs, silent therapy broadening, ambiguous entities and an unrequested all-profiles selection. It does not repair a wrong plan or retry a model. Exact binding alone does not establish correct intent, source support or biomedical truth.

## Audit and reproduction

Traces record protocol, policy, exact-resolution output, instructions/tool-contract hashes, schema and request hashes, model metadata, latency and returned token usage. Source statements, reviewer labels and evaluation reference plans remain excluded from the model input. The query engines and scientific-review state are unchanged.

The new experiment keeps the model revision, image, reasoning-off profile, inference budgets, source bytes, review events, 24 development questions, draft references and display budgets fixed. It freezes a new engine fingerprint and retains the initial all-abstention result. All 24 legacy request payload hashes were checked offline against that first experiment and matched, without making model requests.

The changed component is a **hybrid planning protocol**: deterministic lexical binding, focused catalogue, tool instructions, constrained output choices and post-generation binding checks. Any improvement belongs to that package; it is not evidence that the model learned new knowledge, that a graph was biologically improved or that these development cases form an unseen benchmark. New held-out questions and source review are still needed.
