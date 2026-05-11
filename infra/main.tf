terraform {
  required_version = ">= 1.7.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 3.110"
    }
  }
  # Remote state in Azure Storage (recommended for Azure DevOps)
  # backend "azurerm" {
  #   resource_group_name  = "rg-tfstate"
  #   storage_account_name = "stoptimizertfstate"
  #   container_name       = "tfstate"
  #   key                  = "optimizer.tfstate"
  # }
}

provider "azurerm" {
  features {
    key_vault {
      purge_soft_delete_on_destroy    = false
      recover_soft_deleted_key_vaults = true
    }
  }
  subscription_id = var.subscription_id
  tenant_id       = var.tenant_id
  client_id       = var.client_id
  client_secret   = var.client_secret
}

# ── Resource Group (existing) ─────────────────────────────────────────────────
# Using the pre-existing tst1 resource group; not managed by this Terraform.
data "azurerm_resource_group" "tst1" {
  name = var.resource_group_name
}
