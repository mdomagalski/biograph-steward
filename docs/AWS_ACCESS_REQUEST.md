# AWS Free Plan deployment setup

Updated 2026-11-11. The selected deployment target is the user's **owned**
project in **us-east-2**. The previously inspected shared project is excluded.
The `biograph` CLI profile is authenticated and STS verified the target account.
Keep account identifiers and private receipts in local deployment records.

The current path uses the **Free Plan and signup credits** (for example, $100
for an eligible new account). A Paid Plan
upgrade or external challenge-credit redemption is not needed to start the
eligible CPU workbench. Private award details and codes are not stored here.

## What is verified and what comes next

- Read-only AWS checks verified `t3.small` as Free Tier eligible (2 vCPU,
  2 GiB RAM), an Amazon Linux 2023 x86_64 AMI marked eligible, and a public subnet
  in us-east-2a with an active internet-gateway route.
- Both templates passed AWS `validate-template` before the default was changed
  from t3.medium to **t3.small**. Revalidate the exact release before deployment.
- No deployment resources have been created. Linux bootstrap, container startup,
  memory sufficiency, SSM access, app persistence and backups remain unverified.
- Prepare the committed release, verify the owned account and remaining signup
  credit/expiration, then deploy the existing templates. The guide is
  [deploy/aws/README.md](../deploy/aws/README.md).

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

The Ohio pricing checkpoint estimates approximately **$0.75/day** for continuous
t3.small compute, one public IPv4 address and the default 46 GiB total gp3
storage, excluding S3, transfer and other usage. These costs draw on signup
credits. Stop compute when idle; retained EBS/S3 storage continues to use credit.

The [Free Plan](https://docs.aws.amazon.com/awsaccountbilling/latest/aboutv2/free-tier-plans.html)
ends at six months or when signup credits run out, whichever comes first.
A Paid Plan spend limit is not required for this path. Monitor credit balance
and account expiration and retain recoverable evidence backups.

External challenge credit remains unredeemed. Only if the user later chooses
to redeem it must the account first move to a Paid Plan, since Free Plans are
ineligible for other promotional credits. The user completes that decision and
redemption privately. The [redemption procedure](https://docs.aws.amazon.com/accounts/latest/reference/view-redeem-credits.html)
is AWS Settings → Billing → Current charges → available credits → Redeem credit.
Eligible credits apply across owned projects. Paid Plan [spend limits](https://docs.aws.amazon.com/accounts/latest/reference/create-spend-limit.html)
exclude credits and are separate from available credit balances.
