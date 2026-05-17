# Databricks notebook source
# MAGIC %md
# MAGIC # 03 — Gold: Feature Engineering
# MAGIC
# MAGIC Produces the ML-ready table that the training notebooks will consume.
# MAGIC
# MAGIC Steps:
# MAGIC 1. One-hot encode categoricals
# MAGIC 2. Engineer derived features (avg_charge_per_month, etc.)
# MAGIC 3. Add `_split` column (train/test/val = 80/10/10)
# MAGIC 4. Write to `gold.customer_churn_features`

# COMMAND ----------

dbutils.widgets.text("silver_table", "churn_mlops.silver.customer_churn")
dbutils.widgets.text("gold_table",   "churn_mlops.gold.customer_churn_features")

SILVER_TABLE = dbutils.widgets.get("silver_table")
GOLD_TABLE   = dbutils.widgets.get("gold_table")

# COMMAND ----------

from pyspark.sql.functions import col, when, rand, lit

silver = spark.table(SILVER_TABLE)
print(f"Silver rows: {silver.count()}")

# COMMAND ----------

# ─── 1. Engineered features ──────────────────────────────────────────────
features = (
    silver
    .withColumn(
        "avg_charge_per_month",
        when(col("tenure_months") > 0, col("total_charges") / col("tenure_months"))
        .otherwise(col("monthly_charges"))
    )
    .withColumn("is_long_tenure",   (col("tenure_months") >= 24).cast("int"))
    .withColumn("is_high_spender",  (col("monthly_charges") >= 75).cast("int"))
)

# ─── 2. Binary encodings (yes/no → 1/0) ──────────────────────────────────
binary_cols = ["partner", "dependents", "phone_service", "paperless_billing"]
for c in binary_cols:
    features = features.withColumn(c, (col(c) == "yes").cast("int"))

features = features.withColumn("gender_male", (col("gender") == "male").cast("int")).drop("gender")

# ─── 3. One-hot encode multi-class categoricals ──────────────────────────
def one_hot(df, col_name, values):
    for v in values:
        flag = f"{col_name}_{v.replace(' ', '_').replace('-', '_')}"
        df = df.withColumn(flag, (col(col_name) == v).cast("int"))
    return df.drop(col_name)

features = one_hot(features, "internet_service", ["dsl", "fiber optic", "no"])
features = one_hot(features, "contract_type",    ["month-to-month", "one year", "two year"])
features = one_hot(features, "payment_method",
                   ["electronic check", "mailed check", "bank transfer", "credit card"])

# ─── 4. Drop columns we don't need for training ──────────────────────────
features = features.drop("_ingest_ts", "_source_file")

# COMMAND ----------

# ─── 5. Train/test/val split via deterministic hash ──────────────────────
# Using rand() with a fixed seed gives reproducible splits as data grows.
from pyspark.sql.functions import abs as f_abs, hash as f_hash

features_split = features.withColumn(
    "_split",
    when((f_abs(f_hash("customer_id")) % 10) < 8, lit("train"))
    .when((f_abs(f_hash("customer_id")) % 10) == 8, lit("val"))
    .otherwise(lit("test"))
)

display(features_split.groupBy("_split").count())

# COMMAND ----------

# ─── 6. Write Gold ───────────────────────────────────────────────────────
(features_split
    .write.format("delta")
    .mode("overwrite")
    .option("overwriteSchema", "true")
    .saveAsTable(GOLD_TABLE))

# COMMAND ----------

# Sanity check the final schema
spark.table(GOLD_TABLE).printSchema()
display(spark.table(GOLD_TABLE).limit(5))
