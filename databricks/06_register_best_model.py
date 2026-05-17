# Databricks notebook source
# MAGIC %md
# MAGIC # 06 — Register the Best Model in Unity Catalog
# MAGIC
# MAGIC 1. Searches all runs in the experiment.
# MAGIC 2. Picks the run with the highest `val_f1`.
# MAGIC 3. Registers it as `churn_mlops.models.churn_classifier`.
# MAGIC 4. Sets the alias `@production` on the new version.
# MAGIC
# MAGIC The serving backend later loads:
# MAGIC   `models:/churn_mlops.models.churn_classifier@production`

# COMMAND ----------

dbutils.widgets.text("experiment_path",  "/Shared/churn_mlops_experiments")
dbutils.widgets.text("registered_name",  "churn_mlops.models.churn_classifier")
dbutils.widgets.text("alias",            "production")

EXPERIMENT_PATH = dbutils.widgets.get("experiment_path")
REGISTERED_NAME = dbutils.widgets.get("registered_name")
ALIAS           = dbutils.widgets.get("alias")

# COMMAND ----------

import mlflow
from mlflow.tracking import MlflowClient

# Unity Catalog mode for model registry
mlflow.set_registry_uri("databricks-uc")

# COMMAND ----------

# Find the best run by val_f1
runs = mlflow.search_runs(
    experiment_names=[EXPERIMENT_PATH],
    order_by=["metrics.val_f1 DESC"],
    max_results=1,
)
assert len(runs) > 0, f"No runs found in experiment {EXPERIMENT_PATH}"
best = runs.iloc[0]

print(f"🏆 Winner: run_id = {best['run_id']}")
print(f"   family  : {best.get('tags.model_family')}")
print(f"   val_f1  : {best['metrics.val_f1']:.4f}")
print(f"   val_acc : {best['metrics.val_accuracy']:.4f}")
print(f"   val_auc : {best['metrics.val_auc']:.4f}")

# COMMAND ----------

# Register the model
model_uri = f"runs:/{best['run_id']}/model"
print(f"Registering: {model_uri}  →  {REGISTERED_NAME}")

new_version = mlflow.register_model(
    model_uri=model_uri,
    name=REGISTERED_NAME,
    tags={
        "winning_family": best.get("tags.model_family", "unknown"),
        "val_f1":         f"{best['metrics.val_f1']:.4f}",
        "registered_by":  "06_register_best_model",
    },
)
print(f"Registered as version {new_version.version}")

# COMMAND ----------

# Set the @production alias on the new version
# (In UC, ALIASES replace the legacy stage system.)
client = MlflowClient()
client.set_registered_model_alias(
    name=REGISTERED_NAME,
    alias=ALIAS,
    version=new_version.version,
)
print(f"✅ Alias @{ALIAS} now points to version {new_version.version}")
print(f"   Model URI for serving:  models:/{REGISTERED_NAME}@{ALIAS}")

# COMMAND ----------

# Smoke test: load the model back and run a prediction
loaded = mlflow.pyfunc.load_model(f"models:/{REGISTERED_NAME}@{ALIAS}")
print("Model signature:")
print(loaded.metadata.signature)
