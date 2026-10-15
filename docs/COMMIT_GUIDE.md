# Scoped retrieval checkpoint

The earlier assertion-review and coverage-documentation commits are already in Git. The next commit should contain the scoped retrieval implementation, context browser, validation tests and updated documentation.

**Suggested title:** `Add scoped Pharos retrieval with auditable coverage`

```bash
git add biograph_steward/client.py biograph_steward/retrieval.py \
  biograph_steward/context.py biograph_steward/graph.py \
  biograph_steward/__main__.py biograph_steward/webapp.py biograph_steward/ui.html \
  tests/test_retrieval.py README.md START_HERE.md \
  docs/SCOPED_RETRIEVAL.md docs/DATA_CONTRACT.md docs/PROJECT_ALIGNMENT.md \
  docs/BUILD_PLAN.md docs/COMMIT_GUIDE.md
git diff --cached --stat
git commit -m "Add scoped Pharos retrieval with auditable coverage"
```

Run `python3 -m unittest discover -s tests -v` before committing. See [live coverage and limitations](SCOPED_RETRIEVAL.md). New context records are inspectable and exported; source-specific assertion normalization is still pending. This commit does not introduce external enrichment or a prediction result.

Keep `runs/`, `.pharos_cache/` and screenshots out of Git. No commit or push was performed by the assistant for this checkpoint.
