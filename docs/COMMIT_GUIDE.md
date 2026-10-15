# Context normalization checkpoint

The scoped retrieval checkpoint is already committed. The next commit contains source-aware context normalization, the extended assertion contract, UI filters/passports, review-save fix, tests and documentation.

**Suggested title:** `Normalize Pharos context into qualified assertions`

```bash
git add biograph_steward/normalization.py biograph_steward/context.py \
  biograph_steward/assertions.py biograph_steward/graph.py biograph_steward/client.py \
  biograph_steward/ui.html biograph_steward/__init__.py tests/test_normalization.py \
  README.md START_HERE.md docs/CONTEXT_NORMALIZATION.md docs/DATA_CONTRACT.md \
  docs/SCOPED_RETRIEVAL.md docs/BUILD_PLAN.md docs/PROJECT_ALIGNMENT.md docs/COMMIT_GUIDE.md
git diff --cached --stat
git commit -m "Normalize Pharos context into qualified assertions"
```

Run `python3 -m unittest discover -s tests -v` before committing. See [semantics and validation](CONTEXT_NORMALIZATION.md). New claims remain candidates until human review. Local annotation predicates preserve the limits of the retrieved fields; publication discovery does not become supporting evidence automatically.

Keep `runs/`, `.pharos_cache/` and screenshots out of Git. No commit or push was performed by the assistant for this checkpoint.
