# Cost per service: the billing export to BigQuery (read by sep/cost/finops.py) and a budget that alerts early.
resource "google_bigquery_dataset" "billing" {
  dataset_id = "billing_export"
  location   = "EU"
  labels     = local.labels
}

resource "google_billing_budget" "shop" {
  billing_account = var.billing_account
  display_name    = "shop-${var.env}"
  budget_filter {
    projects = ["projects/${var.project}"]
  }
  amount {
    specified_amount {
      currency_code = "EUR"
      units         = tostring(var.monthly_budget_eur)
    }
  }
  threshold_rules { threshold_percent = 0.5 }
  threshold_rules { threshold_percent = 0.8 }
  threshold_rules {
    threshold_percent = 1.0
    spend_basis       = "FORECASTED_SPEND"
  }
}
