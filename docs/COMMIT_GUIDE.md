# Evaluation and bounded-planner checkpoint

The guided-question checkpoint is committed as `af4dd9b`. The working tree contains the subsequent scoped CIViC integration and the evaluation/planning increment. No commit or push was performed by the assistant. If CIViC has not been committed separately, the following stages both increments together.

**Suggested title:** `Add scoped evidence evaluation and bounded question planner`

```bash
git add biograph_steward/civic.py biograph_steward/civic_questions.py biograph_steward/civic.js \
  biograph_steward/evaluation.py biograph_steward/evaluation_cases.json \
  biograph_steward/planning.py biograph_steward/planner.js \
  biograph_steward/assertions.py biograph_steward/benchmark.py biograph_steward/graph.py \
  biograph_steward/reviews.py biograph_steward/questions.py biograph_steward/guided.js \
  biograph_steward/webapp.py biograph_steward/ui.html \
  biograph_steward/__main__.py biograph_steward/__init__.py \
  tests/test_civic.py tests/test_civic_http.py tests/test_evaluation.py \
  tests/test_planning.py tests/test_planner_http.py \
  README.md START_HERE.md docs/CIVIC_EVIDENCE.md docs/EVALUATION.md \
  docs/GUIDED_QUESTIONS.md docs/DATA_CONTRACT.md docs/BUILD_PLAN.md \
  docs/PROJECT_ALIGNMENT.md docs/COMMIT_GUIDE.md
git diff --cached --stat
git commit -m "Add scoped evidence evaluation and bounded question planner"
```

Validation: **176 tests**, plus browser checks of the pilot report and model-configuration state. The 24-case pilot uses frozen live source snapshots, with draft development plans and pending scientific judgments. No model service is configured, so the live planner arm is explicitly not run. Mock/replay tests are not live model or scientific performance results. See [evaluation instructions](EVALUATION.md).

Keep `runs/`, `.pharos_cache/`, screenshots and credentials out of Git. Raw live data and evaluation artifacts are local; a fresh clone must create/retrieve source runs before executing the pilot.
