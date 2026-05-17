# Phase 14 — Monitoring with Prometheus + Grafana

> **Goal:** Install the `kube-prometheus-stack` chart, scrape `/metrics` on the backend, and view the dashboards.

---

## 14.1 What the Stack Includes

The [`kube-prometheus-stack`](https://github.com/prometheus-community/helm-charts) Helm chart is the de-facto K8s monitoring bundle. One install gets you:

| Component | What |
|---|---|
| **Prometheus operator** | Manages Prometheus + Alertmanager via CRDs |
| **Prometheus** | Scrapes targets, stores time series |
| **Alertmanager** | Routes/silences alerts |
| **Grafana** | Dashboards + alerting UI |
| **node-exporter** | Host-level metrics (CPU, memory, disk) |
| **kube-state-metrics** | Kubernetes object state (Deployments, Pods, etc.) |

---

## 14.2 Install

```bash
helm repo add prometheus-community https://prometheus-community.github.io/helm-charts
helm repo update

helm install kps prometheus-community/kube-prometheus-stack \
   -n monitoring --create-namespace \
   -f k8s/monitoring/prometheus-values.yaml

# Wait ~3 min for everything to come up
kubectl -n monitoring get pods
```

---

## 14.3 Tell Prometheus to Scrape the Backend

Apply our ServiceMonitor:

```bash
kubectl apply -f k8s/monitoring/backend-servicemonitor.yaml
```

A ServiceMonitor is a CRD that the prometheus-operator reads to generate scrape configs. It says: *"Find all Services in namespace `churn` with label `app: backend`. Scrape their `http` port at path `/metrics` every 15 seconds."*

Verify Prometheus sees the target:

```bash
# Port-forward Prometheus UI
kubectl -n monitoring port-forward svc/kps-kube-prometheus-stack-prometheus 9090:9090

# Open http://localhost:9090/targets — you should see the backend
```

---

## 14.4 Open Grafana

```bash
kubectl -n monitoring port-forward svc/kps-grafana 3000:80

# Open http://localhost:3000
# User: admin   Password: admin (from prometheus-values.yaml)
```

In Grafana:
- **Dashboards** → built-ins for K8s/Nodes/Pods are already there.
- **Dashboards → Import** → paste `k8s/monitoring/grafana-dashboard.json` for the **Churn API** dashboard.

The Churn API dashboard shows:
- Requests/sec & error rate
- Latency p50/p95/p99
- Inference latency
- Prediction class distribution
- Pod CPU/memory

---

## 14.5 Useful PromQL Queries

```promql
# RPS by status
sum(rate(http_requests_total{namespace="churn"}[5m])) by (status)

# Error budget consumed (last 24h)
1 - (
   sum(rate(http_requests_total{namespace="churn",status!~"5.."}[24h])) /
   sum(rate(http_requests_total{namespace="churn"}[24h]))
)

# Slowest endpoint
topk(5, histogram_quantile(0.99,
    sum(rate(http_request_duration_seconds_bucket{namespace="churn"}[5m]))
    by (le, path)))

# Pod restarts in last hour (alarming!)
sum(rate(kube_pod_container_status_restarts_total{namespace="churn"}[1h]))
```

---

## 14.6 Setting Up Alerts

In Alertmanager:

```yaml
# alertmanager-config.yaml — applied as a secret named "alertmanager-kps-kube-prometheus-stack-alertmanager"
global:
  resolve_timeout: 5m

route:
  receiver: slack
  group_by: ['alertname', 'namespace']

receivers:
  - name: slack
    slack_configs:
      - api_url:  https://hooks.slack.com/services/xxx/yyy/zzz
        channel:  '#alerts'
        title:    '{{ .GroupLabels.alertname }}'
```

Example alert rule (in a `PrometheusRule` CRD):

```yaml
apiVersion: monitoring.coreos.com/v1
kind: PrometheusRule
metadata:
  name: churn-alerts
  namespace: monitoring
spec:
  groups:
    - name: churn.rules
      rules:
        - alert: HighErrorRate
          expr: |
            sum(rate(http_requests_total{namespace="churn",status=~"5.."}[5m]))
            / sum(rate(http_requests_total{namespace="churn"}[5m])) > 0.05
          for: 5m
          labels:
            severity: page
          annotations:
            summary: ">5% 5xx errors on churn API for 5+ min"
```

---

## 14.7 Exposing Grafana Externally (Optional)

Right now Grafana is port-forwarded. To expose it at `grafana.example.com`:

1. Add an Ingress in `k8s/monitoring/grafana-ingress.yaml`.
2. Add a Route 53 record (`grafana.example.com → ALB`).
3. **Lock it down** — add OAuth via Cognito, GitHub OAuth, or at minimum a strong admin password.

⚠️ Never expose Grafana with the default admin/admin to the public internet.

---

## 14.8 Cost Note

Inside the cluster, monitoring uses a few hundred MB of memory and ~10 GB EBS. Approximately **$5–8/month extra**.

For high-scale production, look at:
- **Amazon Managed Prometheus** (AMP) + **Managed Grafana** (AMG) — fully managed, pay-per-metric.
- **Mimir** — for multi-tenant Prometheus at scale.

---

## ✅ Phase 14 Checklist

- [ ] `kube-prometheus-stack` is installed and all pods are Running
- [ ] `kubectl -n monitoring get servicemonitor` shows `churn-backend`
- [ ] Prometheus `/targets` shows the backend as UP
- [ ] Grafana dashboard imported; metrics flowing in
- [ ] (Optional) Alert routes set up

---

## 🎉 You're Done!

You now have:
- A medallion data pipeline (Phases 1–3)
- Trained, registered models in MLflow (Phase 4)
- A FastAPI backend + HTML frontend (Phases 5–7)
- VPC, EKS, ALB, Route 53, all in Terraform (Phases 8–10)
- CI/CD via GitHub Actions + ArgoCD (Phases 11–12)
- Code quality gates via SonarQube (Phase 13)
- Full Prometheus + Grafana monitoring (Phase 14)

**Don't forget the cleanup** (`terraform destroy`) when you're done experimenting — EKS bills add up.
