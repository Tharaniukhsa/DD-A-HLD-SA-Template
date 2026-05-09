terraform {
  required_version = ">= 1.6.0"
  required_providers {
    azurerm = {
      source  = "hashicorp/azurerm"
      version = "~> 4.0"
    }
  }
}

provider "azurerm" {
  features {}
}

resource "azurerm_resource_group" "data_rg" {
  name     = "rg-data-solution"
  location = "UK South"
}

resource "azurerm_storage_account" "data_lake" {
  name                     = "ukhsadatalake001"
  resource_group_name      = azurerm_resource_group.data_rg.name
  location                 = azurerm_resource_group.data_rg.location
  account_tier             = "Standard"
  account_replication_type = "LRS"
}

# Components discovered: 0
# Datasets discovered: 0
