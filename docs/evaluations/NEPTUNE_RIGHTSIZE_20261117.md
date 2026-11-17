# Neptune right-sizing — 17 November 2026

The approved resize is complete: **two `db.t4g.medium` instances are available**, retaining a writer and failover reader. A fresh manual snapshot is available. The smaller reader passed full database parity, was deliberately promoted, and passed again as writer. The remaining reader was then resized and passed the same final read-only check.

The final control-plane read confirmed CloudFormation **`UPDATE_COMPLETE`** and both T4g instances available without pending modifications. Engine **1.4.8.0**, IAM authentication, encryption, deletion protection, endpoints and seven-day automated backup retention were preserved. Both changesets modified only one instance class without replacement; no instance was deleted.

## What was checked

The existing `Mirror.verify` implementation compared the complete retained mirror against its saved graph, including IDs, properties, evidence, qualifiers and source context. It then performed the same TP53 and KRAS reads through that verified client, with no file fallback. The two scoped reads each returned up to 100 assertions and explicitly reported truncation.

| Actual phase | Class and role | Full parity | TP53 / KRAS reads | Result |
| --- | --- | ---: | ---: | --- |
| Original baseline | R6g large reader | 252.55 s | 10.38 / 11.53 s | Passed |
| Smaller-instance canary | T4g medium reader | 263.96 s | 10.91 / 12.18 s | Passed |
| After deliberate failover | T4g medium writer | 246.28 s | 11.03 / 10.50 s | Passed |
| Final matching reader | T4g medium reader | 278.51 s | 11.25 / 10.90 s | Passed |

All four phases matched **58,154 database vertices and 16,687 relationships** for the **99-target retained workspace**. The graph digest remained `e0e664a9a386fd321c2c65ed9fbb6aa61c165536e106b7c61fc75e37c0de69ff`; both scoped payload digests also matched the original baseline. All 17 original source-profile inventories and the existing app, graph, reviews, registration, environment and function index were byte-identical before and after each canary. Every owned canary worker was removed. There were no model calls, source retrievals, or graph writes.

These are single bounded parity/read observations, not a comparative throughput benchmark or an SLA. They verify this retained mirror, not all Pharos or the newer native-source workspace.

## Cost and capacity boundaries

The recorded Ohio Standard on-demand rates are **$0.3287 per R6g large instance-hour** and **$0.0930 per T4g medium instance-hour**. At the approved two-instance target, base database compute falls from **$15.7776/day to $4.464/day**, approximately **71.7% lower**. This excludes storage, I/O, backup, other AWS services, tax, credits and possible burst CPU charges. The rates were obtained from the AWS Pricing API, effective 1 August 2026. [AWS Neptune pricing](https://aws.amazon.com/neptune/pricing/)

AWS describes T4g as a development/testing class. During the heavy promoted-writer check, eight one-minute periods showed zero queued requests, swap and server errors, with approximately 100% buffer-cache hits. Minimum freeable memory was approximately **393 MiB**, so memory headroom is limited. The final reader check likewise recorded no queue, swap, server error or engine restart in the observed window; both instances remained available afterward. CPU-credit balance was zero and surplus credits were observed. The available credit periods showed zero surplus credits charged; this does **not** establish a surcharge-free day or sustained production capacity. Missing metric points were not imputed to zero. [Instance types](https://docs.aws.amazon.com/neptune/latest/userguide/instance-types.html), [CloudWatch metrics](https://docs.aws.amazon.com/neptune/latest/userguide/cw-metrics.html)

The staged change follows AWS's instance modification and reader-assisted resize/failover guidance. The prechange snapshot and the source-preserving receipts provide recovery evidence; the snapshot was not restored as part of this task. [Modifying an instance](https://docs.aws.amazon.com/neptune/latest/userguide/manage-console-instances-modify.html), [Neptune operational guidance](https://docs.aws.amazon.com/neptune/latest/userguide/best-practices-general-basic.html)

The [aggregate receipt](neptune_rightsize_20261117/receipt.json) records all four passed phases, final state and evidence hashes. Private control-plane, SSM and source-preservation receipts remain under `runs/neptune_rightsize_20261117/`. This infrastructure change preserves graph content; it does not establish biological accuracy.
