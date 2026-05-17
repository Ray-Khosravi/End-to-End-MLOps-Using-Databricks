# Databricks notebook source
# MAGIC %md
# MAGIC # 01 — Bronze Ingestion (Auto Loader)
# MAGIC
# MAGIC Reads new CSV files from `s3://<raw-bucket>/landing/` and appends them to
# MAGIC the Bronze Delta table. Auto Loader tracks which files have been seen.
# MAGIC
# MAGIC **Principles followed:**
# MAGIC 1. Read everything as `string` to avoid schema drift
# MAGIC 2. Add audit columns (`_ingest_ts`, `_source_file`, `_corrupt_record`)
# MAGIC 3. Append-only — never modify Bronze in place

# COMMAND ----------

dbutils.widgets.text("raw_bucket",     "mlops-churn-raw-CHANGEME", "Raw S3 bucket")
dbutils.widgets.text("checkpoint_path","s3://mlops-churn-raw-CHANGEME/_checkpoints/bronze",
                     "Auto Loader checkpoint path")
dbutils.widgets.text("target_table",   "churn_mlops.bronze.customer_churn_raw",
                     "Target Bronze table (3-level UC name)")

RAW_BUCKET       = dbutils.widgets.get("raw_bucket")
CHECKPOINT_PATH  = dbutils.widgets.get("checkpoint_path")
TARGET_TABLE     = dbutils.widgets.get("target_table")
LANDING_PATH     = f"s3://{RAW_BUCKET}/landing/"

print(f"Ingesting from:  {LANDING_PATH}")
print(f"Checkpoint at:   {CHECKPOINT_PATH}")
print(f"Target table:    {TARGET_TABLE}")

# COMMAND ----------

from pyspark.sql.functions import current_timestamp, input_file_name

# Auto Loader: incrementally process new files
bronze_stream = (
    spark.readStream
        .format("cloudFiles")
        .option("cloudFiles.format", "csv")
        .option("cloudFiles.schemaLocation", f"{CHECKPOINT_PATH}/schema")
        .option("cloudFiles.inferColumnTypes", "false")     # all strings
        .option("header", "true")
        .option("mode",   "PERMISSIVE")                     # bad rows → _corrupt_record
        .option("columnNameOfCorruptRecord", "_corrupt_record")
        .option("rescuedDataColumn", "_rescued_data")       # safety net
        .load(LANDING_PATH)
        .withColumn("_ingest_ts",   current_timestamp())
        .withColumn("_source_file", input_file_name())
)

# COMMAND ----------

# Write to Delta, append-only. `trigger(availableNow=True)` runs once until
# all current files are processed, then stops — perfect for scheduled jobs.
(
    bronze_stream.writeStream
        .format("delta")
        .option("checkpointLocation", f"{CHECKPOINT_PATH}/_checkpoint")
        .option("mergeSchema", "true")
        .outputMode("append")
        .trigger(availableNow=True)
        .toTable(TARGET_TABLE)
)

# COMMAND ----------

# MAGIC %md
# MAGIC ## Verify

# COMMAND ----------

display(spark.sql(f"""
SELECT
    COUNT(*)                AS total_rows,
    COUNT(_corrupt_record)  AS corrupt_rows,
    MAX(_ingest_ts)         AS latest_ingest,
    COUNT(DISTINCT _source_file) AS source_files
FROM {TARGET_TABLE}
"""))

# COMMAND ----------

display(spark.table(TARGET_TABLE).limit(10))
