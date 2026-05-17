# ─────────────────────────────────────────────────────────────────────────
# Route 53 — points <app_subdomain>.<domain_name> at the ALB.
#
# Skipped entirely if var.domain_name is empty (useful for cheap testing
# before you have a domain).
#
# This file uses a DATA source to look up the ALB, because the ALB is
# created by the AWS Load Balancer Controller AFTER Ingress is applied.
# So you'd typically:
#   1. terraform apply  (creates VPC, EKS, ALB controller)
#   2. kubectl apply -f k8s/  (creates Ingress → ALB is provisioned)
#   3. terraform apply -target=aws_route53_record.app  (creates DNS record)
# ─────────────────────────────────────────────────────────────────────────

# Look up the existing hosted zone (you must create it once in the AWS console
# or via `aws route53 create-hosted-zone`, and update your domain registrar
# to use its name servers).
data "aws_route53_zone" "main" {
  count        = var.domain_name == "" ? 0 : 1
  name         = var.domain_name
  private_zone = false
}

# Look up the ALB that the controller created from our Ingress. The lookup
# is by tag; the controller tags ALBs with the cluster name and ingress info.
data "aws_lb" "ingress" {
  count = var.domain_name == "" ? 0 : 1

  tags = {
    "ingress.k8s.aws/stack"          = "default/churn-ingress"
    "elbv2.k8s.aws/cluster"          = var.cluster_name
  }
}

resource "aws_route53_record" "app" {
  count   = var.domain_name == "" ? 0 : 1
  zone_id = data.aws_route53_zone.main[0].zone_id
  name    = "${var.app_subdomain}.${var.domain_name}"
  type    = "A"

  alias {
    name                   = data.aws_lb.ingress[0].dns_name
    zone_id                = data.aws_lb.ingress[0].zone_id
    evaluate_target_health = true
  }
}
