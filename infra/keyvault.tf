data "azurerm_client_config" "current" {}

# Key Vault (existing - read via data source)
data "azurerm_key_vault" "kv" {
  name                = var.key_vault_name
  resource_group_name = data.azurerm_resource_group.tst1.name
}

# Single access policy for the SP (deployer + runtime - same object_id)
resource "azurerm_key_vault_access_policy" "deployer" {
  key_vault_id       = data.azurerm_key_vault.kv.id
  tenant_id          = var.tenant_id
  object_id          = data.azurerm_client_config.current.object_id
  secret_permissions = ["Get", "List", "Set", "Delete", "Purge"]
}

# SAS secrets - names match what is already in the vault
resource "azurerm_key_vault_secret" "db_sas" {
  name         = var.kv_secret_db_sas
  value        = data.azurerm_storage_account_blob_container_sas.db.sas
  key_vault_id = data.azurerm_key_vault.kv.id
  depends_on   = [azurerm_key_vault_access_policy.deployer]

  lifecycle {
    ignore_changes = [value]
  }
}

resource "azurerm_key_vault_secret" "exports_sas" {
  name         = var.kv_secret_exports_sas
  value        = data.azurerm_storage_account_blob_container_sas.exports.sas
  key_vault_id = data.azurerm_key_vault.kv.id
  depends_on   = [azurerm_key_vault_access_policy.deployer]

  lifecycle {
    ignore_changes = [value]
  }
}
