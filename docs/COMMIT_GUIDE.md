# Evaluation and live-planner checkpoints

The guided-question checkpoint is committed as `af4dd9b`. The scoped CIViC integration, evaluation runner and initial bounded planner are committed as `b0382f4` (`Add scoped evidence evaluation and bounded question planner`). Do not repeat that commit.

The live-planner follow-up is committed as `c2133b5` (`Add isolated Codex planner and pilot review notes`). It adds an explicit Codex CLI provider, an isolated single-turn contract and preliminary source-review notes.

The next increment adds [study and treatment context](STUDY_CONTEXT.md) beside CIViC claims and in exports. Suggested title: **`Show source study and treatment context beside CIViC claims`**. Validation: **187 tests** and a saved-plan replay preserving all 72 prior workflow statuses, returned evidence, claim text and graph/review bases. No new live model result or human scientific approval is claimed.

See [evaluation instructions](EVALUATION.md) for the live-run protocol and limits. The [source-review notes](PILOT_REVIEW.md) are AI-prepared; scientific judgments remain pending until a reviewer adjudicates the worksheets.

Keep `runs/`, `.pharos_cache/`, screenshots and credentials out of Git. Raw live data and evaluation artifacts are local; a fresh clone must create/retrieve source runs before executing the pilot. A live run uses the explicitly configured model/authentication and records its own trace. No push is implied by a local commit.
