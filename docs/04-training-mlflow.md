# Phase 4 — Model Training with MLflow

> **Goal:** Train two models on the Gold table, track every run with MLflow, pick the winner, and register it to Unity Catalog so the serving layer can load it by name.

---

## 4.1 Why MLflow

MLflow gives us:
- **Tracking:** every hyperparameter, metric, and artifact for every run is logged automatically.
- **Comparison:** the UI lets you sort/filter dozens of runs by F1, accuracy, etc.
- **Registry:** the chosen model is registered with a name + version, and the backend loads it by `models:/churn_mlops.gold.churn_classifier@production`.

In Databricks, MLflow is **already installed and configured** — `mlflow.set_experiment(...)` just works.

---

## 4.2 Choose Compute

For these small training jobs (~20 sample rows in the tutorial; with real data this would be 100k+), you don't need a GPU. A single-node `i3.xlarge` or `m5d.large` cluster on Databricks Runtime **15.4 LTS ML** is plenty.

For real production training jobs:
- **CPU**: `i3.2xlarge` or larger for RF on tabular data
- **GPU**: `g4dn.xlarge` (T4) or `g5.xlarge` (A10) for neural networks at scale

---

## 4.3 The Three Training Notebooks

| Notebook | What |
|---|---|
| `04_train_random_forest.py` | Trains an sklearn `RandomForestClassifier`, logs to MLflow |
| `05_train_neural_network.py` | Trains a small Keras NN, logs to MLflow |
| `06_register_best_model.py` | Compares all runs in the experiment, registers the winner |

**Common pattern in each:**

```python
import mlflow
mlflow.set_experiment("/Users/<you>/churn_mlops")

with mlflow.start_run(run_name="rf_v1") as run:
    mlflow.log_params({"n_estimators": 200, ...})

    # ... train ...

    mlflow.log_metrics({"f1": 0.78, "accuracy": 0.85, ...})
    mlflow.sklearn.log_model(model, artifact_path="model",
                             registered_model_name=None)  # we'll register later
```

---

## 4.4 Running the Sweep

In Databricks:
1. Open `databricks/04_train_random_forest.py` → **Run All**.
2. Open `databricks/05_train_neural_network.py` → **Run All**.
3. Open the **Experiments** sidebar → click on the experiment → see the runs sorted by metric.

In the MLflow UI you'll see:

```
runs/
├── rf_n50    accuracy=0.81  f1=0.74
├── rf_n100   accuracy=0.85  f1=0.78  ◀ winner so far
├── rf_n200   accuracy=0.84  f1=0.77
├── nn_v1     accuracy=0.83  f1=0.75
└── nn_v2     accuracy=0.85  f1=0.79  ◀ new winner!
```

---

## 4.5 Register the Winner in Unity Catalog

`06_register_best_model.py` does this programmatically:

1. Query the MLflow tracking API for all runs in the experiment.
2. Sort by `metrics.f1` descending.
3. Take the top run.
4. Call `mlflow.register_model(model_uri, name="churn_mlops.models.churn_classifier")`.
5. Set its **alias** to `production` (UC uses aliases, not stages).

```python
client = MlflowClient()
client.set_registered_model_alias(
    name="churn_mlops.models.churn_classifier",
    alias="production",
    version=new_version.version,
)
```

The serving backend will load `models:/churn_mlops.models.churn_classifier@production` — completely decoupled from any specific version number.

---

## 4.6 What the Backend Will Use

The backend (Phase 5) calls:

```python
import mlflow
model = mlflow.pyfunc.load_model("models:/churn_mlops.models.churn_classifier@production")
prediction = model.predict(input_df)
```

When you register a new version and re-tag it `@production`, the backend's next `mlflow.pyfunc.load_model` call gets the new model — no code change.

---

## 4.7 Where to Get the Service Principal Token

The backend running in EKS needs to **authenticate to Databricks** to download the model. Two options:

| Option | Pros | Cons |
|---|---|---|
| **Service Principal + OAuth M2M** (recommended) | No expiring PATs, audited, revocable | More setup |
| Personal Access Token (PAT) | Trivial to create | Tied to one user, expires |

For the tutorial:
1. **Account console** → **Service principals** → **Add**.
2. Generate **OAuth secret** for it.
3. Grant it `USE CATALOG` on `churn_mlops` + `READ` on `churn_mlops.models.churn_classifier`.
4. Store the client ID + secret in **AWS Secrets Manager**; the backend reads them at startup via IRSA.

We'll wire this into the Helm/k8s manifests in Phase 9.

---

## ✅ Phase 4 Checklist

- [ ] RF notebook produces ≥1 run in the experiment
- [ ] NN notebook produces ≥1 run in the experiment
- [ ] You can compare them in the MLflow UI
- [ ] Best run is registered as `churn_mlops.models.churn_classifier`, alias `@production`
- [ ] You have a Databricks service principal + OAuth credentials saved in AWS Secrets Manager (for Phase 9)

**Next:** [`05-backend-fastapi.md`](05-backend-fastapi.md) →
