# Evaluation and live-planner checkpoints

The guided-question checkpoint is committed as `af4dd9b`. The scoped CIViC integration, evaluation runner and initial bounded planner are committed as `b0382f4` (`Add scoped evidence evaluation and bounded question planner`). Do not repeat that commit.

The follow-up increment adds an explicit Codex CLI planner provider, an isolated single-turn execution contract, progress reporting, CLI contract tests and preliminary three-case source-review notes. Suggested title: **`Add isolated Codex planner and pilot review notes`**.

Validation: **181 automated tests**, including local HTTP tests. See [evaluation instructions](EVALUATION.md) for the live-run protocol and limits. The [source-review notes](PILOT_REVIEW.md) are AI-prepared; scientific judgments remain pending until a reviewer adjudicates the worksheets.

Keep `runs/`, `.pharos_cache/`, screenshots and credentials out of Git. Raw live data and evaluation artifacts are local; a fresh clone must create/retrieve source runs before executing the pilot. A live run uses the explicitly configured model/authentication and records its own trace. No push is implied by a local commit.
