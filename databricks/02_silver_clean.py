# Databricks notebook source
# MAGIC %md
# MAGIC # 02 — Silver: Clean & Validate
# MAGIC
# MAGIC Reads from Bronze, applies:
# MAGIC - Type casting
# MAGIC - Deduplication on `customer_id`
# MAGIC - Null checks on required columns
# MAGIC - Quarantine of bad rows
# MAGIC
# MAGIC Writes a *typed*, *validated* Silver table.

# COMMAND ----------

dbutils.widgets.text("bronze_table",     "churn_mlops.bronze.customer_churn_raw")
dbutils.widgets.text("silver_table",     "churn_mlops.silver.customer_churn")
dbutils.widgets.text("quarantine_table", "churn_mlops.silver.customer_churn_quarantine")

BRONZE_TABLE     = dbutils.widgets.get("bronze_table")
SILVER_TABLE     = dbutils.widgets.get("silver_table")
QUARANTINE_TABLE = dbutils.widgets.get("quarantine_table")

# COMMAND ----------

from pyspark.sql.functions import col, when, trim, lower, current_timestamp

# 1. Read the latest Bronze data
bronze = spark.table(BRONZE_TABLE)
print(f"Bronze rows: {bronze.count()}")

# COMMAND ----------

# 2. Identify corrupt or invalid rows
corrupt_cond = (
    col("_corrupt_record").isNotNull()
    | col("customer_id").isNull()
    | (trim(col("customer_id")) == "")
)
quarantine = bronze.filter(corrupt_cond).withColumn("_quarantined_at", current_timestamp())
print(f"Quarantined rows: {quarantine.count()}")

# 3. Filter to clean rows
clean = bronze.filter(~corrupt_cond)

# COMMAND ----------

# 4. Type-cast and normalize
silver = (
    clean
    .withColumn("customer_id",       trim(col("customer_id")))
    .withColumn("gender",             lower(trim(col("gender"))))
    .withColumn("senior_citizen",    col("senior_citizen").cast("int"))
    .withColumn("partner",            lower(trim(col("partner"))))
    .withColumn("dependents",         lower(trim(col("dependents"))))
    .withColumn("tenure_months",      col("tenure_months").cast("int"))
    .withColumn("phone_service",      lower(trim(col("phone_service"))))
    .withColumn("internet_service",   lower(trim(col("internet_service"))))
    .withColumn("contract_type",      lower(trim(col("contract_type"))))
    .withColumn("paperless_billing",  lower(trim(col("paperless_billing"))))
    .withColumn("payment_method",     lower(trim(col("payment_method"))))
    .withColumn("monthly_charges",    col("monthly_charges").cast("double"))
    .withColumn("total_charges",      col("total_charges").cast("double"))
    .withColumn("churn",              when(lower(trim(col("churn"))) == "yes", 1).otherwise(0))
)

# 5. Deduplicate — keep the most recent ingest per customer
from pyspark.sql.window import Window
from pyspark.sql.functions import row_number

w = Window.partitionBy("customer_id").orderBy(col("_ingest_ts").desc())
silver_dedup = (
    silver
    .withColumn("_rn", row_number().over(w))
    .filter(col("_rn") == 1)
    .drop("_rn", "_corrupt_record", "_rescued_data")
)

print(f"Silver rows (after dedup): {silver_dedup.count()}")

# COMMAND ----------

# 6. Validation gate — fail loudly if data quality drops
total_rows = silver_dedup.count()
unique_ids = silver_dedup.select("customer_id").distinct().count()

assert unique_ids == total_rows, \
    f"Duplicate customer_ids after dedup ({total_rows=}, {unique_ids=})"
assert total_rows > 0, "No clean rows survived — something is very wrong upstream."

print("✅ Validation passed.")

# COMMAND ----------

# 7. Write Silver (overwrite for simplicity in the tutorial;
#    in production use MERGE INTO for incremental updates)
(silver_dedup
    .write.format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(SILVER_TABLE))

(quarantine
    .write.format("delta")
    .mode("append")
    .option("mergeSchema", "true")
    .saveAsTable(QUARANTINE_TABLE))

# COMMAND ----------

display(spark.table(SILVER_TABLE).limit(10))
