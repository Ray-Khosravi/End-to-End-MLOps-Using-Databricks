# Databricks notebook source
# MAGIC %md
# MAGIC # 00 — Unity Catalog Setup
# MAGIC
# MAGIC Run this **once** after creating the workspace + metastore.
# MAGIC It creates the catalog and schemas for the entire pipeline.
# MAGIC
# MAGIC Prereqs:
# MAGIC - Unity Catalog metastore is assigned to this workspace
# MAGIC - Your user has `CREATE CATALOG` on the metastore (or the workspace admin runs this)

# COMMAND ----------

# MAGIC %sql
# MAGIC -- Catalog: the top-level container
# MAGIC CREATE CATALOG IF NOT EXISTS churn_mlops
# MAGIC   COMMENT 'Customer churn MLOps tutorial — medallion + MLflow';
# MAGIC
# MAGIC USE CATALOG churn_mlops;
# MAGIC
# MAGIC -- Schemas (databases) for each medallion layer
# MAGIC CREATE SCHEMA IF NOT EXISTS bronze COMMENT 'Raw, append-only';
# MAGIC CREATE SCHEMA IF NOT EXISTS silver COMMENT 'Cleaned, validated';
# MAGIC CREATE SCHEMA IF NOT EXISTS gold   COMMENT 'ML-ready feature tables';
# MAGIC CREATE SCHEMA IF NOT EXISTS models COMMENT 'Registered MLflow models';
# MAGIC
# MAGIC SHOW SCHEMAS IN churn_mlops;

# COMMAND ----------

# MAGIC %md
# MAGIC ## External Location Sanity Check
# MAGIC
# MAGIC If you set up the storage credential + external location in Phase 2.4,
# MAGIC this cell should list your raw CSV file.

# COMMAND ----------

# Replace the suffix with yours, OR set this widget at the top of the notebook
dbutils.widgets.text("raw_bucket", "mlops-churn-raw-CHANGEME",
                     "Raw S3 bucket name")
RAW_BUCKET = dbutils.widgets.get("raw_bucket")
print(f"Listing s3://{RAW_BUCKET}/landing/")
display(dbutils.fs.ls(f"s3://{RAW_BUCKET}/landing/"))

# COMMAND ----------

# MAGIC %md
# MAGIC If the above fails with `AccessDenied`, your external location isn't
# MAGIC configured correctly. Re-check Phase 2.4 in `docs/02-databricks-setup.md`.
