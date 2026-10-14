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

1. Click a protein in the graph or target table.
2. Open its raw evidence and provenance.
3. Filter to Tbio or Tdark. These are the source's development-level labels, not scores calculated by this application.
4. Open **Needs review** and **Quarantine**. Notice missing source information, a differing disease label, a duplicate record, and a missing protein identifier.
5. Download the run ZIP. The graph, readable tables, raw input snapshot and validation log travel together.

A prebuilt version is in `examples/synthetic_demo/report.html`; open it without starting Python to inspect the synthetic output only.

## Second: replace the synthetic input with live Pharos

Select **Live Pharos API**. Search for `colorectal`. Choose the exact disease returned by Pharos; do not assume colorectal cancer, colorectal carcinoma and a subtype are interchangeable.

Leave the first run at **25 targets** and **5 pathways per target**. Click **Build Pharos inspection graph**.

A successful live run is explicitly labeled `live_pharos`. It saves responses and their retrieval times. If the API fails, the program stops with the error; it never substitutes demonstration data.

**Delivery limitation:** the development environment could not resolve the live Pharos hostname for API requests. The published NCATS schema and resolver were inspected, but a live response has not been verified here. The live client needs this first integration check on your own network. The local application, transformations, simulated API behavior, exports and tests were exercised.

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

**The next shared deliverable is one saved live Pharos run that everyone can open.** Do not add ROBOKOP, CPTAC, a GNN or an LLM until that run is understood. Improvement tasks should come from the actual records and limitations observed in this prototype.
