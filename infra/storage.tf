# Storage Account (existing - read via data source)
data "azurerm_storage_account" "data" {
  name                = var.storage_account_name
  resource_group_name = data.azurerm_resource_group.tst1.name
}

resource "azurerm_storage_container" "db" {
  name                  = "optimizer-db"
  storage_account_name  = data.azurerm_storage_account.data.name
  container_access_type = "private"
  lifecycle { prevent_destroy = true }
}

resource "azurerm_storage_container" "exports" {
  name                  = "optimizer-exports"
  storage_account_name  = data.azurerm_storage_account.data.name
  container_access_type = "private"
  lifecycle { prevent_destroy = true }
}

data "azurerm_storage_account_blob_container_sas" "db" {
  connection_string = data.azurerm_storage_account.data.primary_connection_string
  container_name    = azurerm_storage_container.db.name
  https_only        = true
  start             = "2024-01-01"
  expiry            = "2029-12-31"
  permissions {
    read   = true
    add    = true
    create = true
    write  = true
    delete = false
    list   = true
  }
}

data "azurerm_storage_account_blob_container_sas" "exports" {
  connection_string = data.azurerm_storage_account.data.primary_connection_string
  container_name    = azurerm_storage_container.exports.name
  https_only        = true
  start             = "2024-01-01"
  expiry            = "2029-12-31"
  permissions {
    read   = true
    add    = true
    create = true
    write  = true
    delete = false
    list   = true
  }
}
