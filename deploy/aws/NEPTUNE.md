# Private Neptune comparison deployment

This add-on uses **Neptune Database**, the existing EC2 workbench and the same
private artifact bucket. By default it creates one provisioned **db.r6g.large** writer,
encrypted storage, IAM-authenticated HTTPS, seven-day automated backups and a
same-region S3 gateway endpoint for the official bulk loader. It adds no public
8182 access or NAT gateway. One writer is an integration and recovery test;
it does not establish high availability. An optional reader in the second AZ
can be enabled for a separately recorded failover test.

`WriterInstanceClass` and `ReaderInstanceClass` independently select
`db.r6g.large` or `db.t4g.medium`; both default to the original R6g class.
The existing Ohio demo now uses two T4g medium instances, with the reader
enabled. Its [staged resize assessment](../../docs/evaluations/NEPTUNE_RIGHTSIZE_20261117.md)
records full graph parity before and after reader resize, failover and final
reader verification. This qualifies the smaller capacity for the current
saved workload. Broader workloads need their own capacity assessment, including
memory headroom and burst CPU charges. The CloudFormation logical names do not
identify current writer/reader roles after failover; inspect the live cluster
members before changing either instance.

Neptune requires an eligible **Paid Plan** in the new AWS experience. The CPU
workbench can run on the Free Plan, but that does not unlock Neptune. The user
completes any plan change and external credit redemption privately. Do not store
award emails or codes in the repository. [Supported services](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html)

## Preflight and create

Use a selected account and region, not a default browser project. Verify
`EXPECTED_ACCOUNT_ID`, the available credit and applicable plan before creation.
Review current regional Neptune pricing, including storage, I/O, backups and
the temporary instance used for recovery. The
[November 11 live assessment](../../docs/evaluations/AWS_NEPTUNE_20261111.md)
records successful deployment, database reconstruction, failover and snapshot
recovery for the frozen cohort. Repeat these checks for a new deployment;
local tests alone do not establish successful AWS startup.

The November 11 Ohio pricing API checkpoint returned $0.3287/hour for a
Standard db.r6g.large writer: about $47.33 for six continuous days of database
compute alone. I/O-Optimized was $0.443/hour. This template uses Standard
storage, so include actual storage, I/O, backups and workbench costs separately.
[Neptune pricing](https://aws.amazon.com/neptune/pricing/)

First deploy the [workbench](README.md). Its outputs now include `VpcId`,
`SubnetId`, `AppSecurityGroupId` and `InstanceRoleName`. The add-on takes these
as parameters and attaches its read-only graph policy to that new instance
role. It does not modify a managed project access role.
The AWS bootstrap builds the existing container with `INSTALL_AWS=1`, using
the committed, hash-locked `requirements-aws.txt`. The source bundle includes
that lock file. No SDK installer or credential is downloaded from the graph.

Select two existing subnets in different AZs of that VPC. Verify their actual
AZs, effective route tables, default tenancy and VPC DNS hostnames/resolution.
Parameter rules reject identical subnet IDs or AZ names; they cannot verify
that a supplied subnet really belongs to the supplied AZ/VPC. The same-region
artifact bucket must contain the import files. [VPC requirements](https://docs.aws.amazon.com/neptune/latest/userguide/get-started-vpc.html)

Pin an exact regional engine version and verify that the instance is orderable:

```sh
aws neptune describe-db-engine-versions --profile biograph --region REGION \
  --engine neptune --query 'DBEngineVersions[].EngineVersion' --output table
aws neptune describe-orderable-db-instance-options --profile biograph --region REGION \
  --engine neptune --engine-version EXACT-VERSION --db-instance-class db.r6g.large
aws ec2 describe-vpc-endpoints --profile biograph --region REGION \
  --filters Name=vpc-id,Values=vpc-EXACT Name=service-name,Values=com.amazonaws.REGION.s3
```

Use a current engine at least 1.2.0.2 for custom property-graph IDs and current
IAM query permissions. `EngineVersion` is required rather than silently using
an unverified latest release. Confirm both DB subnet route tables are covered
by the S3 gateway endpoint. If that endpoint already exists, supply
`CreateS3GatewayEndpoint=false` and reuse it; do not create a competing S3 route.

The following creates billable resources after its placeholders are replaced:

```sh
aws cloudformation deploy --profile biograph --region REGION \
  --stack-name biograph-neptune --template-file deploy/aws/neptune.template.json \
  --capabilities CAPABILITY_IAM \
  --parameter-overrides \
    VpcId=vpc-EXACT DbSubnetA=subnet-A DbSubnetB=subnet-B \
    PrimaryAvailabilityZone=REGIONa SecondaryAvailabilityZone=REGIONb \
    AppSecurityGroupId=sg-APP AppInstanceRoleName=WORKBENCH-ROLE \
    ArtifactBucket=BUCKET GraphObjectPrefix=neptune/import/FROZEN-RELEASE/ \
    S3RouteTableIds=rtb-A,rtb-B EngineVersion=EXACT-VERSION \
    AllowInitialGraphImport=false EnableReader=false
aws cloudformation describe-stacks --profile biograph --region REGION \
  --stack-name biograph-neptune --query 'Stacks[0].Outputs' --output table
```

The DB accepts TCP8182 only from the workbench security group. The add-on also
adds the missing outbound TCP8182 rule to that app group; its existing HTTPS
443 rule alone cannot reach Neptune. The writer and optional reader explicitly
set `PubliclyAccessible=false`. Neptune enforces TLS; keep certificate
verification enabled. Access the graph from the EC2 host/container in the VPC,
with an instance-role SDK or CLI, rather than exposing the database to a laptop.

## S3 and one initial import phase

The gateway endpoint deliberately uses AWS's standard full-access endpoint
policy. It is a transport policy and does not grant identities S3 access. A
bucket-only endpoint policy can unintentionally block other same-route-table
S3 traffic, including app releases or Amazon Linux repositories. Bucket public
access remains blocked, the bucket requires TLS, and the loader role permits
only GetObject/GetObjectVersion and prefix-constrained ListBucket for the
dedicated import prefix. The loader cannot write or delete objects. Verify an
existing endpoint policy permits these same operations if reusing one.
[S3 gateway policies](https://docs.aws.amazon.com/vpc/latest/privatelink/vpc-endpoints-s3.html)

The normal app policy allows only OpenCypher `ReadDataViaQuery` and engine
health, scoped to the cluster resource ID. It does not permit graph writes,
bulk loading, IAM role passing or import-prefix uploads. To initialize a frozen
graph, update the stack with **the same parameter values** and
`AllowInitialGraphImport=true`. This temporarily attaches a separate policy
allowing the official loader, query writes, passing only the attached loader
role to RDS, and staging objects under the import prefix. It grants neither
delete queries nor database reset. This parameter does not automatically run
an import. IAM propagation can take up to ten minutes; record when privileges
are enabled and later removed. [Data permissions](https://docs.aws.amazon.com/neptune/latest/userguide/iam-dp-actions.html)

Use [the documented openCypher CSV format](https://docs.aws.amazon.com/neptune/latest/userguide/bulk-load-tutorial-format-opencypher.html),
with separate UTF-8 node and relationship files, preserving stable IDs. Reject
duplicate IDs before upload: the loader's duplicate resolution can select
properties nondeterministically. Upload only CSV data files to the selected
loader prefix; keep manifests/source packets outside it because the loader
attempts every file in the selected folder. Preserve the immutable canonical
workspace, provenance and disposition ledger in the ordinary artifact backup.

From the VPC host, the official CLI supports the same IAM-authenticated Data
API used by boto3. Use stack outputs for the endpoint, loader role and source:

```sh
AWS_MAX_ATTEMPTS=1 aws neptunedata start-loader-job --region REGION \
  --endpoint-url https://CLUSTER-ENDPOINT:8182 \
  --source s3://BUCKET/neptune/import/FROZEN-RELEASE/ \
  --format opencypher --s3-bucket-region REGION --iam-role-arn LOADER-ROLE-ARN \
  --mode NEW --parallelism LOW --fail-on-error \
  --no-update-single-cardinality-properties
aws neptunedata get-loader-job-status --region REGION \
  --endpoint-url https://CLUSTER-ENDPOINT:8182 --load-id LOAD-ID --details --errors
```

`LOW` avoids the documented openCypher deadlock risk with HIGH/OVERSUBSCRIBE.
Require `LOAD_COMPLETED` with zero recorded errors, then compare identifiers,
edge counts, qualifications, provenance and fixed query results with the frozen
local source. A loader success alone does not establish lossless integration
or scientific accuracy. [Loader behavior](https://docs.aws.amazon.com/neptune/latest/userguide/load-api-reference-load.html),
[known parallelism issue](https://docs.aws.amazon.com/neptune/latest/userguide/bulk-load-optimize.html)

Before acceptance, update **all unchanged parameters plus**
`AllowInitialGraphImport=false`, wait for completion/propagation, and demonstrate
read queries still work while a harmless write is denied. Do not leave initial
import privileges enabled for a demo. Keep the deployed source immutable until
that revocation check passes. New import batches require an explicitly recorded
deployment phase; they are not exposed as a browser agent capability.

## Snapshot, recovery and export acceptance

### Application and verified graph operations

The optional AWS environment uses the hash-locked SDK in
`requirements-aws.txt` (`boto3==1.44.0`). The ordinary core app still works
without it. Export a saved workspace through its existing verified reader:

```sh
python3 app.py neptune-export --run runs/SOURCE --out runs/NEPTUNE-PROJECTION
```

Upload only `nodes.csv` and `relationships.csv` to the loader's dedicated S3
prefix. Keep `projection_manifest.json` with the source and audit artifacts,
outside that prefix. Its dataset identifier binds the complete graph digest.
The initial scoped CRC graph contains 9,746 biological entities and 15,717
source evidence relationships. Its 34,823 Neptune vertices additionally include
qualified assertions, ordered context and metadata records; these are not new
biological discoveries. The frozen Pharos319 baseline remains explicitly dated.

From the VPC host/container with the temporary import policy enabled:

```sh
python3 app.py neptune-load --neptune-endpoint https://CLUSTER-ENDPOINT:8182 \
  --aws-region REGION --source-s3-uri s3://BUCKET/CSV-ONLY-PREFIX/ \
  --loader-role-arn LOADER-ROLE-ARN --out /data/loader-start.json
python3 app.py neptune-load-status --neptune-endpoint https://CLUSTER-ENDPOINT:8182 \
  --aws-region REGION --load-id LOAD-ID --out /data/loader-status.json
python3 app.py neptune-verify --run /data/runs/SOURCE \
  --neptune-endpoint https://CLUSTER-ENDPOINT:8182 --aws-region REGION \
  --out /data/neptune-verification.json
python3 app.py neptune-export-verified --run /data/runs/SOURCE \
  --neptune-endpoint https://CLUSTER-ENDPOINT:8182 --aws-region REGION \
  --out /data/neptune-roundtrip
```

The last command freshly reads the database, reconstructs every ordered record
inventory and metadata field, and checks the complete graph digest before
publishing `graph.json` and `export_receipt.json`. It inverts this application's
projection; AWS's generic `neptune-export` remains the option for other database
representations. Local source data cannot silently replace a failed database
read.

After the import policy is revoked, set `BIOGRAPH_NEPTUNE_ENDPOINT` and
`BIOGRAPH_AWS_REGION` in the root-owned runtime environment and restart the app.
The **Evidence** tab's Neptune card performs a real database neighborhood read,
checks its original IDs, payloads and qualifications, and opens the existing
source guides. A full parity audit is cached per immutable graph for that server
instance; returned records are checked freshly. Endpoint credentials are never
entered through this browser view. The app exposes no arbitrary query or loader
operation. Other saved-workspace tools continue to enforce their existing
scientific and review semantics.

### Recovery acceptance

The cluster has deletion protection, seven-day automated backups, and explicit
CloudFormation `Snapshot` deletion/replacement policies. Deleting the stack is
not a backup test. Intentional retirement first requires a verified manual
snapshot and a deliberate deletion-protection change; otherwise deletion fails.
The instance resources themselves are disposable and use `Delete`; graph data
and automated backup policy belong to the cluster. [Backup semantics](https://docs.aws.amazon.com/neptune/latest/userguide/backup-restore.html)

For recovery, create a manual DB cluster snapshot, restore it to a **new**
cluster with the same private subnet/security/IAM/encryption settings, create a
writer instance in that restored cluster, and verify the same source identifiers,
counts, ledger state and fixed answers before switching any endpoint. The new
cluster has a different resource ID: an authorized operator must grant temporary
read access to that ID for verification. Retain the original until recovery is
verified. Record engine, source commit/hash, snapshot ID, restoration duration
and result comparisons. Provisioned snapshot restoration is a paid operation.

Keep ordinary canonical source packets and graph exports in the private S3
backup. For an independent property-graph export, reuse AWS's
[neptune-export CLI](https://docs.aws.amazon.com/neptune/latest/userguide/neptune-export.html)
on the VPC host; native engine export is currently for RDF. Export from a frozen
graph or clone to obtain consistent results. No Batch export service is needed
for the initial bounded cohort. The
[November 11 live assessment](../../docs/evaluations/AWS_NEPTUNE_20261111.md)
records successful export and snapshot-recovery verification for this mirror.
Each new dataset or deployment still needs its own verification receipts.

An optional second-AZ reader can be enabled with `EnableReader=true` after the
single-writer comparison works. Only then run and record a real failover test;
the default one-writer configuration is not presented as an HA deployment.

Use `DBClusterMembers[].IsClusterWriter` to identify the current writer, rather
than inferring its role from a CloudFormation logical name. Initial concurrent
instance creation and later failovers can change which physical instance owns
that role. Before setting `EnableReader=false`, confirm that the physical
instance mapped to `WriterInstance` is the current writer; promote it and verify
fresh reads first if necessary. Otherwise the update could remove the current
writer. The application uses the cluster endpoint and reports failed reads
without substituting local files. Reconnect and verify after promotion; brief
read interruptions are expected during failover. See the
[cluster-member and failover API](https://docs.aws.amazon.com/neptune/latest/userguide/api-clusters.html)
and [endpoint guidance](https://docs.aws.amazon.com/neptune/latest/userguide/feature-overview-endpoints.html).
