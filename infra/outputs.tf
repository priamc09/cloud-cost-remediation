output "api_url" {
  description = "FQDN of the deployed API Container App"
  value       = "https://${azurerm_container_app.api.latest_revision_fqdn}"
}

output "key_vault_uri" {
  description = "Key Vault URI"
  value       = data.azurerm_key_vault.kv.vault_uri
}

output "storage_account_name" {
  description = "Storage account name"
  value       = data.azurerm_storage_account.data.name
}
