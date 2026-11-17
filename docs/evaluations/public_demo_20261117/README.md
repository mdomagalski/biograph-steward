# Public saved-demo delivery

[Open the recorded KRAS investigation](https://bi-3a117d5e2b3942678dc518fce65ab5d2.ecs.us-east-2.on.aws/?run=native_evidence_workspace_20261115&question=native_physical_KRAS_question_v3_20261115&agent_job=source_agent_eval_dc7b597201da_S01&view=data).
No token, AWS account or running model is required. The existing AWS address
now serves a separate read-only snapshot of the two designated real-data
workspaces. The private operator application retains its own authentication.

The [server acceptance](hosted_acceptance.json) verifies the deployed image,
anonymous HTTPS entry, one healthy gateway task and the unchanged load balancer.
The [live browser check](hosted_browser_acceptance.json) follows the direct
example through all four recorded agent steps, source inspection, the five
task tabs, graph export and mobile navigation. These are functional checks,
not an independent user study. A prior bare-root navigation attempt reported
a Mac Chrome network-change error; it is preserved, and its cause is not
claimed resolved. The direct example completed without that error.

The [candidate acceptance](candidate_acceptance.json) separately records
real-source inspection and qualification checks, plus invented upstream tests
of NGINX routing and credential isolation. Source data, model records, graph
content and scientific results were not changed by this access update. Bulk
source and graph packages remain separate submission or private operator assets.

The [final operations receipt](final_operations.json) verifies all 732 snapshot
files against their originals, enables the public service at boot and records
cleanup of the temporary proxy and tunnel. Neither application was restarted.

Current artifact receipts:

- [Final report](final_report.json): four pages, with only access wording changed.
- [Team guide](team_review_guide.json): two pages with direct examples and five tasks.
- [Software instructions](software_access_copy.json): only the packaged README
  changed; the other 132 archive members are byte-identical.

The separate [Neptune resize assessment](../NEPTUNE_RIGHTSIZE_20261117.md)
records four successful full-parity checks and two available T4g medium
instances, retaining a writer and failover reader. Base database compute is
approximately $4.46/day, before storage, I/O, other AWS services and possible
burst CPU charges.
