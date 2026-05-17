# ─────────────────────────────────────────────────────────────────────────
# ArgoCD — installed via the official Helm chart.
#
# After apply, get the initial admin password with:
#
#   kubectl -n argocd get secret argocd-initial-admin-secret \
#       -o jsonpath="{.data.password}" | base64 -d ; echo
#
# Reach the UI via port-forward:
#   kubectl -n argocd port-forward svc/argocd-server 8081:443
#   → https://localhost:8081  (user: admin)
#
# (Optional: expose via Ingress — annotated example commented at the bottom.)
# ─────────────────────────────────────────────────────────────────────────

resource "kubernetes_namespace" "argocd" {
  metadata {
    name = "argocd"
    labels = {
      "app.kubernetes.io/managed-by" = "terraform"
    }
  }
  depends_on = [module.eks]
}

resource "helm_release" "argocd" {
  name       = "argocd"
  repository = "https://argoproj.github.io/argo-helm"
  chart      = "argo-cd"
  namespace  = kubernetes_namespace.argocd.metadata[0].name
  version    = "7.6.0"

  # Use ClusterIP — we'll expose via Ingress later if needed.
  set {
    name  = "server.service.type"
    value = "ClusterIP"
  }
  set {
    name  = "server.insecure"
    value = "true"     # we'll terminate TLS at the ALB
  }
  # Reduce resource usage for tutorial-scale clusters
  set {
    name  = "controller.resources.requests.cpu"
    value = "100m"
  }
  set {
    name  = "controller.resources.requests.memory"
    value = "256Mi"
  }

  depends_on = [module.eks]
}
