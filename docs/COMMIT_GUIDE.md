# Guided question checkpoint

The normalization checkpoint is already committed. The next commit contains guided evidence-path queries, the primary question screen, traceable summaries, saved question exports, CLI/API support and tests.

**Suggested title:** `Add guided evidence questions and traceable summaries`

```bash
git add biograph_steward/questions.py biograph_steward/guided.js \
  biograph_steward/graph.py biograph_steward/webapp.py biograph_steward/ui.html \
  biograph_steward/__main__.py biograph_steward/__init__.py \
  tests/test_questions.py tests/test_question_http.py README.md START_HERE.md \
  docs/GUIDED_QUESTIONS.md docs/DATA_CONTRACT.md docs/BUILD_PLAN.md \
  docs/PROJECT_ALIGNMENT.md docs/COMMIT_GUIDE.md
git diff --cached --stat
git commit -m "Add guided evidence questions and traceable summaries"
```

Run `python3 -m unittest discover -s tests -v` before committing. See [scope and validation](GUIDED_QUESTIONS.md). Candidate exploration remains separate from accepted paths; summaries describe database records without causal, physical-binding or treatment-response inferences.

Keep `runs/`, `.pharos_cache/` and screenshots out of Git. No commit or push was performed by the assistant for this checkpoint.
