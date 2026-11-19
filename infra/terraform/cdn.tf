# Static assets (images, JS, CSS) from a bucket behind Cloud CDN; HTML goes to Varnish through the same load balancer.
resource "google_storage_bucket" "assets" {
  name                        = "${var.project}-shop-assets"
  location                    = "EU"
  uniform_bucket_level_access = true
  labels                      = merge(local.labels, { service = "cdn" })
}

resource "google_compute_backend_bucket" "assets" {
  name        = "shop-assets"
  bucket_name = google_storage_bucket.assets.name
  enable_cdn  = true
  cdn_policy {
    cache_mode        = "CACHE_ALL_STATIC"
    default_ttl       = 86400
    max_ttl           = 31536000
    serve_while_stale = 86400
    cache_key_policy {
      query_string_whitelist = ["v"]
    }
  }
}

resource "google_compute_global_address" "shop" {
  name = "shop-${var.env}"
}
