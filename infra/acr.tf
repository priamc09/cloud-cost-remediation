# Azure Container Registry (new)
resource "azurerm_container_registry" "acr" {
  name                = var.acr_name
  resource_group_name = data.azurerm_resource_group.tst1.name
  location            = data.azurerm_resource_group.tst1.location
  sku                 = "Basic"
  admin_enabled       = true
  tags                = var.tags
}

# Role assignment skipped - using ACR admin credentials instead (SP lacks roleAssignments/write)
