# Pharos release availability check — October 27, 2026

**The application does not select Pharos319. Its configured public service still reports `pharos319`.** A fresh, uncached metadata-only request to `https://pharos-api.ncats.io/graphql` returned `{"data":{"dbVersion":"pharos319"}}`. The version query is dynamic in `biograph_steward/client.py`; construction checks it before and after retrieval. No `pharos319` or `pharos400` literal occurs in the runtime package or GraphQL query files.

The [official NCATS distribution](https://opendata.ncats.nih.gov/public/pharos/) now publishes two Pharos400 identity/TDL tables. Its linked [SQL archive](https://opendata.ncats.nih.gov/public/pharos/archive/) lists numbered full dumps only through 319. The [400 release notes](https://opendata.ncats.nih.gov/public/pharos/pharos400_readme.html) describe changed canonical, isoform and alternate-product grouping, UniProt as the public protein identifier, and internal IFX IDs for traceability. The public tables contain identity, TDL and supporting summaries; they do not replace the full PPI/GO/pathway retrieval used by this application.

This establishes an API-versus-distribution difference, not its cause. No complete 400 API endpoint or SQL dump was verified in these checked official materials. It does not establish that none exists elsewhere. The [NCATS server README](https://github.com/ncats/pharos-graphql-server) links a development deployment but does not identify it as 400. A separate follow-up sent one uncached version query to that exact documented URL, `https://ncatsidg-dev.appspot.com/graphql`; it returned HTTP 404 and no version. The original audit receipt remains unchanged. Follow-up receipts are in `runs/pharos_release_check_20261027_dev_followup/`, with report SHA-256 `a7faa86550a3fd10f0bb41b26a8e03d28db8ffa185bda2b7bea851f5727b050c`. Per-provider import dates also cannot be inferred from the service's database label.

## Update path

1. Preserve prior snapshots and comparison results under their actual source release. A release migration is a separate change from evidence qualification.
2. Keep endpoint-reported version and access time visible. Do not relabel 319 responses as 400 or guess a replacement endpoint.
3. Treat a future official 400 identity/TDL download as a separately versioned source. It can support identity reconciliation without pretending to update all graph relationships.
4. Use SSSOM to record each asserted mapping's relation, source and target releases, evidence and ambiguity. Isoforms, alternate products and one-to-many accession replacements must not be silently collapsed into exact protein identity.
5. Migrate full graph retrieval when an official 400 full-data location is verified, required schema and source coverage checked, and a new snapshot frozen. No default endpoint, cache or historical data changed in this audit.

## Receipt and limits

[`pharos_release_check_20261027_summary.json`](pharos_release_check_20261027_summary.json) records the conclusions, source URLs and artifact hashes. `runs/pharos_release_check_20261027/` contains the request contract, raw official metadata pages, raw version response, HTTP receipts and report. There were three bounded metadata GETs and one version POST, zero retries, no redirects and no cache. No CSV/SQL table bodies, targets, interactions, assays, articles, abstracts, or fresh reserved study records were requested. No model or GPU compute was used.
