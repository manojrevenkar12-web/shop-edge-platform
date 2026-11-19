# Regional GKE with Managed Prometheus; separate node pools so Varnish memory never competes with PHP.
resource "google_container_cluster" "shop" {
  name                     = "shop-${var.env}"
  location                 = var.region
  remove_default_node_pool = true
  initial_node_count       = 1
  networking_mode          = "VPC_NATIVE"
  release_channel { channel = "REGULAR" }
  ip_allocation_policy {}
  workload_identity_config { workload_pool = "${var.project}.svc.id.goog" }
  monitoring_config {
    enable_components = ["SYSTEM_COMPONENTS"]
    managed_prometheus { enabled = true }
  }
  cost_management_config { enabled = true } # GKE cost allocation: cost per namespace and label in the billing export
  resource_labels = local.labels
}

resource "google_container_node_pool" "php" {
  name     = "php"
  cluster  = google_container_cluster.shop.id
  location = var.region
  autoscaling {
    total_min_node_count = 3
    total_max_node_count = 60
  }
  node_config {
    machine_type    = "c3-standard-8"
    labels          = { workload = "php" }
    resource_labels = merge(local.labels, { service = "shop-php" })
    workload_metadata_config { mode = "GKE_METADATA" }
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }
}

resource "google_container_node_pool" "cache" {
  name       = "cache"
  cluster    = google_container_cluster.shop.id
  location   = var.region
  node_count = 1
  node_config {
    machine_type    = "n2-highmem-4"
    labels          = { workload = "varnish" }
    resource_labels = merge(local.labels, { service = "varnish" })
    taint {
      key    = "workload"
      value  = "varnish"
      effect = "NO_SCHEDULE"
    }
    workload_metadata_config { mode = "GKE_METADATA" }
    oauth_scopes = ["https://www.googleapis.com/auth/cloud-platform"]
  }
}

resource "google_artifact_registry_repository" "shop" {
  location      = var.region
  repository_id = "shop"
  format        = "DOCKER"
  labels        = local.labels
}
