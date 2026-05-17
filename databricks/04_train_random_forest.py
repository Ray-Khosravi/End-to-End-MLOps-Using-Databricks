# Databricks notebook source
# MAGIC %md
# MAGIC # 04 — Train Random Forest
# MAGIC
# MAGIC Trains an sklearn RandomForestClassifier on the Gold table.
# MAGIC Logs hyperparameters, metrics, and the model artifact to MLflow.

# COMMAND ----------

dbutils.widgets.text("gold_table",       "churn_mlops.gold.customer_churn_features")
dbutils.widgets.text("experiment_path",  "/Shared/churn_mlops_experiments")

GOLD_TABLE      = dbutils.widgets.get("gold_table")
EXPERIMENT_PATH = dbutils.widgets.get("experiment_path")

# COMMAND ----------

import mlflow
import mlflow.sklearn
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (accuracy_score, precision_score,
                             recall_score, f1_score, roc_auc_score)
import pandas as pd

mlflow.set_experiment(EXPERIMENT_PATH)

# COMMAND ----------

# Load the Gold table as pandas (small dataset; Spark for bigger)
gold = spark.table(GOLD_TABLE).toPandas()

# Identify feature columns (everything except the id, label, split)
feature_cols = [c for c in gold.columns
                if c not in ("customer_id", "churn", "_split")]

train = gold[gold["_split"] == "train"]
val   = gold[gold["_split"] == "val"]
test  = gold[gold["_split"] == "test"]

X_train, y_train = train[feature_cols], train["churn"]
X_val,   y_val   = val[feature_cols],   val["churn"]
X_test,  y_test  = test[feature_cols],  test["churn"]

print(f"train={len(X_train)}  val={len(X_val)}  test={len(X_test)}")

# COMMAND ----------

# Try a small hyperparameter grid
grid = [
    {"n_estimators":  50, "max_depth": 5},
    {"n_estimators": 100, "max_depth": 8},
    {"n_estimators": 200, "max_depth": 12},
]

for params in grid:
    with mlflow.start_run(run_name=f"rf_n{params['n_estimators']}_d{params['max_depth']}") as run:
        mlflow.log_params(params)
        mlflow.set_tag("model_family", "random_forest")

        model = RandomForestClassifier(random_state=42, **params)
        model.fit(X_train, y_train)

        # Validation metrics
        preds_val = model.predict(X_val)
        probs_val = model.predict_proba(X_val)[:, 1]
        metrics = {
            "val_accuracy":  accuracy_score(y_val, preds_val),
            "val_precision": precision_score(y_val, preds_val, zero_division=0),
            "val_recall":    recall_score(y_val, preds_val, zero_division=0),
            "val_f1":        f1_score(y_val, preds_val, zero_division=0),
            "val_auc":       roc_auc_score(y_val, probs_val) if len(y_val.unique()) > 1 else 0.0,
        }
        mlflow.log_metrics(metrics)
        print(run.info.run_id, params, metrics)

        # Log the model artifact for later registration
        # `signature` auto-captures input/output schema — important!
        signature = mlflow.models.infer_signature(X_train, model.predict(X_train))
        mlflow.sklearn.log_model(
            sk_model=model,
            artifact_path="model",
            signature=signature,
            input_example=X_train.head(3),
        )

# COMMAND ----------

# Quick visual: list all RF runs from this experiment
runs = mlflow.search_runs(
    experiment_names=[EXPERIMENT_PATH],
    filter_string="tags.model_family = 'random_forest'",
    order_by=["metrics.val_f1 DESC"],
)
display(runs[["run_id", "params.n_estimators", "params.max_depth",
              "metrics.val_f1", "metrics.val_accuracy", "metrics.val_auc"]])
