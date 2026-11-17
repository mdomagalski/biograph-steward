# Optional native ProtNote research comparison

These adapters are separate from the application and its dependencies. They
reuse the unchanged MIT-licensed [official ProtNote implementation](https://github.com/microsoft/protnote/tree/b29e17fa308d8c0fc1d9692f705b37dff3a8cf5e)
and one released seed-42 checkpoint. Model weights, tokenizers, source data,
environments and private per-protein outputs are not bundled here.

`native_inference_adapter.py` accepts a whole canonical-amino-acid sequence and
an independently supplied, dated GO-description axis. It calls native model
classes without reference labels, a loss, training or downloads. The adapter
is not restricted to a particular gene or disease; the comparison driver
deliberately fixes the previously released 547-target NK/LK frame.

The source-qualified execution order is:

1. Verify official source, checkpoint and local tokenizer/config hashes in a
   separate compatible runtime. Strictly load every native model-state key.
2. Run `pilot_driver.py --phase qualify` with its qualification-only config.
   This records the complete original target inventory and all eligible dated
   GO terms before model forward; it accepts no benchmark reference or TOI.
3. Bind that qualification in the inference config. Run `--phase parity` on
   synthetic data, then `--phase cache` with the passed parity receipt.
   Native dataset/collator and adapter outputs must match bitwise under the
   same precision and chunk plan. Header changes and cache-axis corruption
   are tested separately.
4. Freeze the scientific comparison protocol after the cache is sealed and
   before any target predictions. Run `--phase pilot` with its scalar protocol
   hashes, parity and body-pinned cache receipts. Keep all original identities;
   missing, ambiguous, noncanonical or unscorable sequences remain explicit
   abstentions. No residue substitution or silent denominator change occurs.
5. Run `evaluate_driver.py` in the separate pinned CAFA evaluation runtime.
   It admits only the complete source-bound forecast, independently checks
   every finite unit-interval score and target/GO row, then invokes the existing
   native point/count and paired-bootstrap tools without new metric formulas.

Every phase requires explicit config FILE hashes and a new output directory.
Use `--help` for the receipt arguments. Inference configs contain no reference,
annotation or benchmark-TOI paths; evaluation is a separate process. Frozen
case-level artifacts stay on the research instance. The aggregate-only
publisher lives at `tools/deepgo_reference/publish_protnote.py`.

The official source has conflicting conda/setup dependency declarations; use
the [qualified runtime and integration record](../../docs/evaluations/PROTNOTE_QUALIFICATION_20261114.md).
Keep the existing optional GPL CAFA runners isolated from the MIT app. Do not
install the research stack into the hosted workbench.

This is retrospective development on already exposed reference outcomes.
Training/homology overlap is unresolved, and E5 postdates the historical
baseline. Reference-supported predictions are not validated new functions,
and no model, graph fact or pruning rule is automatically adopted.
