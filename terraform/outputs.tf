# ─────────────────────────────────────────────────────────────────────────
# Outputs — convenient summary printed after `terraform apply`.
# ─────────────────────────────────────────────────────────────────────────

output "cluster_name" {
  description = "EKS cluster name (use with `aws eks update-kubeconfig`)"
  value       = module.eks.cluster_name
}

output "cluster_endpoint" {
  description = "EKS API server endpoint"
  value       = module.eks.cluster_endpoint
}

output "cluster_region" {
  description = "Region — needed for kubeconfig"
  value       = var.aws_region
}

output "vpc_id" {
  description = "VPC ID"
  value       = module.vpc.vpc_id
}

output "private_subnet_ids" {
  description = "Private subnet IDs (where EKS nodes live)"
  value       = module.vpc.private_subnets
}

output "public_subnet_ids" {
  description = "Public subnet IDs (where the ALB lives)"
  value       = module.vpc.public_subnets
}

output "kubeconfig_command" {
  description = "Run this to point kubectl at the new cluster"
  value       = "aws eks update-kubeconfig --region ${var.aws_region} --name ${module.eks.cluster_name}"
}

output "argocd_password_command" {
  description = "Retrieve the initial ArgoCD admin password"
  value       = "kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d ; echo"
}

output "alb_dns_name" {
  description = "ALB DNS name (only populated after k8s/ingress.yaml is applied)"
  value       = try(data.aws_lb.ingress[0].dns_name, "ALB not provisioned yet — apply k8s/ingress.yaml first")
}

output "app_url" {
  description = "Final URL of the app"
  value = var.domain_name == "" ? (
    "ALB DNS (no custom domain): http://<alb-dns>  — get it with: kubectl get ingress -A"
  ) : (
    "https://${var.app_subdomain}.${var.domain_name}"
  )
}
