# Container App Environment
resource "azurerm_log_analytics_workspace" "law" {
  name                = "law-cost-optimizer"
  location            = data.azurerm_resource_group.tst1.location
  resource_group_name = data.azurerm_resource_group.tst1.name
  sku                 = "PerGB2018"
  retention_in_days   = 30
  tags                = var.tags
}

resource "azurerm_container_app_environment" "env" {
  name                       = "cae-cost-optimizer"
  location                   = data.azurerm_resource_group.tst1.location
  resource_group_name        = data.azurerm_resource_group.tst1.name
  log_analytics_workspace_id = azurerm_log_analytics_workspace.law.id
  tags                       = var.tags
}

# API Container App
resource "azurerm_container_app" "api" {
  name                         = "tstapp01"
  container_app_environment_id = azurerm_container_app_environment.env.id
  resource_group_name          = data.azurerm_resource_group.tst1.name
  revision_mode                = "Single"
  tags                         = var.tags

  ingress {
    external_enabled = true
    target_port      = 8000
    traffic_weight {
      percentage      = 100
      latest_revision = true
    }
  }

  template {
    min_replicas = 1
    max_replicas = 1

    container {
      name   = "api"
      image  = "${azurerm_container_registry.acr.login_server}/cloud-cost-optimizer-api:${var.api_image_tag}"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "AZURE_TENANT_ID"
        value = var.tenant_id
      }
      env {
        name  = "AZURE_CLIENT_ID"
        value = var.client_id
      }
      env {
        name        = "AZURE_CLIENT_SECRET"
        secret_name = "azure-client-secret"
      }
      env {
        name  = "AZURE_SUBSCRIPTION_ID"
        value = var.subscription_id
      }
      env {
        name  = "AZURE_KEYVAULT_URL"
        value = data.azurerm_key_vault.kv.vault_uri
      }
      env {
        name  = "AZURE_STORAGE_ACCOUNT_URL"
        value = "https://${data.azurerm_storage_account.data.name}.blob.core.windows.net"
      }
      env {
        name  = "AZURE_DB_CONTAINER_NAME"
        value = azurerm_storage_container.db.name
      }
      env {
        name  = "AZURE_EXPORTS_CONTAINER_NAME"
        value = azurerm_storage_container.exports.name
      }
      env {
        name  = "DATABASE_PROVIDER"
        value = "sqlite"
      }
      env {
        name  = "LOCAL_DB_PATH"
        value = "/tmp/optimizer.db"
      }
      env {
        name  = "DB_BLOB_NAME"
        value = "optimizer.db"
      }
      env {
        name  = "LOCAL_SCRIPTS_DIR"
        value = "/tmp/deletion_scripts"
      }
      env {
        name  = "KV_SECRET_DB_SAS"
        value = var.kv_secret_db_sas
      }
      env {
        name  = "KV_SECRET_EXPORTS_SAS"
        value = var.kv_secret_exports_sas
      }
      env {
        name  = "IDLE_VM_CPU_THRESHOLD_PCT"
        value = tostring(var.idle_vm_cpu_threshold_pct)
      }
      env {
        name  = "IDLE_STORAGE_DAYS"
        value = tostring(var.idle_storage_days)
      }
      env {
        name  = "IDLE_APP_DAYS"
        value = tostring(var.idle_app_days)
      }
      env {
        name  = "IDLE_DB_DAYS"
        value = tostring(var.idle_db_days)
      }
      env {
        name  = "IDLE_AKS_CPU_THRESHOLD_PCT"
        value = tostring(var.idle_aks_cpu_threshold_pct)
      }
      env {
        name  = "ANALYSIS_LOOKBACK_DAYS"
        value = tostring(var.analysis_lookback_days)
      }
    }
  }

  registry {
    server               = azurerm_container_registry.acr.login_server
    username             = azurerm_container_registry.acr.admin_username
    password_secret_name = "acr-password"
  }
  secret {
    name  = "azure-client-secret"
    value = var.client_secret
  }
  secret {
    name  = "acr-password"
    value = azurerm_container_registry.acr.admin_password
  }
}

# Optimiser Container App Job (daily 02:00 UTC)
resource "azurerm_container_app_job" "optimiser" {
  name                         = "tstjob01"
  location                     = data.azurerm_resource_group.tst1.location
  resource_group_name          = data.azurerm_resource_group.tst1.name
  container_app_environment_id = azurerm_container_app_environment.env.id
  tags                         = var.tags

  replica_timeout_in_seconds = 1800
  replica_retry_limit        = 1

  schedule_trigger_config {
    cron_expression          = "0 2 * * *"
    parallelism              = 1
    replica_completion_count = 1
  }

  template {
    container {
      name   = "optimiser-job"
      image  = "${azurerm_container_registry.acr.login_server}/cloud-cost-optimizer-job:${var.api_image_tag}"
      cpu    = 0.5
      memory = "1Gi"

      env {
        name  = "AZURE_TENANT_ID"
        value = var.tenant_id
      }
      env {
        name  = "AZURE_CLIENT_ID"
        value = var.client_id
      }
      env {
        name        = "AZURE_CLIENT_SECRET"
        secret_name = "azure-client-secret"
      }
      env {
        name  = "AZURE_SUBSCRIPTION_ID"
        value = var.subscription_id
      }
      env {
        name  = "AZURE_KEYVAULT_URL"
        value = data.azurerm_key_vault.kv.vault_uri
      }
      env {
        name  = "AZURE_STORAGE_ACCOUNT_URL"
        value = "https://${data.azurerm_storage_account.data.name}.blob.core.windows.net"
      }
      env {
        name  = "AZURE_DB_CONTAINER_NAME"
        value = azurerm_storage_container.db.name
      }
      env {
        name  = "AZURE_EXPORTS_CONTAINER_NAME"
        value = azurerm_storage_container.exports.name
      }
      env {
        name  = "DATABASE_PROVIDER"
        value = "sqlite"
      }
      env {
        name  = "LOCAL_DB_PATH"
        value = "/tmp/optimizer.db"
      }
      env {
        name  = "DB_BLOB_NAME"
        value = "optimizer.db"
      }
      env {
        name  = "LOCAL_SCRIPTS_DIR"
        value = "/tmp/deletion_scripts"
      }
      env {
        name  = "KV_SECRET_DB_SAS"
        value = var.kv_secret_db_sas
      }
      env {
        name  = "KV_SECRET_EXPORTS_SAS"
        value = var.kv_secret_exports_sas
      }
      env {
        name  = "IDLE_VM_CPU_THRESHOLD_PCT"
        value = tostring(var.idle_vm_cpu_threshold_pct)
      }
      env {
        name  = "IDLE_STORAGE_DAYS"
        value = tostring(var.idle_storage_days)
      }
      env {
        name  = "IDLE_APP_DAYS"
        value = tostring(var.idle_app_days)
      }
      env {
        name  = "IDLE_DB_DAYS"
        value = tostring(var.idle_db_days)
      }
      env {
        name  = "IDLE_AKS_CPU_THRESHOLD_PCT"
        value = tostring(var.idle_aks_cpu_threshold_pct)
      }
      env {
        name  = "ANALYSIS_LOOKBACK_DAYS"
        value = tostring(var.analysis_lookback_days)
      }
    }
  }

  registry {
    server               = azurerm_container_registry.acr.login_server
    username             = azurerm_container_registry.acr.admin_username
    password_secret_name = "acr-password"
  }
  secret {
    name  = "azure-client-secret"
    value = var.client_secret
  }
  secret {
    name  = "acr-password"
    value = azurerm_container_registry.acr.admin_password
  }
}
