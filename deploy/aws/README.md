# AWS workbench deployment

This deployment uses the existing core app and Dockerfile. AWS hosts a CPU
workbench, its persistent evidence volume and private release/backup storage.
The NVIDIA model can remain in Brev; no AWS GPU, Bedrock or Neptune is required.
The optional [Neptune Database deployment](NEPTUNE.md) extends this workbench
with a private persistent graph for the production-style comparison and
snapshot/recovery test. That add-on requires a Paid Plan.
The November 11 live checkpoint deployed a `t3.large` workbench and the optional
Neptune add-on on a Paid Plan. Automated access, persistence and recovery checks
passed; see the [deployment assessment](../../docs/evaluations/AWS_NEPTUNE_20261111.md)
for the tested scope and remaining checks. The CPU-only Free Plan path below
remains a separate starting option.

The final public saved-data snapshot uses the existing `t3.large` host. Its
read-only backend container has a **3 GiB memory limit and 1 CPU**. A measured
2.08 GiB peak exceeded its earlier 2 GiB limit while opening the full saved
graphs. Raising that container allowance used existing host RAM and preserved
the source files, gateway, private app and Neptune configuration. This is a
verified setting for the supplied snapshot, not a load benchmark or evidence
that the smaller Free Plan instance can host these full profiles. See the
[delivery receipt](../../docs/evaluations/usability_delivery_20261117/hosted_acceptance.json)
and Docker's [memory-limit documentation](https://docs.docker.com/engine/containers/resource_constraints/).

The public KRAS example also offers **Download an editable local copy**. Its prepared
ZIP includes the app, full saved graph, source files, question and recorded
agent job. A local Python launcher opens the copy for evidence reviews that
save in a new run. The hosted snapshot stays read-only. The backend streams a
checksum-verified archive from a separate read-only `BIOGRAPH_EDITABLE_COPY_DIR`
mount on the persistent data volume, outside the immutable source snapshot.
The gateway permits only the registered metadata and archive GET/HEAD routes;
it does not enable public writes, model calls or fresh retrieval. See the
[editable-copy delivery record](../../docs/evaluations/editable_demo_copy_20261117/README.md).

## Start with the Free Plan

The initial deployment can use the **Free Plan and signup credits** (for
example, the $100 signup-credit balance for an eligible new account).
A Paid Plan upgrade or external challenge-credit redemption is **not required**
for this path. The template defaults to **t3.small** (2 vCPU, 2 GiB RAM), an
x86_64 type documented as [Free Tier eligible for new accounts](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html).
The optional `t3.medium` and `t3.large` values are for account plans that permit
them; do not select them on the initial Free Plan.

On November 11, 2026, authenticated read-only AWS checks verified the owned
target account in **us-east-2**, `t3.small` eligibility, an available us-east-2a
subnet with an active internet-gateway route, and an Amazon Linux 2023 x86_64
AMI marked Free Tier eligible. Both templates passed real AWS template
validation before this default-instance adjustment. At that preflight checkpoint,
no deployment resources had been created, and bootstrap, app startup, SSM access,
persistence and backups had not been tested live. The later
[live checkpoint](../../docs/evaluations/AWS_NEPTUNE_20261111.md) used `t3.large`;
it does not establish sufficient memory for the `t3.small` default.

Use the **owned** project selected during setup; a previously inspected shared
project is excluded. Account identifiers and private preflight receipts belong
in local deployment records. With AWS CLI 2.32.0 or newer and profile `biograph`,
replace `REGION` below with the selected account's verified region (us-east-2
for this checkpoint):

```sh
aws login --profile biograph --region REGION
aws sts get-caller-identity --profile biograph --region REGION
```

Confirm the returned account matches the intended owned account before creating
resources; compare it with your recorded `EXPECTED_ACCOUNT_ID`. See
[AWS CLI sign-in](https://docs.aws.amazon.com/signin/latest/userguide/command-line-sign-in.html).
Successful sign-in and template validation do not prove resource-creation
permission or successful runtime deployment. Recheck the resolved AMI's Free
Tier eligibility when using the latest-AMI parameter or another region.

The existing signup-credit balance was visible in the account. Eligible compute,
EBS, public IPv4 and S3 usage draws on that balance. For the Ohio checkpoint,
AWS pricing API results were $0.0208/hour for t3.small, $0.005/hour for its public
IPv4, and $0.08/GB-month for gp3. The default 16 GiB root plus 30 GiB evidence
volumes and a continuously running instance total approximately **$0.75/day**,
excluding S3, transfer and other usage. This is an estimate, not a daily cap.
Check [EC2](https://aws.amazon.com/ec2/pricing/on-demand/),
[EBS](https://aws.amazon.com/ebs/pricing/) and
[VPC](https://aws.amazon.com/vpc/pricing/) rates before launch.

The [Free Plan](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html)
ends when its signup credits are exhausted or six months after account creation,
whichever comes first. Monitor its balance and expiration; stopping the instance
leaves EBS/S3 storage consuming credits. A Paid Plan project spend limit is not
a prerequisite for this Free Plan path.

The [supported services](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html)
include this template's services. [Project policies](https://docs.aws.amazon.com/accounts/latest/reference/scps-and-rcps-for-projects.html)
still apply; no need for advanced features has been established. Keep the S3
bucket, EC2 instance and EBS volume in the verified target region.

### External promotional credits

External challenge-credit redemption and its status are handled privately.
The Free Plan is ineligible for other promotional credits; the November 11
Neptune checkpoint already uses a Paid Plan. Private award details, balances
and codes are not stored here.

The [AWS Settings redemption flow](https://docs.aws.amazon.com/accounts/latest/reference/view-redeem-credits.html)
is Billing → Current charges → available credits → Redeem credit. Eligible
credits automatically apply across projects the user owns. On a Paid Plan,
usage beyond applicable credits can incur charges. Its optional [project spend
limits](https://docs.aws.amazon.com/accounts/latest/reference/create-spend-limit.html)
exclude credits and apply to pre-tax charges; they are separate from the credit
balance and from a Free Plan cap.

## Resources and access

- `storage.template.json`: an S3 bucket with versioning, AES256 server-side
  encryption, blocked public access, bucket-owner enforcement and TLS-only access.
- `workbench.template.json`: one Amazon Linux 2023 EC2 instance (`t3.small`
  default), an encrypted 30 GiB gp3 evidence volume and the required instance role.
- The security group has **no inbound rules**. The app binds host loopback port
  8766. AWS Systems Manager Session Manager provides shell access and a local
  browser tunnel. It needs no SSH key or open port 22.
- The host receives a public IPv4 address for outbound package, source and SSM
  access. This is not a public app endpoint. The existing subnet must have an
  internet-gateway route. No NAT gateway or load balancer is created.
- The data volume and S3 bucket are retained when their stacks are deleted.
  Instance stop/start preserves the mounted evidence. The root/code disk is
  disposable; local workspace access tokens are generated on that disk.

A new role obtains only its exact S3 source object, its own backup prefix and
the standard AWS-managed SSM node permissions. The deployer separately needs
permission to create the stacks, EC2/EBS/security-group resources, IAM instance
role/profile and S3 bucket, including `iam:PassRole`. CloudFormation requires
`CAPABILITY_IAM`. The project owner can grant the required project access or
deploy the templates and delegate operation of the resulting resources.
**Do not share the owner's access keys.**
AWS CloudShell can run the CLI commands under an authenticated console session
when local CLI access is not yet configured.

This private deployment requires an authorized AWS operator for the SSM tunnel.
An anonymous judge-facing HTTPS URL is a separate delivery choice. Do not expose
8766 or a workspace token over public HTTP to create one.

## Prepare a committed source release

Commit the selected app and deployment files, then use a new output directory:

```sh
python3 deploy/aws/prepare_release.py --ref HEAD --out runs/aws_release_01
```

This uses `git archive`, not the local data directory or private GitHub checkout
credentials. It includes the runtime, existing Dockerfile and AWS scripts and
writes a SHA256 receipt. It refuses links and unexpected dataset/credential
paths. Generated `.env`, caches and scientific runs do not enter the code bundle.

These examples use the `biograph` profile. Replace `REGION` with the verified
user-owned project region. In CloudShell, omit `--profile` and confirm the
same project/account and region:

```sh
aws sts get-caller-identity --profile biograph --region REGION
aws cloudformation deploy --profile biograph --region REGION \
  --stack-name biograph-storage \
  --template-file deploy/aws/storage.template.json
aws cloudformation describe-stacks --profile biograph --region REGION \
  --stack-name biograph-storage --query 'Stacks[0].Outputs' --output table
```

Upload the generated archive to that bucket using an immutable commit-specific
key:

```sh
aws s3 cp runs/aws_release_01/biograph-COMMIT.tar.gz \
  s3://BUCKET/releases/COMMIT/biograph-COMMIT.tar.gz \
  --profile biograph --region REGION --sse AES256
```

Use the actual commit, bundle name and SHA256 from `release.json`. Select an
existing public subnet in that region and its matching VPC/availability zone.
The deployer can inspect these without starting an instance:

```sh
aws ec2 describe-subnets --profile biograph --region REGION \
  --query 'Subnets[].{Subnet:SubnetId,Vpc:VpcId,AZ:AvailabilityZone,PublicIPv4:MapPublicIpOnLaunch}' \
  --output table
```

The subnet also needs an effective `0.0.0.0/0` route to an internet gateway.
`MapPublicIpOnLaunch` alone does not establish that route. Do not guess an AZ
different from the selected subnet.

## Launch the workbench

The following command creates billable resources. Confirm the account, region
and credit balance, then replace every placeholder before running:

```sh
aws cloudformation deploy --profile biograph --region REGION \
  --stack-name biograph-workbench \
  --template-file deploy/aws/workbench.template.json \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    VpcId=vpc-EXACT SubnetId=subnet-EXACT AvailabilityZone=EXACT-AZ \
    ArtifactBucket=BUCKET ArtifactKey=releases/COMMIT/biograph-COMMIT.tar.gz \
    ArtifactSha256=EXACT-SHA256
aws cloudformation describe-stacks --profile biograph --region REGION \
  --stack-name biograph-workbench --query 'Stacks[0].Outputs' --output table
```

The instance verifies the archive before executing its bootstrap. It maps the
EBS volume by its stable volume serial, formats only the new empty disk, mounts
by filesystem UUID and starts the existing container under systemd. The app
still runs as UID/GID 10001. A separate CloudFormation readiness condition waits
for the volume attachment and app health, so stack success represents completed
startup rather than only VM creation. No access token is a CloudFormation
parameter or output, and bootstrap does not print the generated token.

The base image defaults to the existing `python:3.12-slim` Docker tag. For a
frozen deployment, supply a reviewed image digest with `PythonImage=...` and
retain the resolved AMI and `/etc/biograph/image-id`. The startup SHA verifies
the source bundle, not reproducibility of an unpinned base image or package mirror.

This initial template is intended for a frozen challenge release. It does not
implement rolling app updates or evidence migration. User data does not rerun
on ordinary stop/start; a new source parameter is not an automatic code rollout.
Back up data and use a new release stack when replacing the host. Retained
volumes are not silently adopted by a new stack.

## Connect and verify

Install the official Session Manager plugin on the operator's computer if it is
not present. Use the instance ID from the stack output:

```sh
aws ssm start-session --profile biograph --region REGION \
  --target i-EXACT --document-name AWS-StartPortForwardingSession \
  --parameters portNumber=8766,localPortNumber=8766
```

Open `http://127.0.0.1:8766/`. Keep the same local and remote port to match the
app's existing origin policy. In a separate SSM shell, an authorized operator
can read `sudo cat /etc/biograph/access-token` privately and enter that token
in the app. Keep it out of chat, logs, source control and URLs.

Use the existing [deployment smoke procedure](../../docs/PORTABILITY.md#check-the-running-deployment)
for the installed version: check startup/authentication/origin handling, save a
synthetic question, restart `sudo systemctl restart biograph.service`, then
reopen the same saved run. These checks make no model or source API requests
unless the explicit optional planner flag is used.

Import compatible real run folders through the established source-packet
procedure, preserving every manifest and source file. `graph.json` alone is
not a complete workspace. AWS storage does not alter evidence qualifications,
review state or the gold-interface decision contract.

## Back up and stop

In the authorized SSM shell:

```sh
sudo bash /opt/biograph/app/deploy/aws/backup.sh
```

The backup pauses the app briefly, writes a standard tar archive plus SHA256
sidecar, restarts the service and uploads both under the host's private S3
prefix. It first checks conservative staging space in `/var/tmp`; the default
16 GiB root volume cannot stage a full 30 GiB evidence volume. For a larger
workspace, provide sufficient root/staging capacity before backing it up.
Stop separate write-producing CLI jobs before capturing the archive.
Tokens and model credentials live outside the data mount and are excluded.
The upload uses the instance role, not a copied AWS access key. Download the
archive and sidecar to a new recovery directory, verify `sha256sum --check`,
and restore only while the destination service is stopped. Never unpack over
the only surviving source data.

Stop compute without deleting evidence:

```sh
aws ec2 stop-instances --profile biograph --region REGION --instance-ids i-EXACT
```

Stopping ends the running instance charge, while retained EBS/S3 storage
continues to accrue charges. Running cost includes the selected CPU instance,
root and evidence EBS volumes, one public IPv4 address, and S3 storage/requests.
Check current regional prices and applicable credit coverage before launch.
The template disables unlimited T3 CPU credits. It creates no paid GPU, NAT
gateway, load balancer, Bedrock invocation or Neptune database.

## Established AWS mechanisms

This adapts the existing Docker app to standard AWS services. It does not add
a cloud-specific graph format or replace the existing agent workflow.

- [Session Manager port forwarding](https://docs.aws.amazon.com/systems-manager/latest/userguide/session-manager-working-with-sessions-start.html)
- [EC2 CloudFormation resource](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-ec2-instance.html)
- [WaitCondition with a creation policy](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-cloudformation-waitcondition.html)
- [SignalResource readiness](https://docs.aws.amazon.com/cli/latest/reference/cloudformation/signal-resource.html)
- [Stable EBS NVMe mapping](https://docs.aws.amazon.com/ebs/latest/userguide/identify-nvme-ebs-device.html)
- [Formatting and mounting EBS](https://docs.aws.amazon.com/ebs/latest/userguide/ebs-using-volumes.html)
- [Docker on Amazon Linux 2023](https://docs.aws.amazon.com/AmazonECS/latest/developerguide/create-container-image.html)
- [S3 CloudFormation properties](https://docs.aws.amazon.com/AWSCloudFormation/latest/TemplateReference/aws-resource-s3-bucket.html)
