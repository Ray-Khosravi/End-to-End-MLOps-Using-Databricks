# ─────────────────────────────────────────────────────────────────────────
# VPC — public + private subnets, IGW, NAT GW, route tables
#
# We use the official terraform-aws-modules/vpc/aws module — it encodes
# AWS best practices and saves hundreds of lines of low-level resources.
#
# Subnet tags are critical for the AWS Load Balancer Controller:
#   • public  subnets:  kubernetes.io/role/elb           = 1
#   • private subnets:  kubernetes.io/role/internal-elb  = 1
#   • all  subnets:     kubernetes.io/cluster/<name>     = shared
# ─────────────────────────────────────────────────────────────────────────

module "vpc" {
  source  = "terraform-aws-modules/vpc/aws"
  version = "~> 5.13"

  name = "${var.project}-vpc"
  cidr = var.vpc_cidr

  azs             = var.azs
  public_subnets  = var.public_subnets
  private_subnets = var.private_subnets

  # IGW for public subnets (provider creates it because public_subnets is non-empty)
  # NAT GW for private subnets — outbound only, ingress is denied.
  enable_nat_gateway     = true
  single_nat_gateway     = true   # one NAT for all AZs → cheaper for the tutorial
                                  # set to false in real prod for AZ-fault-tolerance
  enable_dns_hostnames   = true
  enable_dns_support     = true

  # ─── Subnet tags for ALB Ingress Controller ───────────────────────────
  public_subnet_tags = {
    "kubernetes.io/role/elb"                    = "1"
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
  }
  private_subnet_tags = {
    "kubernetes.io/role/internal-elb"           = "1"
    "kubernetes.io/cluster/${var.cluster_name}" = "shared"
  }

  tags = {
    Project = var.project
  }
}
