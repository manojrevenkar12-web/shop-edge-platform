terraform {
  required_version = ">= 1.7"
  required_providers {
    google = { source = "hashicorp/google", version = "~> 6.10" }
  }
}

provider "google" {
  project = var.project
  region  = var.region
}

locals {
  labels = { platform = "shop-edge", env = var.env }
}
