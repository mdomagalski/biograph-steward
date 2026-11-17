# AWS deployment access and plan status

Updated 2026-11-11. The selected deployment target is the user's **owned**
project in **us-east-2**. The previously inspected shared project is excluded.
The `biograph` CLI profile is authenticated and STS verified the target account.
Keep account identifiers and private receipts in local deployment records.

The [November 11 live checkpoint](evaluations/AWS_NEPTUNE_20261111.md) uses a
**Paid Plan**, a `t3.large` workbench and Neptune. The earlier CPU-only starting
path could use the Free Plan and eligible signup credits without an upgrade;
Neptune requires the Paid Plan. Private award details, balances and codes are
not stored here.

## Earlier preflight and current deployment

- At the November 11 preflight, read-only AWS checks verified `t3.small` as Free Tier eligible (2 vCPU,
  2 GiB RAM), an Amazon Linux 2023 x86_64 AMI marked eligible, and a public subnet
  in us-east-2a with an active internet-gateway route.
- Both templates passed AWS `validate-template` before the default was changed
  from t3.medium to **t3.small**. Revalidate the exact release before deployment.
- At that checkpoint, no deployment resources had been created; Linux bootstrap,
  container startup, SSM access, app persistence and backups were unverified.
- The later [live assessment](evaluations/AWS_NEPTUNE_20261111.md) records those
  deployment and automated recovery checks on `t3.large`, plus Neptune parity,
  failover and native snapshot recovery. It does not establish memory sufficiency
  for the `t3.small` default. For another deployment, verify the owned account,
  applicable plan and budget, then follow [the guide](../deploy/aws/README.md).

The template now defaults to t3.small. Larger optional instance types require
an account plan that permits them. [EC2 Free Tier eligibility](https://docs.aws.amazon.com/AWSEC2/latest/UserGuide/ec2-free-tier-usage.html)
and the [new-experience service list](https://docs.aws.amazon.com/accounts/latest/reference/supported-services-sign-up-new.html)
support this starting path; regional availability and account permissions still
need to hold for the exact deployment.

For session renewal, use AWS CLI 2.32.0 or newer, replace `REGION` with the
verified target region (us-east-2 at this checkpoint), and select the owned
project in the browser:

```sh
aws login --profile biograph --region REGION
aws sts get-caller-identity --profile biograph --region REGION
```

Compare the returned account with your recorded `EXPECTED_ACCOUNT_ID` before
creating resources.

No new IAM console user or IAM Identity Center/SSO setup is needed for the
existing Builder ID/project flow. An authorized administrator can deploy the
templates instead of delegating creation privileges; no password or shared
long-term access key is needed.

## Credit use and the separate external award

The earlier CPU-only Ohio pricing checkpoint estimated approximately **$0.75/day** for continuous
t3.small compute, one public IPv4 address and the default 46 GiB total gp3
storage, excluding S3, transfer and other usage. This is not the cost of the
deployed `t3.large` workbench and Neptune instances. Review their current costs
and applicable credit coverage separately; retained storage continues to incur
charges when compute stops.

The [Free Plan](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html)
ends at six months or when signup credits run out, whichever comes first.
A Paid Plan spend limit was not required for that CPU-only Free Plan starting
path. The current deployment uses a Paid Plan; monitor its spending and applicable
credit terms and retain recoverable evidence backups.

External challenge-credit redemption and its status are handled privately.
Free Plans are ineligible for other promotional credits; the current deployment
already uses a Paid Plan. The [redemption procedure](https://docs.aws.amazon.com/accounts/latest/reference/view-redeem-credits.html)
is AWS Settings → Billing → Current charges → available credits → Redeem credit.
Eligible credits apply across owned projects. Paid Plan [spend limits](https://docs.aws.amazon.com/accounts/latest/reference/create-spend-limit.html)
exclude credits and are separate from available credit balances.
