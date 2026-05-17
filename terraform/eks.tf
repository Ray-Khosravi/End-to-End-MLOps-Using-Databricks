# ─────────────────────────────────────────────────────────────────────────
# EKS Cluster
#
# Uses the official terraform-aws-modules/eks/aws module.
# Key choices for the tutorial:
#   • Cluster API endpoint:    public (so kubectl from your laptop works)
#                              tighten to private in prod via cluster_endpoint_public_access_cidrs
#   • Worker nodes:            in PRIVATE subnets (no public IPs)
#   • IRSA:                    enabled (needed by ALB Controller & ArgoCD)
# ─────────────────────────────────────────────────────────────────────────

module "eks" {
  source  = "terraform-aws-modules/eks/aws"
  version = "~> 20.24"

  cluster_name    = var.cluster_name
  cluster_version = var.cluster_version

  vpc_id     = module.vpc.vpc_id
  subnet_ids = module.vpc.private_subnets

  # Public API endpoint so you can run kubectl from your laptop. In production
  # restrict by IP via `cluster_endpoint_public_access_cidrs`.
  cluster_endpoint_public_access  = true
  cluster_endpoint_private_access = true

  # IRSA — required by ALB Controller and any pod needing IAM perms
  enable_irsa = true

  # Managed addons keep CoreDNS, kube-proxy, VPC CNI, EBS CSI up to date
  cluster_addons = {
    coredns                = { most_recent = true }
    kube-proxy             = { most_recent = true }
    vpc-cni                = { most_recent = true }
    aws-ebs-csi-driver     = { most_recent = true }
    eks-pod-identity-agent = { most_recent = true }
  }

  # Single managed node group on private subnets
  eks_managed_node_groups = {
    default = {
      desired_size   = var.node_desired_size
      min_size       = var.node_min_size
      max_size       = var.node_max_size
      instance_types = var.node_instance_types
      capacity_type  = "ON_DEMAND"

      labels = {
        role = "general"
      }

      tags = {
        "k8s.io/cluster-autoscaler/enabled"             = "true"
        "k8s.io/cluster-autoscaler/${var.cluster_name}" = "owned"
      }
    }
  }

  # Grant the IAM user/role running terraform full cluster admin via the
  # EKS access entries API (replaces the older aws-auth ConfigMap approach).
  enable_cluster_creator_admin_permissions = true

  tags = {
    Project = var.project
  }
}
