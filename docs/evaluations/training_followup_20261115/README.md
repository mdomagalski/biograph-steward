# Training follow-up: qualification before another fit

This follow-up prepares **one development fit**. It does not change the app's
graph, pruning decisions or selected prediction method. The April–November
reference has already been used; a further result on it cannot be presented as
independent confirmation.

The [cross-fitting source review](oof_qualification.md) supports a bounded
adaptation of the existing native stacker: **LocalPlus + observed fitting-label
frequency + the original 40 GOA context channels**. Fitting rows receive graph
and frequency inputs made without their exact-sequence fold. Validation and
final rows use the complete original fitting source. DeepGO is excluded from
this candidate because its checkpoint training membership is not reconstructed.
This does not establish that the old parent leaked future labels.

The model, loss, optimizer, seed, 20-epoch budget, original fitting targets and
dated context remain fixed. All three base-feature caches must be rebuilt with
honest parent names. Native LocalPlus replay, empty-head handling, complement
priors, actual runtime compatibility and GPU memory must pass before fitting.
The existing selected method and all earlier controls remain in the comparison.
This is a combined input-profile change, not an isolated causal test of
cross-fitting or a full reproduction of ProtBoost.

The [PU-GO review](pu_qualification.md) does **not** admit a PU loss into this
fit. The released objective differs from the paper's equation, the code expects
different embeddings, and its code reuse terms are unresolved. A future nnPU
adaptation also needs defensible class priors and value/gradient parity with its
licensed implementation. Annotation frequency is not a verified biological
class prior.

Execution status is deliberately separate from source qualification. Native
runtime qualification, a completed fit and its full consumed-reference results
must be recorded before reporting a training gain.

The [fixed method plan](../../../tools/contextual_combination/crossfit_protocol.json)
specifies one candidate and preserves all 22 earlier methods in six BP evaluation
cells. The preparation adapter has separate `parents` and `features` stages so
the existing LocalPlus and Torch environments can retain their qualified NumPy
versions. The training wrapper delegates to the unchanged native trainer;
its outer metadata explicitly records consumed validation and reference roles.
