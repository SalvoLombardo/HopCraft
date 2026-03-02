terraform {
  required_version = ">= 1.6"

  required_providers {
    aws = {
      source  = "hashicorp/aws"
      version = "~> 5.0"
    }
  }

  # ---------------------------------------------------------------------------
  # Terraform state remoto (S3) — abilitare dopo il primo `terraform apply`
  # Bootstrap: creare manualmente il bucket con:
  #   aws s3api create-bucket \
  #     --bucket hopcraft-terraform-state-YOURNAME \
  #     --region eu-south-1 \
  #     --create-bucket-configuration LocationConstraint=eu-south-1
  #   aws s3api put-bucket-versioning \
  #     --bucket hopcraft-terraform-state-YOURNAME \
  #     --versioning-configuration Status=Enabled
  # ---------------------------------------------------------------------------
  # backend "s3" {
  #   bucket = "hopcraft-terraform-state-YOURNAME"
  #   key    = "hopcraft/terraform.tfstate"
  #   region = "eu-south-1"
  # }
}

provider "aws" {
  region = var.aws_region

  default_tags {
    tags = {
      Project     = "hopcraft"
      ManagedBy   = "terraform"
      Environment = "production"
    }
  }
}
