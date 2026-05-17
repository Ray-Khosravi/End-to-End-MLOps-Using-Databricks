# ─────────────────────────────────────────────────────────────────────────
# Providers + Backend
#
# All Terraform state lives in S3 (with DynamoDB locking).
# Replace the placeholders in `backend "s3"` with your bucket + table.
# ─────────────────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.60"
    }
    kubernetes = {
      source  = "hashicorp/kubernetes"
      version = "~> 2.30"
    }
    helm = {
      source  = "hashicorp/helm"
      version = "~> 2.14"
    }
  }

  # ── Remote state (created in docs/01-aws-s3-setup.md) ──────────────────
  backend "s3" {
    # IMPORTANT: edit these or pass `-backend-config=...` flags on init
    bucket         = "mlops-tfstate-CHANGEME"
    key            = "churn-mlops/terraform.tfstate"
    region         = "us-east-1"
    encrypt        = true
    dynamodb_table = "mlops-tflock"
  }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "churn-mlops"
      Environment = var.environment
      ManagedBy   = "terraform"
    }
  }
}

# ─── Data: pull EKS cluster info AFTER the cluster module creates it ─────
data "aws_eks_cluster" "this" {
  name       = module.eks.cluster_name
  depends_on = [module.eks]
}
data "aws_eks_cluster_auth" "this" {
  name       = module.eks.cluster_name
  depends_on = [module.eks]
}

provider "kubernetes" {
  host                   = data.aws_eks_cluster.this.endpoint
  cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data)
  token                  = data.aws_eks_cluster_auth.this.token
}

provider "helm" {
  kubernetes {
    host                   = data.aws_eks_cluster.this.endpoint
    cluster_ca_certificate = base64decode(data.aws_eks_cluster.this.certificate_authority[0].data)
    token                  = data.aws_eks_cluster_auth.this.token
  }
}
