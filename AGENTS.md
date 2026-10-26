# Project working instructions

## Check existing solutions before custom work

Before proposing or implementing a custom fix, verify whether the problem is
already understood or handled by this project's dependencies, upstream issues,
version-specific official documentation, published methods, or reusable tools.

Check that existing capabilities are being used correctly, including the actual
model/runtime version and the full scope of any schema or validation constraint.
Prefer reproducing or adapting an established implementation when it fits.
Explain the remaining verified gap before creating a new protocol, abstraction,
prompting strategy, or workaround. Distinguish a known limitation from an
untested hypothesis or an error in our own integration.

For biomedical extraction, use primary papers and their official code/data when
available. Inspect task assumptions, released artifacts, dependencies, licenses
and training/evaluation overlap before treating a method as a reusable baseline.
Preserve existing failed experiments and hold-out boundaries when comparing a
replacement approach. A schema-valid output does not establish factual accuracy.

When an investigation reveals a new scientific or data-integration issue,
check the relevant literature and author-provided artifacts before choosing a
remedy. Record what is documented, what our implementation demonstrates, and
what remains unresolved; do not infer missing assay or identifier semantics.

This is the user's standing preference for work in this repository. Routine
source checks and investigation do not require another confirmation.

## Brev compute

Before work requires the Brev-hosted model or GPU, tell the user what will run
so they can start the instance. Tell them when that compute is no longer needed.
Local source review, identifier audits and ordinary retrieval do not require
the Brev instance to stay on. Do not start paid compute automatically.
