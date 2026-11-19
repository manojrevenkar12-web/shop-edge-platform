output "cluster" { value = google_container_cluster.shop.name }
output "registry" { value = google_artifact_registry_repository.shop.id }
output "assets_bucket" { value = google_storage_bucket.assets.name }
