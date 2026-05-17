# ─────────────────────────────────────────────────────────────────────────
# Input variables. Defaults are sensible for the tutorial — override in
# terraform.tfvars or via `-var=...` on the CLI.
# ─────────────────────────────────────────────────────────────────────────

variable "aws_region" {
  description = "AWS region for all resources"
  type        = string
  default     = "us-east-1"
}

variable "environment" {
  description = "Environment label (dev / staging / prod)"
  type        = string
  default     = "dev"
}

variable "project" {
  description = "Short project name (used as resource-name prefix)"
  type        = string
  default     = "churn-mlops"
}

# ─── VPC ─────────────────────────────────────────────────────────────────
variable "vpc_cidr" {
  description = "CIDR block for the VPC"
  type        = string
  default     = "10.0.0.0/16"
}

variable "azs" {
  description = "Availability zones to span"
  type        = list(string)
  default     = ["us-east-1a", "us-east-1b"]
}

variable "public_subnets" {
  description = "Public subnet CIDRs (one per AZ; for ALB + NAT GW)"
  type        = list(string)
  default     = ["10.0.1.0/24", "10.0.2.0/24"]
}

variable "private_subnets" {
  description = "Private subnet CIDRs (one per AZ; for EKS nodes)"
  type        = list(string)
  default     = ["10.0.11.0/24", "10.0.12.0/24"]
}

# ─── EKS ─────────────────────────────────────────────────────────────────
variable "cluster_name" {
  description = "EKS cluster name"
  type        = string
  default     = "churn-mlops-eks"
}

variable "cluster_version" {
  description = "Kubernetes version"
  type        = string
  default     = "1.30"
}

variable "node_instance_types" {
  description = "Node group instance types"
  type        = list(string)
  default     = ["t3.medium"]
}

variable "node_desired_size" {
  description = "Desired number of worker nodes"
  type        = number
  default     = 2
}

variable "node_min_size" {
  type    = number
  default = 1
}

variable "node_max_size" {
  type    = number
  default = 4
}

# ─── DNS ─────────────────────────────────────────────────────────────────
variable "domain_name" {
  description = "Your registered domain (e.g. example.com). Leave empty to skip Route 53 setup."
  type        = string
  default     = ""
}

variable "app_subdomain" {
  description = "Subdomain for the app (e.g. 'app' → app.example.com)"
  type        = string
  default     = "app"
}

variable "acm_certificate_arn" {
  description = "ACM cert ARN for *.<domain_name>. Create one in advance in ACM console."
  type        = string
  default     = ""
}
