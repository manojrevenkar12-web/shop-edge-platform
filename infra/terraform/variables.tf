variable "project" {
  type = string
}
variable "region" {
  type    = string
  default = "europe-west3"
}
variable "env" {
  type    = string
  default = "prod"
}
variable "billing_account" {
  type        = string
  description = "Billing account for budgets and the BigQuery billing export"
}
variable "monthly_budget_eur" {
  type    = number
  default = 25000
}
