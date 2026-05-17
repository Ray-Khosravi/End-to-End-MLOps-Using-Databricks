# Phase 2 — Databricks Workspace + Unity Catalog

> **Goal:** Stand up a Databricks workspace that can read from your S3 bucket, with Unity Catalog enabled and a clean catalog/schema structure ready for the medallion pipeline.

---

## 2.1 Choose a Plan

| Plan | Cost | Unity Catalog? |
|---|---|---|
| Free trial | $0 for 14 days | ✅ (limited) |
| Standard | $$ | ❌ (no UC) |
| **Premium** | $$$ | ✅ |

**For this tutorial, use the 14-day free trial or Premium.** Unity Catalog is what makes governance possible.

Sign up:
- Direct: https://www.databricks.com/try-databricks
- Or **AWS Marketplace**: https://aws.amazon.com/marketplace/pp/prodview-wbjirxnasoznm (provisions through your AWS account)

---

## 2.2 Create the Workspace

When the Account Console asks for placement details:

| Setting | Value |
|---|---|
| Workspace name | `mlops-tutorial` |
| Region | **Same as your S3 bucket** (e.g. `us-east-1`) |
| Pricing tier | **Premium** (for Unity Catalog) |
| Network | Default (Databricks-managed VPC is fine for the tutorial) |

Wait ~10 minutes for provisioning. The Account Console will show a URL like `https://dbc-xxxxxxx.cloud.databricks.com`.

---

## 2.3 Enable Unity Catalog

Unity Catalog requires a one-time metastore setup *per region*.

### Step 1: Create the metastore storage bucket

This is a *different* S3 bucket from your raw-data bucket — it's where Unity Catalog stores managed tables.

```bash
source .env

aws s3api create-bucket \
    --bucket "uc-metastore-${SUFFIX}" \
    --region "$AWS_REGION"
```

### Step 2: Create the metastore in the Account Console

1. Open https://accounts.cloud.databricks.com/ (account-level, not workspace).
2. Go to **Catalog** → **Create metastore**.
3. Fill in:
   - **Name:** `metastore-us-east-1`
   - **Region:** `us-east-1`
   - **S3 bucket path:** `s3://uc-metastore-<suffix>/`
   - **IAM role ARN:** *(you'll create this in 2.4)*
4. Click **Create**, then assign it to your workspace.

### Step 3: Create the IAM role for Unity Catalog

Unity Catalog needs an IAM role it can assume to read/write its bucket. The exact policy + trust JSON are in the Databricks docs and the role ARN goes into the metastore creation form.

→ Follow: https://docs.databricks.com/aws/en/data-governance/unity-catalog/get-started

(Detailed step-by-step is long; the doc above is authoritative.)

---

## 2.4 Grant Databricks Access to Your Raw S3 Bucket

For Databricks to read `s3://mlops-churn-raw-${SUFFIX}/landing/`, you need an **external location** in Unity Catalog. That requires a **storage credential** (an IAM role) plus an **external location** pointing at the bucket.

### Step 1: Create the storage-credential IAM role

```bash
source .env
ACCOUNT_ID=$(aws sts get-caller-identity --query Account --output text)

# Trust policy: allows Databricks's UC role to assume this role
cat > trust.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": { "AWS": "arn:aws:iam::414351767826:role/unity-catalog-prod-UCMasterRole-14S5ZJVKOTYTL" },
    "Action": "sts:AssumeRole",
    "Condition": { "StringEquals": { "sts:ExternalId": "<your-databricks-account-id>" } }
  }]
}
EOF

aws iam create-role --role-name dbx-uc-raw-access --assume-role-policy-document file://trust.json
```

(`414351767826` is the fixed Databricks UC account in `us-east-1` — verify on https://docs.databricks.com.)

### Step 2: Inline policy granting S3 access

```bash
cat > policy.json <<EOF
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Action": ["s3:GetObject","s3:PutObject","s3:DeleteObject","s3:ListBucket","s3:GetBucketLocation"],
    "Resource": [
      "arn:aws:s3:::${RAW_BUCKET}",
      "arn:aws:s3:::${RAW_BUCKET}/*"
    ]
  }]
}
EOF

aws iam put-role-policy --role-name dbx-uc-raw-access \
    --policy-name s3-raw --policy-document file://policy.json
```

### Step 3: Register in Databricks

In the Databricks **Catalog Explorer**:

1. **Storage Credentials** → **Create credential**
   - Name: `dbx-uc-raw-cred`
   - IAM role ARN: `arn:aws:iam::<account>:role/dbx-uc-raw-access`
2. **External Locations** → **Create location**
   - Name: `raw-data`
   - URL: `s3://mlops-churn-raw-<suffix>/`
   - Credential: `dbx-uc-raw-cred`
3. Test the connection — should say "Test connection succeeded."

---

## 2.5 Create the Catalog Hierarchy

Open a Databricks SQL editor (or notebook), and run:

```sql
-- ──────────────────────────────────────────────────────────
-- One catalog per project; one schema per medallion layer
-- ──────────────────────────────────────────────────────────
CREATE CATALOG IF NOT EXISTS churn_mlops
  COMMENT 'Customer churn MLOps tutorial';

USE CATALOG churn_mlops;

CREATE SCHEMA IF NOT EXISTS bronze COMMENT 'Raw, append-only';
CREATE SCHEMA IF NOT EXISTS silver COMMENT 'Cleaned, validated';
CREATE SCHEMA IF NOT EXISTS gold   COMMENT 'ML-ready features';
CREATE SCHEMA IF NOT EXISTS models COMMENT 'Registered models';

-- Quick sanity check
SHOW SCHEMAS IN churn_mlops;
```

Final structure:
```
churn_mlops (catalog)
├── bronze   (schema) — raw ingestion lands here
├── silver   (schema) — cleaned tables
├── gold     (schema) — features + training table
└── models   (schema) — registered MLflow models
```

---

## 2.6 Set Up a Compute Cluster

For the notebooks in the next phases, create a cluster:

- **Cluster mode:** Single node (for the tutorial) or small autoscaling 1-2 nodes
- **Databricks Runtime version:** `15.4 LTS ML` (includes MLflow + ML libs)
- **Node type:** `i3.xlarge` or `m5d.large` (cheap-ish)
- **Auto-terminate:** 20 minutes (saves money when you walk away)
- **Access mode:** **Shared** with Unity Catalog enabled
  - ⚠️ Single-user mode also works but loses some UC features

Click **Create cluster** and wait ~3 minutes for it to be `Running`.

---

## 2.7 Connect Your Local Environment (Optional)

If you want to develop notebooks locally and push to Databricks:

```bash
pip install databricks-cli
databricks configure --token
# Host:  https://dbc-xxxxx.cloud.databricks.com
# Token: <create in User Settings → Access tokens>
```

Then you can sync the `databricks/` folder:
```bash
databricks workspace import_dir databricks/ /Workspace/Users/<you>/mlops-tutorial/ --overwrite
```

---

## ✅ Phase 2 Checklist

- [ ] Databricks workspace created in the same region as S3
- [ ] Unity Catalog metastore created and assigned to workspace
- [ ] IAM role for UC raw-bucket access created
- [ ] Storage credential + external location point at `s3://mlops-churn-raw-<suffix>/`
- [ ] Catalog `churn_mlops` with schemas `bronze`, `silver`, `gold`, `models`
- [ ] A 15.4 ML cluster is running and Unity-Catalog-enabled
- [ ] (Optional) Databricks CLI configured locally

**Next:** [`03-medallion-architecture.md`](03-medallion-architecture.md) →
