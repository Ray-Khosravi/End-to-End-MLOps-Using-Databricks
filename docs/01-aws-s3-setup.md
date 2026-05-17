# Phase 1 — AWS Account & S3 Setup

> **Goal:** Get an AWS account ready, create the S3 buckets, and configure local AWS CLI access.

---

## 1.1 Create an AWS Account

If you already have one, skip ahead. Otherwise:

1. Sign up at https://aws.amazon.com/ — you'll need a credit card.
2. AWS gives you a **Free Tier** for the first 12 months, but **EKS itself is not free** (~$0.10/hour for the control plane alone). Budget ~$5–10/day while resources are running.
3. **Enable MFA** on the root account immediately. Never use root credentials for anything else.

---

## 1.2 Create an IAM Admin User

The root account should never be used for day-to-day work. Create an IAM user instead:

1. Open the IAM console → **Users** → **Create user**.
2. Name: `mlops-admin`.
3. Attach the AWS-managed policy `AdministratorAccess` (for the tutorial; tighten later).
4. After creation, open the user → **Security credentials** tab → **Create access key**.
5. Save the **Access Key ID** and **Secret Access Key** somewhere safe (e.g. a password manager).

---

## 1.3 Configure the AWS CLI Locally

```bash
aws configure
# AWS Access Key ID:        <paste yours>
# AWS Secret Access Key:    <paste yours>
# Default region name:      us-east-1
# Default output format:    json
```

Verify:
```bash
aws sts get-caller-identity
# {
#   "UserId":  "AIDA...",
#   "Account": "123456789012",
#   "Arn":     "arn:aws:iam::123456789012:user/mlops-admin"
# }
```

---

## 1.4 Pick a Suffix for Resource Names

S3 bucket names must be **globally unique**. Pick a short suffix (your initials + a number) and stick with it.

```bash
export SUFFIX="<your-initials>-$RANDOM"     # e.g. ar-12345
echo $SUFFIX
```

(Save this somewhere — you'll reuse it.)

---

## 1.5 Create the S3 Buckets

Two buckets:

| Bucket | Purpose |
|---|---|
| `mlops-churn-raw-<suffix>` | Holds the raw customer data |
| `mlops-tfstate-<suffix>` | Holds Terraform state (with versioning) |

```bash
REGION=us-east-1

# Bucket 1: raw data
aws s3api create-bucket \
    --bucket "mlops-churn-raw-${SUFFIX}" \
    --region "$REGION"

# Bucket 2: terraform state, with versioning + encryption
aws s3api create-bucket \
    --bucket "mlops-tfstate-${SUFFIX}" \
    --region "$REGION"

aws s3api put-bucket-versioning \
    --bucket "mlops-tfstate-${SUFFIX}" \
    --versioning-configuration Status=Enabled

aws s3api put-bucket-encryption \
    --bucket "mlops-tfstate-${SUFFIX}" \
    --server-side-encryption-configuration '{
      "Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]
    }'
```

> **Note for non-`us-east-1` regions:** add `--create-bucket-configuration LocationConstraint=<your-region>`.

---

## 1.6 Block Public Access (Important)

```bash
aws s3api put-public-access-block \
    --bucket "mlops-churn-raw-${SUFFIX}" \
    --public-access-block-configuration \
       "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"

# Same for tfstate bucket
aws s3api put-public-access-block \
    --bucket "mlops-tfstate-${SUFFIX}" \
    --public-access-block-configuration \
       "BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true"
```

---

## 1.7 Upload the Sample Data

```bash
aws s3 cp sample_data/customer_churn_raw.csv \
    "s3://mlops-churn-raw-${SUFFIX}/landing/customer_churn_raw.csv"

# Verify
aws s3 ls "s3://mlops-churn-raw-${SUFFIX}/landing/"
```

Folder convention we'll use:
```
mlops-churn-raw-<suffix>/
├── landing/             ← raw drops from upstream
└── _checkpoints/        ← Databricks Auto Loader state (created automatically)
```

---

## 1.8 Create a DynamoDB Table for Terraform State Locking

Without locking, two `terraform apply` runs in parallel can corrupt state. DynamoDB gives Terraform a cheap, reliable lock:

```bash
aws dynamodb create-table \
    --table-name mlops-tflock \
    --attribute-definitions AttributeName=LockID,AttributeType=S \
    --key-schema           AttributeName=LockID,KeyType=HASH \
    --billing-mode         PAY_PER_REQUEST \
    --region "$REGION"
```

Wait until the table is `ACTIVE`:
```bash
aws dynamodb wait table-exists --table-name mlops-tflock --region "$REGION"
```

---

## 1.9 Save Your Settings

Create a `.env` file at the repo root (we'll source it many times):

```bash
cat > .env <<EOF
export AWS_REGION=us-east-1
export SUFFIX=${SUFFIX}
export RAW_BUCKET=mlops-churn-raw-${SUFFIX}
export TFSTATE_BUCKET=mlops-tfstate-${SUFFIX}
export TFLOCK_TABLE=mlops-tflock
EOF

# Add to .gitignore!
echo ".env" >> .gitignore
```

Source it whenever you open a new shell:
```bash
source .env
```

---

## ✅ Phase 1 Checklist

- [ ] AWS account exists, MFA on root, IAM admin user created
- [ ] `aws sts get-caller-identity` returns your admin user
- [ ] Raw bucket exists and contains `landing/customer_churn_raw.csv`
- [ ] tfstate bucket exists with versioning + encryption
- [ ] DynamoDB lock table exists
- [ ] `.env` file saved + git-ignored

**Next:** [`02-databricks-setup.md`](02-databricks-setup.md) →
