# Reactome context annex: B3GALNT2

This is a small real-data option alongside the software/synthetic demonstration.
It contains seven exact native Reactome JSON responses and the successful plain-
text release response, all copied from an existing capture. No new source call,
model inference, biological comparison or graph/review change occurred.

## Inspect offline

Open `index.html` in a browser. The static viewer makes no background network
requests; only clicking an external publisher/citation link needs the internet.
If your browser prefers HTTP, use ordinary Python in this directory:

```sh
python3 -m http.server 8768 --bind 127.0.0.1
```

Open `http://127.0.0.1:8768/`. No packages, account, GPU, model or cloud are needed.
Ctrl+C stops the optional local server.

## Scope and exact source identity

The captured service reports Reactome release **98**. Native fields link
UniProt `Q8NCR0` to physical entity `R-HSA-8878916.1`, CatalystActivity
`8931635` and reaction `R-HSA-8931648.3`. The participant and ancestor lists
are displayed directly from the preserved objects, not a custom BioPAX
projection or a newly inferred reaction. The manifest records each original
request URL, capture time, byte count and SHA256.

Original capture record: `biograph-steward.current-native-Reactome-source-role-trace.v1`,
created November 13, 2026. Its content seal is
`98e1132369857c7b96d7daca95ebffc1562e1f0dc4fc45005fa3bb2d628f7b2a`.
The complete original private trace and its cached documentation are not copied.
The manifest preserves the actual original format string and data-file pins.

Human species, inference status and compartments are curator/model fields. They
do not by themselves prove the experimental host, exact assay construct, native
topology or every mechanistic detail. Cited-publication metadata remain data;
no full article, figure or expert adjudication is supplied in this annex.

This is current Reactome source context, not proof of the historical Reactome
revision imported into Pharos319. It is not the full 99-target Pharos graph, its
original baseline/decision ledger, an offline replay of that workspace, a new
biological gold set, or evidence of scientific accuracy/prediction improvement.
The complete mixed-source package has separate source-sharing boundaries.

## License and attribution

**Data:** Reactome states that its data and derived data files use CC0 1.0.
See https://reactome.org/license and
https://creativecommons.org/publicdomain/zero/1.0/. Credit Reactome, release 98,
and retain the native provenance/cross-references. The successful data responses
are the only publisher files included.

**Viewer and authored documentation:** MIT; the full code notice is in
`LICENSE_CODE.txt`. MIT does not replace the Reactome data grant or license
external articles and other upstream content. See `DATA_LICENSE.md`.

## Verify the received files

`manifest.json` lists the exact data files and source provenance.
`CHECKSUMS.sha256` covers every payload file, including the manifest, but not
itself or the ZIP. Run the following where available:

```sh
shasum -a 256 -c CHECKSUMS.sha256
```

`reactome_context_20261113.zip` contains this directory's allowlisted payload
under a `reactome_context_20261113/` prefix; it does not contain itself. Its
separate release-index checksum identifies the archive bytes. The original
Pharos/source packet, cached HTML, raw request headers/cookies, articles,
images, environments and credentials are excluded.
