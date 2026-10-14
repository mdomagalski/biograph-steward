# Start here: one shared prototype, not separate workstreams

## What we have

A local browser application for this first question:

> Which proteins does Pharos associate with a selected disease, what target-development levels does it report, and which pathways annotate those proteins?

This is the first inspection step for **BioGraph Steward / CRC Target Scout**. It is not yet a target-prediction model or an autonomous AI agent.

## Open it

Unzip the project. In a terminal, change into the `biograph-steward-pharos` folder and run:

```bash
python3 app.py
```

Requires Python 3.10 or newer. There is nothing to install with pip. On Windows, `py app.py` may be the appropriate command instead.

The browser opens at `http://127.0.0.1:8765`. Keep the terminal open. Press Ctrl+C in the terminal to stop the application.

## First: understand the software together

Select **Offline demonstration**, then **Build synthetic demonstration**.

The demo is deliberately synthetic. It contains no downloaded Pharos records and must never be shown as scientific evidence or challenge performance. It lets everyone explore the software before troubleshooting API access.

1. Click **Inspect candidates**. New assertions are unreviewed, so the accepted view starts empty. Click an assertion or a protein.
2. Open its raw evidence and provenance.
3. Filter to Tbio or Tdark. These are the source's development-level labels, not scores calculated by this application.
4. Open **Needs review** and **Quarantine**. Notice missing source information, a differing disease label, a duplicate record, and a missing protein identifier.
5. Open an assertion passport, choose a decision and enter a reviewer and reason. In the synthetic demo this tests the workflow only. Saving creates a new run and updates its URL; reloading that URL preserves the review.
6. Download the run ZIP. It includes assertions, review events, tables, the original snapshot and validation results.

A prebuilt version is in `examples/synthetic_demo/report.html`; open it without starting Python to inspect the synthetic output only.

## Second: replace the synthetic input with live Pharos

Select **Live Pharos API**. Search for `colorectal`. Choose the exact disease returned by Pharos; do not assume colorectal cancer, colorectal carcinoma and a subtype are interchangeable.

Leave the first run at **25 targets** and **5 pathways per target**. Click **Build Pharos inspection graph**.

A successful live run is explicitly labeled `live_pharos`. It saves responses and their retrieval times. If the API fails, the program stops with the error; it never substitutes demonstration data.

**Live verification update, October 14, 2026:** the Pharos connectivity/schema check passed and a paginated retrieval returned all 99 reported colorectal adenocarcinoma proteins. The saved local report is `runs/crc_baseline_audited_20261014/report.html`. Availability can change; the commands below check your current connection.

For diagnosis:

```bash
python3 app.py doctor
python3 app.py search colorectal
```

## What to show at the next meeting

Open the first successful live report and ask together:

- Is this the intended disease, and is our target cap obvious?
- Which source records explain one selected protein-disease connection?
- Which records need scientific review before becoming benchmark labels?

The app now includes a collapsed **Evaluation — benchmark readiness** section and exports a pair-level review worksheet. The [live coverage audit](docs/PHAROS_COVERAGE_AUDIT.md) found substantial Pharos data missing from our extract and overlap with proposed external sources. The next deliverable is expanded Pharos retrieval with evidence normalization, followed by a frozen cohort, reviewed evidence and qualified external additions. The benchmark evaluates this evidence workbench. See [the build plan](docs/BUILD_PLAN.md) for the revised sequence and source decisions.
