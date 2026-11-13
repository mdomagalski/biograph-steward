Optional WikiPathways utility development replay
===============================================

This adapter reuses the project's PyKEEN 1.11.1 / torch 2.6.0 native R-GCN
training path and INMC recorded-assay outcome adapter. The INMC panel has already
been inspected in earlier development. This is a retrospective sensitivity
comparison, **not an unopened biological validation set**.

The fixed contrast is normalized source-reported exact protein/pathway-version
claims versus their previously fixed source-eligibility qualification. Both
views use exact source revision URLs. Duplicate source evidence is preserved in
the copied source packages and becomes one triple per claim in the simple
learner. Other source families, supervision, query masks, vocabularies and exact
reviewed product links are identical across arms. No graph verdict is changed.
The fixed qualification concerns **current-release eligibility**. A removed
membership may be supported in its historical pathway revision; this comparison
does not classify every removed source assertion as biologically false.

Four arms are fixed before fitting:

1. All normalized source-reported memberships.
2. The fixed qualified subset, including unresolved currentness records that
   the source-eligibility policy retained.
3. One fixed random subset of the normalized memberships with the same count
   as arm 2. This is a count control, not a matched-degree control.
4. One XSwap permutation of arm 2 preserving every protein and pathway degree.
   The author implementation is pinned to commit
   `ffbb933d1731c2ce4e4e24f00a9a909b53ddf75c` from
   [hetio/xswap](https://github.com/hetio/xswap), BSD-2-Clause. Integer protein and
   pathway ranges are disjoint. Ten attempted swaps per edge and one fixed seed
   are a reproducible sensitivity control; no mixing guarantee, permutation
   p-value or scientific null distribution is claimed.

Each arm receives the same seeds (17, 43, 101), 20 epochs, 99,394 directed HuRI
supervision triples and 500 optimizer updates. Native adjacency, parameter,
positive-batch, negative-proposal/filter and accepted-negative fingerprints
verify pairing. A pre-fit native message probe checks that changed memberships
actually affect representations of nominated query endpoints. Random-weight
message effects establish input visibility, not biological usefulness.

`prepare.py` freezes and copies the source packages, exact source/code hashes,
registry mapping decisions, degree controls and all nominated query identities.
It does not decode assay labels. `run.py --resource` makes a one-epoch check
without constructing prediction queries. `run.py` then runs the fixed full
comparison. `score.py` authenticates complete predictions before opening the
already-consumed outcome cache and calls the existing `inmc_outcomes` scorer.
All nominated outcomes and exclusions remain in the output. AP/AUROC concern
recorded assay detection under the existing complete-scored eligibility rule;
non-detection is not universal biological noninteraction. Direct Wiki coverage
of this panel is sparse, so any full-panel differences may be indirect context
effects and do not establish whole-graph scientific accuracy.

Use an existing runtime satisfying `requirements-inmc-evaluation.txt` and an
isolated installed copy of the pinned XSwap package. Preparation arguments are
explicit paths, for example:

```sh
python tools/wiki_utility/prepare.py --base ORIGINAL_INMC_PACKET \
  --original ORIGINAL_GRAPH_JSON --qualified VERIFIED_RETAINED_PACKAGE \
  --registry VERIFIED_REGISTRY --xswap ISOLATED_XSWAP_SITE_PACKAGES --out NEW_PACKET
python tools/wiki_utility/run.py --packet NEW_PACKET --out NEW_RESOURCE --resource
python tools/wiki_utility/run.py --packet NEW_PACKET --out NEW_PREDICTIONS
python tools/wiki_utility/score.py --packet NEW_PACKET \
  --predictions NEW_PREDICTIONS --out NEW_SCORES
```

No source retrieval, paid compute start, model service, default app change or
automatic graph promotion is performed by these commands.

The historical follow-up uses `historical.py`, the existing
`biograph_steward.wiki_history` native GPML reader, and an explicitly pinned
pre-exposure declaration. Its positive feature view includes literal protein
xrefs and compatible gene-level xrefs as separate evidence bases. Unmatched
claims remain UNKNOWN in the preserved source. A gene-compatible xref does not
establish historical protein/isoform identity. Archive/member bytes and every
original subject/version connection are replayed before fitting. Producer XSD
receipts are byte-bound and reported as attached; the consumer does not claim
to reexecute XML Schema validation.

```sh
python tools/wiki_utility/historical.py --parent ORIGINAL_DEVELOPMENT_PACKET \
  --history VERIFIED_NATIVE_HISTORY --history-content-sha256 TRUSTED_HISTORY_SEAL \
  --declaration FROZEN_SELECTION --declaration-content-sha256 TRUSTED_SELECTION_SEAL \
  --xswap ISOLATED_XSWAP_SITE_PACKAGES --out NEW_HISTORICAL_PACKET
```

The full resource/run/score commands then use that new packet. The copied
`sources/qualified` package preserves the parent's Gold source lineage; the
historical feature treatment is defined by `historical_selection.json` and the
native history package, not the parent's current-release filtering decisions.

The verifier reconstructs deterministic memberships, common context, masks,
queries and vocabulary from preserved source copies. It checks the fixed
stored degree-control row inventory and both degree vectors. Without the native
backend it does not claim to regenerate a past XSwap seed; the actual-run audit
can reexecute the pinned author backend separately. Hashes establish byte
consistency rather than external scientific truth or proof of a past execution.
