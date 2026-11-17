# Reviewer HTTPS gateway

The default renderer below retains the authenticated reviewer gateway. The
opt-in [public saved-demo preparation](#prepare-a-scoped-public-demo-without-token-entry)
uses a separate backend, token and read-only data snapshot. Preparing either
packet makes no AWS calls and does not change the currently deployed site.

Reusable configuration for the [deployed reviewer gateway](../../../docs/evaluations/reviewer_https_delivery_20261113_summary.json).
See the [team guide](../../../docs/TEAM_REVIEW_GUIDE_20261113.md) for its checked
address and sign-in instructions. Running the renderer below only prepares
files; deploying another instance requires its own authorized scope.

This adds an AWS-provided HTTPS
hostname without requiring an owned domain. It uses native **ECS Express Mode**
(Fargate, ALB, managed hostname/certificate) and the standard NGINX reverse
proxy. No new scientific protocol or asynchronous job framework is introduced.
The existing EC2 app owns authentication, sessions, data, saved questions and
Neptune access. The gateway stores no source packet, workspace token, model key
or AWS application credential. It does not accept an Authorization value on the
user's behalf.

This gateway is **saved-data review mode**. Standard NGINX routing permits
GET/HEAD and only the exact POST routes for sign-in/out, guided saved questions,
saved path/source/Neptune inspection, native GO context and its separately
validated native packet download. GET/HEAD `/api/planner` is explicitly blocked
because optional provider setup can invoke a local version command. Other POSTs and all
other methods receive a JSON 403 explanation compatible with the app. Construction, fresh retrieval,
model planning, review changes and refresh cannot be invoked through this
endpoint. The full local/SSM app is unchanged. A guided question may save its
derived answer; this is not a globally read-only filesystem or per-user role.
Other allowed GETs expose all app-authenticated valid saved workspaces and
publications to this intended team; the gateway is not a TP53-only access rule.
Saved-refresh verification may create temporary replay files, without source
retrieval or changes to the original saved sources.
The backend has no HEAD handler, so a permitted HEAD request can return 501.

This is a **new billable ingress deployment and a new route to private data**.
Prepare and test first. Obtain the user's approval of the concrete resources,
network/authentication changes and intended reviewers before deploying or
changing the existing app. Commands below are operator instructions, not steps
the preparation script executes. No automatic deployment command is supplied.

## Prepare a scoped public demo without token entry

This mode reuses standard NGINX proxy-header injection and
[ECS secret delivery from SSM Parameter Store](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/secrets-envvar-ssm-paramstore.html).
It does **not** disable application authentication. The intended backend is a
separate saved-data-only instance of the same application image on the existing
VM's private port **8768**. The private operator app on **8766** and its token,
data, permissions and model configuration remain separate.

Before rendering, the operator must prepare and review a new read-only snapshot.
It contains only the approved saved folders, the two required restricted index
files and the native GO/QC context needed by those examples. Do not mount the
original runs root or indexes pointing outside the snapshot. Do not provide
model keys, the private operator token or Neptune operator configuration to the
public backend. Run it with the existing `--saved-data-only` policy, a read-only
container/data mount, bounded memory/CPU and writable ephemeral temporary/cache
space. Verify the two workspace IDs and their original graph/source/answer pins.
The renderer cannot verify the VM snapshot or its mounts.

Copy [public_scope.example.json](public_scope.example.json) into ignored `runs/`
and replace its snapshot ID and inventory-SHA placeholders with the actual
reviewed snapshot values. The example lists the **17** selected saved folders
and **102 exact GET paths** for the current examples. The two raw graph-handoff
folders are deliberately excluded. The exact fields are:

- `format`: `biograph-steward.public-demo-scope.v1`.
- `snapshot_id`, `snapshot_inventory_sha256`, `read_only_snapshot: true`:
  the separate reviewed data snapshot, not a claim made by this renderer.
- `run_ids`: every approved snapshot-folder ID, with no private experiments or
  synthetic fixture folders.
- `workspace_ids`: exactly the workspaces available to graph/source inspection.
- `get_paths`: exact approved bootstrap, saved run/question/agent-record,
  aggregate assessment and optional saved assay-reuse paths. No prefix grants.

The public mode permits only these four POST endpoints:
`/api/explore`, `/api/inspect-source`, `/api/protein-context` and
`/api/native-go-context`. Their request bodies can select only data mounted in
the separate snapshot. Question creation, live model calls, retrieval, review
edits, native-GO question creation, Neptune inspection and export-creation POSTs
are blocked. Source-agent status/jobs require one exact approved `run_id`.
Duplicate query keys, unexpected keys, unknown IDs, encoded paths and other
GETs are denied. Raw source/Gold/recovery/workspace ZIP routes are not anonymous.
An approved recorded-agent JSON download contains the same already-visible
result/trace/passports as its GET response. Local browser JSON export of an
already-visible graph does not obtain additional source files.

The narrow HTML presentation filters remove the exact known sign-out form,
hide creation/bulk-download controls and identify the site as a public saved
demo. A checked one-occurrence JavaScript hook suppresses only the otherwise
ID-less native-GO/QC packet-download control. Recorded-agent step tabs, saved
questions and source/path inspection remain. These presentation filters are
not security controls. NGINX's route maps, backend saved-only policy and the
separate read-only filesystem enforce the boundary independently.

```sh
python3 deploy/aws/reviewer_gateway/render.py \
  --public-demo --public-scope runs/PUBLIC_SCOPE.json \
  --upstream-ip PRIVATE_APP_IP --out runs/public_gateway_build_01
python3 -m unittest discover -s deploy/aws/reviewer_gateway -p 'test_*.py'
```

The public packet contains a token **placeholder**, never a token value. Its
separate Dockerfile uses the same pinned/patched NGINX base and starts as UID101.
ECS injects `BIOGRAPH_SERVER_TOKEN` from an existing SSM **SecureString holding
only the new public-backend token**. The startup script validates a 24–256
character base64url value, uses explicit-variable `envsubst` to render a private
`/tmp` config with mode0600, unsets the variable and executes NGINX. Missing or
invalid tokens fail before config creation. Config dumps, alternate configs and
debug-log arguments are rejected. Do not run `nginx -T`, shell tracing or commands
that print the container's environment. Query strings, headers and bodies are
omitted from gateway access logs. Client Authorization/Cookie values are
discarded, the public bearer is set upstream and Set-Cookie is stripped.
The gateway requests identity encoding only for root and the exact approved
HTML report pages that need presentation filtering. JSON forwards the browser's
`Accept-Encoding` unchanged so the app's existing large-response gzip support,
quality checks and response `Content-Encoding`/`Vary` remain effective.
The explicit-variable substitution follows the
[official NGINX image's existing envsubst mechanism](https://github.com/nginx/docker-nginx/blob/master/entrypoint/20-envsubst-on-templates.sh).
Exact GET targets use anchored, case-sensitive expressions because
[NGINX map string keys are case-insensitive](https://nginx.org/en/docs/http/ngx_http_map_module.html#map).

For a deployment packet, add the ordinary immutable-image/network arguments
shown below and `--ssm-parameter-arn arn:aws:ssm:us-east-2:ACCOUNT:parameter/NAME`.
The ARN must be in the gateway image's account. The generated public CloudFormation
template has optional `PublicDemoEnabled`/`SSMParameterARN` parameters, conditioned
`ssm:GetParameters` for that exact ARN, ECS container `Secrets` and conditioned
private port8768 ingress/egress rules. Existing8766 rules are preserved. It adds
no task role. The operator should use the AWS-managed SSM encryption key. A
customer-managed key would need separately reviewed, scoped `kms:Decrypt`
permission, which this template does not add. Secret rotation requires a new
task deployment, as documented by ECS. No secret or cloud resource is created by
the local renderer.

Preparation tests do not establish NGINX/CloudFormation acceptance. Before
rollout, the authorized operator must run:

1. `aws cloudformation validate-template --template-body file://PACKET/gateway.template.json`
   and inspect the change set for only the intended existing-service/IAM/SG
   changes. This is not permission to create another service or VM.
2. A real `nginx -t` in the built image using a disposable canary token. Then
   an isolated proxy test with a mock upstream. Check header overwrite,
   Cookie/Set-Cookie suppression, token absence in response/image/logs and the
   default-deny path/method/query cases in `test_public_demo.py`. Test invalid
   startup values and verify the runtime config permissions and unset environment.
3. The actual isolated public backend and candidate gateway. Open root and the
   selected saved agent, all four recorded steps, both workspace examples, path
   exploration, citation inspection and the aggregate assessment. Confirm there
   are no visible actions requiring a denied write route. Use no model calls.
4. Compare complete snapshot/private-source/review/index inventories before and
   after. Confirm no new question folders, no source changes and no access from
   the public backend to private operator data. The private backend must still
   reject a request lacking its own credential.

The public demo reveals the approved saved scientific content and its provenance
to anyone with the URL. Review metadata, source terms and exact content first.
For example, existing recorded model traces identify the old model endpoint and
some aggregate provenance files contain local paths. Those are not credentials,
but their disclosure must be intentional. A publicly downloadable database is
not automatically covered by this repository's software license.

## Why these established components

- [ECS Express Mode](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-getting-started.html)
  supplies a hostname such as `https://SERVICE.ecs.us-east-2.on.aws` and manages
  TLS/ALB/Fargate. No domain purchase or custom certificate is required.
- [Native CloudFormation resource](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-ecs-expressgatewayservice.html)
  and its typed `NetworkConfiguration`/`ScalingTarget` properties are used.
  The installed CLI's `create-express-gateway-service` skeleton also supports
  custom task definitions, subnet/security-group lists and min/max task counts.
- The [official custom-task contract](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/express-service-work.html)
  uses the supplied Fargate definition as-is: `Main`, one TCP port mapping,
  CPU 1024, memory 2048 MiB, linux/amd64 and **no `TaskRoleArn`**. The task
  execution role pulls the image/writes logs; its credentials are not given to
  NGINX. The infrastructure role uses AWS's documented managed policy.
- [NGINX proxy directives](https://nginx.org/en/docs/http/ngx_http_proxy_module.html)
  preserve root paths, methods, bodies, query strings, Host, Origin,
  Authorization, Cookie and response Set-Cookie. Caching and response buffering
  are disabled; no token is injected and failed upstream requests are not
  automatically retried.
- The existing cold Neptune request took about 239 seconds. Both proxy read
  timeout and the [ALB idle timeout](https://docs.aws.amazon.com/elasticloadbalancing/latest/application/edit-load-balancer-attributes.html)
  must be 600 seconds. Express has no idle-timeout property: the checked native
  `elbv2 modify-load-balancer-attributes` step below is required after creation.
  CloudFront's ordinary 120-second origin limit and App Runner's 120-second
  total limit do not cover that request. A longer timeout does not make it fast.

`image.lock.json` pins official NGINX **1.30.6-alpine** by index digest and records
the linux/amd64 child manifest. Registry response bytes and digest headers were
checked. The [official image definition](https://github.com/docker-library/official-images/blob/master/library/nginx)
and [NGINX advisories](https://nginx.org/en/security_advisories.html) were reviewed
for this selection; that is not a claim that the entire image is vulnerability
free. Build with `--platform linux/amd64` and review the ECR image scan.

The Dockerfile also pins Alpine's published `libxslt=1.1.43-r4` and
`zlib=1.4-r0` fixes. The original image's ECR scan reported three high and one
medium libxslt findings and one critical zlib finding. The rebuilt image's scan
completed with no findings on November 13; this is a dated scanner result, not
a vulnerability-free guarantee. These are vendor packages, not custom patches:
see Alpine's [immutable libxslt packaging and secfixes](https://raw.githubusercontent.com/alpinelinux/aports/e85ecba78539486bd0a685963ca5da3e1652fbd0/main/libxslt/APKBUILD)
and [zlib advisory](https://security.alpinelinux.org/vuln/CVE-2026-4738).
The initial archive/image and unsuccessful checks remain separate from the fixed
candidate. Production uses the fixed private ECR manifest digest.

## Prepare locally without AWS calls

Use the existing host's **verified private RFC1918 IPv4 address**, not its public
address or metadata endpoint. No account IDs or real VPC addresses belong in
the repository. Write generated packets under ignored `runs/`:

```sh
python3 deploy/aws/reviewer_gateway/render.py \
  --upstream-ip PRIVATE_APP_IP --out runs/reviewer_gateway_build_01
python3 -m unittest discover -s deploy/aws/reviewer_gateway -p 'test_*.py'
```

The renderer creates a fresh private output directory and refuses overwrite,
untrusted upstream addresses, mutable ECR image tags and incomplete deployment
parameters. It performs no network requests or AWS operations. The baked upstream
is fixed at private-IP port 8766; NGINX listens on 8080 as UID/GID 101. Its pid
and temporary paths are under `/tmp`. The official image entrypoint is bypassed.
Logs omit query strings, Authorization, cookies and request bodies. No app data
or secrets are copied into the image.

All five HTTP-module temporary paths use `/tmp`, following the
[NGINX maintainer's unprivileged-container guidance](https://github.com/nginx/docker-nginx-unprivileged#troubleshooting-tips).
An initial real syntax/startup check correctly failed when the unused FastCGI
default still pointed at the read-only `/var/cache/nginx`; that failed candidate
is retained separately. Preparation tests alone did not establish startup.

An approved isolated build can run:

```sh
docker build --platform linux/amd64 --pull \
  --tag biograph-reviewer-gateway:CANDIDATE runs/reviewer_gateway_build_01
docker run --rm --network none --read-only --tmpfs /tmp:rw,size=16m \
  biograph-reviewer-gateway:CANDIDATE -t
```

These local commands need Docker. Preparation unit checks do **not** replace
`nginx -t` or a real proxy replay. Before approval, test the candidate on a
loopback-only isolated endpoint with a disposable mock upstream: anonymous and
authenticated requests, POST login body, unmodified Origin/Host/Cookie headers,
Set-Cookie and Location responses, blocked construction/review/planner POSTs,
blocked PUT/DELETE, a delayed first response and a multi-megabyte
binary download with matching SHA256. Use dummy credentials only. No synthetic
test may be reported as a successful live-app login.

## Concrete deployment packet and permissions

`registry.template.json` creates a private, encrypted, immutable ECR repository
with scan-on-push; it is retained on stack deletion. After approval, build/push
the reviewed gateway image there and resolve the exact ECR digest. The ECS
template deliberately requires that private ECR digest. ECR is used to avoid
public-registry credentials/rate limits, not because Express only supports ECR.

Prepare a **second fresh packet** after the image exists:

```sh
python3 deploy/aws/reviewer_gateway/render.py \
  --upstream-ip PRIVATE_APP_IP --out runs/reviewer_gateway_deploy_01 \
  --gateway-image REGISTRY.dkr.ecr.us-east-2.amazonaws.com/REPOSITORY@sha256:DIGEST \
  --vpc-id vpc-EXACT --subnet-a subnet-EXACT_A --subnet-b subnet-EXACT_B \
  --app-security-group sg-EXISTING_APP
```

Verify that both subnets and the app SG are in the intended owned VPC; the
subnets must be public, in different AZs and have at least eight free IPv4
addresses each. The November 13 read-only preflight found three such subnets,
ECS API access and a 30-vCPU Fargate quota. A quota is a limit, not available
capacity. Successful reads and local schema preparation do not prove create
permissions or task launch.

The optional `gateway.template.json` creates:

- A dedicated ECS cluster, one custom task definition, a seven-day CloudWatch
  log group, the standard execution/infrastructure roles, and Express service.
- Min/max tasks **1/1**, CPU **1 vCPU**, memory **2 GiB**. Canary updates can
  temporarily run extra deployment tasks; 1/1 is not a global task/cost cap.
- A task identity SG with **no added ingress**, plus one rule in the existing
  app SG: TCP 8766 from that task SG only. Express independently manages its
  ALB/service SG path; inspect **all** attached task SGs after provisioning.
  The identity SG does not by itself prove aggregate egress restriction.
- AWS-managed ALB, HTTPS certificate/hostname, service networking/scaling and
  associated service-linked roles through the documented Express mechanism.

The operator needs CloudFormation deployment, ECS/Fargate/task registration,
ECR push, IAM creation/managed-policy attachment and `iam:PassRole`, plus the
underlying EC2/security-group, ALB, CloudWatch and scaling permissions required
by Express. New service-linked role creation may be required. See the official
[infrastructure role](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/infrastructure_IAM_role.html)
and [execution role](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/task_execution_IAM_role.html).
The managed infrastructure policy is substantial: review it as an intentional
delegation, not as read-only or a least-privilege proof.

In a first-use account, check the standard `AWSServiceRoleForECS` role before
cluster creation. The [CreateCluster API](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_CreateCluster.html)
attempts to create it automatically. The initial deployment here failed because
ECS could not yet assume that newly created role; the retry succeeded after
the role and its standard managed policy were present. Preserve failed stack
events and let rollback remove its new resources before reusing their identities.

For current canary services, use the documented
[`currentServiceRevisions`](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_ServiceCurrentRevisionSummary.html)
and [DescribeServiceRevisions](https://docs.aws.amazon.com/AmazonECS/latest/APIReference/API_DescribeServiceRevisions.html).
Do not require `DescribeServices` to repeat the task definition or load balancers
at its top level. Inspect revision-managed resources, all listener/default/rule
forwarding targets and the exact service's target groups before changing an
ALB-wide attribute. Also distinguish requested task SGs from the additional
Express-managed SG in the resolved service, a bare managed endpoint hostname
from its HTTPS URL, and a resolved image repository from its separate digest.

Use native CloudFormation validation and a reviewed change set before execution.
Deploy with the generated `gateway.parameters.json`, `CAPABILITY_IAM` and the
verified account/region. The templates contain no token/secret parameters.
Do not execute an unrelated existing stack update under this name.

## Activation order after approval

1. Preserve current image/unit/env hashes and existing token privately. Keep
   source graph, questions, publications and Neptune immutable.
2. Change only the existing app bind to `0.0.0.0`, retaining its port 8766,
   token and existing loopback origin support. With the current app SG still
   closed, verify that the SSM loopback login/saved answer still work. This
   permits later private gateway traffic without replacing SSM access.
3. Deploy the prepared gateway. Its health check proxies `/healthz`, which does
   not expose graph data. The app continues to require its token. Until its
   exact HTTPS origin is added, browser sign-in must fail closed.
4. Read `Endpoint` and `LoadBalancerArn` from this stack's outputs. Before
   allowing review traffic, apply the native ALB attributes:

   ```sh
   aws elbv2 modify-load-balancer-attributes --profile biograph --region us-east-2 \
     --load-balancer-arn REVIEWED_ALB_ARN \
     --attributes file://deploy/aws/reviewer_gateway/alb_attributes.json
   ```

   Inspect/record attributes after the update. An Express-created ALB can be
   shared; verify its service inventory before changing attributes. No custom
   CloudFormation resource or Lambda hook is used to hide this operation.
5. Add only the returned exact root **HTTPS origin** to the existing app's
   `BIOGRAPH_ALLOWED_ORIGINS`, preserving any already approved origins and all
   other env bytes/token. Do not trust a forwarded header or inject a bearer
   token at the gateway. Restarting the app revokes browser sessions; saved
   questions remain. The app's explicit HTTPS Origin sets a Secure session
   cookie even though the private ALB→gateway→app legs use HTTP.
6. Verify actual unauthenticated denial; correct and wrong-token login; cookie
   Secure/HttpOnly/SameSite; foreign/missing/null Origin denial; sign-out; SSM
   access; the TP53 saved answer; GO inspector; cold Neptune verification;
   large run/question ZIP bytes and restart persistence. Preserve source hashes
   and before/after graph/question/publication inventories. A TCP/TLS health
   check or warm-only replay is insufficient.
7. Give reviewers the checked HTTPS root and access token **separately and
   privately**. Update the guide only once the browser route works. Never put
   a token in a URL, template, Docker image, feedback screenshot or repository.

App authentication remains a shared workspace credential, not individual-user
authorization. The gateway's explicit route allowlist restricts this ingress;
it does not change the token's authority on the private local/SSM app. Use only
the intended trusted team, keep the qualified workspace read-only, and state
that scope in the approval request.

## Rollback and stopping charges

Retain SSM access throughout. To withdraw access, remove the added HTTPS origin
and restore the exact prior app environment/bind, restart and verify loopback
access, then remove the new gateway stack/rule using the authorized rollback
plan. Existing graph/data/Neptune stacks are not rollback targets. Verify the
Express deletion has removed its service and unused ALB/networking resources;
shared ALBs may remain. ECR and the log group have retain policies and require
separate intentional cleanup. Stopping EC2 alone does not stop ALB/Fargate
charges. Do not delete the execution/infrastructure roles before Express
resource cleanup completes.
