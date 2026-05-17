# Databricks notebook source
# MAGIC %md
# MAGIC # 05 — Train Neural Network
# MAGIC
# MAGIC Trains a small Keras neural network on the same Gold features.
# MAGIC Logs the same MLflow metrics so we can compare against the RF baseline.

# COMMAND ----------

dbutils.widgets.text("gold_table",      "churn_mlops.gold.customer_churn_features")
dbutils.widgets.text("experiment_path", "/Shared/churn_mlops_experiments")

GOLD_TABLE      = dbutils.widgets.get("gold_table")
EXPERIMENT_PATH = dbutils.widgets.get("experiment_path")

# COMMAND ----------

import mlflow
import mlflow.keras
import numpy as np
import pandas as pd
from sklearn.metrics import (accuracy_score, precision_score,
                             recall_score, f1_score, roc_auc_score)
from sklearn.preprocessing import StandardScaler

import tensorflow as tf
from tensorflow import keras
from tensorflow.keras import layers

mlflow.set_experiment(EXPERIMENT_PATH)

# COMMAND ----------

gold = spark.table(GOLD_TABLE).toPandas()
feature_cols = [c for c in gold.columns
                if c not in ("customer_id", "churn", "_split")]

train = gold[gold["_split"] == "train"]
val   = gold[gold["_split"] == "val"]
test  = gold[gold["_split"] == "test"]

# Scaling matters for NNs (not for RF)
scaler = StandardScaler()
X_train = scaler.fit_transform(train[feature_cols])
X_val   = scaler.transform(val[feature_cols])
X_test  = scaler.transform(test[feature_cols])
y_train = train["churn"].values
y_val   = val["churn"].values
y_test  = test["churn"].values

INPUT_DIM = X_train.shape[1]

# COMMAND ----------

def build_model(hidden_units: int, dropout: float) -> keras.Model:
    """Small dense classifier with one hidden layer."""
    model = keras.Sequential([
        layers.Input(shape=(INPUT_DIM,)),
        layers.Dense(hidden_units, activation="relu"),
        layers.Dropout(dropout),
        layers.Dense(1, activation="sigmoid"),
    ])
    model.compile(
        optimizer="adam",
        loss="binary_crossentropy",
        metrics=[keras.metrics.AUC(name="auc"), "accuracy"],
    )
    return model


# COMMAND ----------

grid = [
    {"hidden_units": 32,  "dropout": 0.2, "epochs": 30, "batch_size": 8},
    {"hidden_units": 64,  "dropout": 0.3, "epochs": 50, "batch_size": 8},
    {"hidden_units": 128, "dropout": 0.4, "epochs": 50, "batch_size": 8},
]

for params in grid:
    with mlflow.start_run(run_name=f"nn_h{params['hidden_units']}_d{params['dropout']}") as run:
        mlflow.log_params(params)
        mlflow.set_tag("model_family", "neural_network")

        model = build_model(params["hidden_units"], params["dropout"])
        history = model.fit(
            X_train, y_train,
            validation_data=(X_val, y_val),
            epochs=params["epochs"],
            batch_size=params["batch_size"],
            verbose=0,
        )

        # Eval on validation set
        probs_val = model.predict(X_val, verbose=0).flatten()
        preds_val = (probs_val > 0.5).astype(int)
        metrics = {
            "val_accuracy":  accuracy_score(y_val, preds_val),
            "val_precision": precision_score(y_val, preds_val, zero_division=0),
            "val_recall":    recall_score(y_val, preds_val, zero_division=0),
            "val_f1":        f1_score(y_val, preds_val, zero_division=0),
            "val_auc":       roc_auc_score(y_val, probs_val) if len(set(y_val)) > 1 else 0.0,
        }
        mlflow.log_metrics(metrics)
        print(run.info.run_id, params, metrics)

        # NOTE: we log the *combined* model + scaler as a pyfunc so the backend
        # doesn't need to re-derive the scaler at serving time.
        import joblib, os, tempfile
        tmpdir = tempfile.mkdtemp()
        joblib.dump(scaler, os.path.join(tmpdir, "scaler.pkl"))
        model.save(os.path.join(tmpdir, "keras_model.keras"))

        class ChurnNNModel(mlflow.pyfunc.PythonModel):
            def load_context(self, context):
                import joblib, tensorflow as tf
                self.scaler = joblib.load(context.artifacts["scaler"])
                self.model  = tf.keras.models.load_model(context.artifacts["keras_model"])
            def predict(self, context, model_input, params=None):
                X = self.scaler.transform(model_input)
                return (self.model.predict(X, verbose=0).flatten() > 0.5).astype(int)

        signature = mlflow.models.infer_signature(
            pd.DataFrame(train[feature_cols].head(3)),
            np.array([0, 1, 0]),
        )
        mlflow.pyfunc.log_model(
            artifact_path="model",
            python_model=ChurnNNModel(),
            artifacts={
                "scaler":      os.path.join(tmpdir, "scaler.pkl"),
                "keras_model": os.path.join(tmpdir, "keras_model.keras"),
            },
            signature=signature,
            input_example=train[feature_cols].head(3),
            pip_requirements=[
                "tensorflow>=2.15.0", "scikit-learn>=1.3.0",
                "joblib>=1.3.0", "pandas>=2.0.0",
            ],
        )

# COMMAND ----------

# Compare all runs (RF + NN) — best F1 wins
runs = mlflow.search_runs(
    experiment_names=[EXPERIMENT_PATH],
    order_by=["metrics.val_f1 DESC"],
)
display(runs[["run_id", "tags.model_family", "metrics.val_f1",
              "metrics.val_accuracy", "metrics.val_auc"]].head(10))
