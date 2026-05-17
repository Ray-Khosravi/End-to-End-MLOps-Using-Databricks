# ─────────────────────────────────────────────────────────────────────────
# AWS Load Balancer Controller
#
# The controller watches Ingress resources and provisions/manages ALBs
# accordingly. It needs IAM permissions, which we grant via IRSA:
#
#   IAM role  ←─ trusted by ──  Cluster OIDC provider
#       ↑
#       │ annotation
#       │
#   ServiceAccount aws-load-balancer-controller (in kube-system)
#
# ─────────────────────────────────────────────────────────────────────────

# 1. Fetch the official IAM policy JSON published by AWS
data "http" "alb_controller_policy" {
  url = "https://raw.githubusercontent.com/kubernetes-sigs/aws-load-balancer-controller/v2.9.0/docs/install/iam_policy.json"
}

resource "aws_iam_policy" "alb_controller" {
  name        = "${var.cluster_name}-alb-controller"
  description = "IAM policy for the AWS Load Balancer Controller"
  policy      = data.http.alb_controller_policy.response_body
}

# 2. IRSA role bound to the kube-system/aws-load-balancer-controller SA
module "alb_controller_irsa" {
  source  = "terraform-aws-modules/iam/aws//modules/iam-role-for-service-accounts-eks"
  version = "~> 5.44"

  role_name = "${var.cluster_name}-alb-controller"

  role_policy_arns = {
    policy = aws_iam_policy.alb_controller.arn
  }

  oidc_providers = {
    main = {
      provider_arn               = module.eks.oidc_provider_arn
      namespace_service_accounts = ["kube-system:aws-load-balancer-controller"]
    }
  }
}

# 3. Install the controller via Helm
resource "helm_release" "alb_controller" {
  name             = "aws-load-balancer-controller"
  repository       = "https://aws.github.io/eks-charts"
  chart            = "aws-load-balancer-controller"
  namespace        = "kube-system"
  version          = "1.9.0"
  create_namespace = false

  set {
    name  = "clusterName"
    value = module.eks.cluster_name
  }
  set {
    name  = "serviceAccount.create"
    value = "true"
  }
  set {
    name  = "serviceAccount.name"
    value = "aws-load-balancer-controller"
  }
  set {
    name  = "serviceAccount.annotations.eks\\.amazonaws\\.com/role-arn"
    value = module.alb_controller_irsa.iam_role_arn
  }
  set {
    name  = "region"
    value = var.aws_region
  }
  set {
    name  = "vpcId"
    value = module.vpc.vpc_id
  }

  depends_on = [module.eks]
}
