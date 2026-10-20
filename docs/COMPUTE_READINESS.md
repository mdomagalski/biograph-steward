# Compute readiness and the AWS boundary

The Brev setup is complete for the current single-workspace development workflow. That is narrower than production readiness or completion of the challenge evaluation.

| Capability | Status and limit |
|---|---|
| GPU and serving | L40S, existing driver and pinned vLLM/Nemotron container verified with live inference. |
| App access | Token sign-in, protected APIs, approved browser origins and loopback SSH forwarding tested through HTTP. Automated in-app visual inspection remains unverified. |
| Persistence | Named volumes, saved-source/answer hashes and real app restart/reopen checks passed. VM deletion still requires an external backup policy. |
| Real public data | Frozen Pharos/CIViC snapshots copied, validated and opened in Brev; this does not establish a new live API retrieval on Brev. |
| Planning evaluation | Development runs and a [first prospective comparison](evaluations/PLANNING_CHALLENGE_LIVE_20261020.md) recorded. V3 matched 24/24 reused development plans but 22/32 new AI-reviewed scope plans, including seven incorrectly scoped queries. Independent/biomedical performance remains unknown. |
| NeMo/NIM | Optional NeMo wrapper tested with the real Toolkit CLI against a local mock. The Brev serving stack is vLLM, not NIM, and no broader challenge-agent discovery has been deployed. |
| Scientific accuracy | Source review, held-out biological evaluation and the challenge's controlled baseline/enrichment prediction experiment remain separate work. |
| Production operations | Individual user authorization, managed monitoring, external backups and restore policy remain unimplemented. |
| AWS | No account integration, AWS credentials or AWS resources have been used by this implementation. |

## When an AWS account becomes necessary

The current local-model comparison does not require AWS. The next practical AWS increment can be private S3 export/import of frozen run artifacts: save manifests, snapshots and evaluation results, verify their hashes, and prove a restore independently of the Brev VM. Obtain access to the approved organization or challenge AWS account before implementing a live version of that step. Confirm the allowed region, artifact prefix and budget with the account owner.

This is an architectural recommendation, not a completed integration. S3 is AWS's object-storage service; its [getting-started guide](https://docs.aws.amazon.com/AmazonS3/latest/userguide/GetStartedWithS3.html) describes the required AWS account and permissions. Configure only the access the chosen artifact workflow needs. AWS recommends [temporary credentials and IAM roles](https://docs.aws.amazon.com/IAM/latest/UserGuide/best-practices.html), including appropriate credential delivery for workloads outside AWS. A Brev instance on another provider does not automatically receive an EC2 instance role.

An account will also be needed if we later choose an AWS-hosted model service or Neptune graph storage. Neither is necessary to resolve the observed planning failures, and neither should be represented as implemented by the generic HTTP transport. Native Bedrock authentication/Converse, S3 adapters and Neptune ingestion/query support are still absent.

The supplied challenge brief mentions AWS credits in its competition tracks and provides Neptune resources. That is not evidence that credits are already active in this project account. The existing Brev budget is not treated as an AWS budget. No key creation or account provisioning is needed for the current experiment.
