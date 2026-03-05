terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }
}

variable "project_id" {
  default = "kin-tracker"
}

variable "region" {
  default = "us-central1"
}

# ── Secret shells — values are set via gcloud secrets versions add ─────────────
# NEVER set sensitive defaults here; Terraform state must never contain secrets.

resource "google_secret_manager_secret" "db_url" {
  secret_id = "kin-db-url"
  project   = var.project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "mqtt_password" {
  secret_id = "kin-mqtt-password"
  project   = var.project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "jwt_secret" {
  secret_id = "kin-jwt-secret"
  project   = var.project_id

  replication {
    auto {}
  }
}

resource "google_secret_manager_secret" "encryption_key" {
  secret_id = "kin-encryption-key"
  project   = var.project_id

  replication {
    auto {}
  }
}
