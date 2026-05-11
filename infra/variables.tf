variable "subscription_id" {
  description = "Azure Subscription ID"
  type        = string
}

variable "tenant_id" {
  description = "Azure Tenant ID"
  type        = string
}

variable "client_id" {
  description = "Service Principal Client ID (App ID)"
  type        = string
}

variable "client_secret" {
  description = "Service Principal Client Secret"
  type        = string
  sensitive   = true
}

variable "app_sp_object_id" {
  description = "Object ID of the Service Principal (not the client/app ID)"
  type        = string
}

variable "location" {
  description = "Azure region for all resources"
  type        = string
  default     = "eastus"
}

variable "resource_group_name" {
  description = "Existing resource group to deploy all resources into"
  type        = string
  default     = "tst1"
}

variable "key_vault_name" {
  description = "Existing Key Vault name"
  type        = string
  default     = "tst-test-1"
}

variable "storage_account_name" {
  description = "Existing Storage Account name"
  type        = string
  default     = "tstteststg1"
}

variable "kv_secret_db_sas" {
  description = "KV secret name for the DB container SAS token"
  type        = string
  default     = "optimizer-db-sas-url"
}

variable "kv_secret_exports_sas" {
  description = "KV secret name for the exports container SAS token"
  type        = string
  default     = "optimizer-exports-sas-url"
}

variable "acr_name" {
  description = "Azure Container Registry name (must be globally unique, 5-50 alphanumeric)"
  type        = string
  default     = "acrtst1"
}

variable "api_image_tag" {
  description = "Docker image tag for container images"
  type        = string
  default     = "latest"
}

variable "tags" {
  description = "Common resource tags"
  type        = map(string)
  default = {
    project     = "cloud-cost-optimizer"
    environment = "mvp"
  }
}

# -- Analysis threshold overrides ---------------------------------------------
variable "idle_vm_cpu_threshold_pct" {
  type    = number
  default = 5.0
}

variable "idle_storage_days" {
  type    = number
  default = 30
}

variable "idle_app_days" {
  type    = number
  default = 30
}

variable "idle_db_days" {
  type    = number
  default = 30
}

variable "idle_aks_cpu_threshold_pct" {
  type    = number
  default = 10.0
}

variable "analysis_lookback_days" {
  type    = number
  default = 30
}