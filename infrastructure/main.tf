# ──────────────────────────────────────────────────────────────
# Content-to-Ebook Agent — Google Cloud Infrastructure
# Matches the Cloud Assist architecture diagram:
#
#   ebook-lb-frontend (Cloud Load Balancer)
#   ebook-global-lb-backend (Cloud Load Balancer)
#   ebook-frontend-sales-platform (Cloud Run)
#   ebook-content-processor (Cloud Run)
#   ebook-validation-workflow (Cloud Run)
#   ebook-raw-uploads (Cloud Storage)
#   ebook-final-files (Cloud Storage)
#   ebook-processing-trigger (Pub/Sub)
#   ebook-db-secret (Secret Manager)
#   vertex-ai-capabilities (Vertex AI)
#   ebook-postgresql-db (Cloud SQL)
# ──────────────────────────────────────────────────────────────

terraform {
  required_version = ">= 1.5"

  required_providers {
    google = {
      source  = "hashicorp/google"
      version = "~> 5.0"
    }
  }

  backend "gcs" {
    bucket = "ebook-agent-terraform-state"
    prefix = "terraform/state"
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# ──────────────────────────────────────────────────────────────
# Variables
# ──────────────────────────────────────────────────────────────

variable "project_id" {
  description = "GCP Project ID"
  type        = string
}

variable "region" {
  description = "GCP region for resources"
  type        = string
  default     = "us-central1"
}

variable "db_password" {
  description = "PostgreSQL database password"
  type        = string
  sensitive   = true
}

variable "domain_name" {
  description = "Custom domain for the frontend (optional)"
  type        = string
  default     = ""
}

# ──────────────────────────────────────────────────────────────
# Enable required APIs
# ──────────────────────────────────────────────────────────────

resource "google_project_service" "apis" {
  for_each = toset([
    "run.googleapis.com",
    "cloudbuild.googleapis.com",
    "sqladmin.googleapis.com",
    "pubsub.googleapis.com",
    "secretmanager.googleapis.com",
    "aiplatform.googleapis.com",
    "vision.googleapis.com",
    "videointelligence.googleapis.com",
    "texttospeech.googleapis.com",
    "translate.googleapis.com",
    "compute.googleapis.com",
  ])

  service            = each.value
  disable_on_destroy = false
}

# ──────────────────────────────────────────────────────────────
# Cloud Storage — ebook-raw-uploads & ebook-final-files
# ──────────────────────────────────────────────────────────────

resource "google_storage_bucket" "raw_uploads" {
  name          = "${var.project_id}-ebook-raw-uploads"
  location      = var.region
  force_destroy = false
  storage_class = "STANDARD"

  uniform_bucket_level_access = true

  lifecycle_rule {
    condition {
      age = 90 # Auto-delete raw uploads after 90 days
    }
    action {
      type = "Delete"
    }
  }

  cors {
    origin          = ["*"]
    method          = ["PUT", "POST", "GET"]
    response_header = ["Content-Type"]
    max_age_seconds = 3600
  }
}

resource "google_storage_bucket" "processed_files" {
  name          = "${var.project_id}-ebook-processed"
  location      = var.region
  force_destroy = false
  storage_class = "STANDARD"

  uniform_bucket_level_access = true
}

resource "google_storage_bucket" "final_files" {
  name          = "${var.project_id}-ebook-final-files"
  location      = var.region
  force_destroy = false
  storage_class = "STANDARD"

  uniform_bucket_level_access = true

  cors {
    origin          = ["*"]
    method          = ["GET"]
    response_header = ["Content-Type", "Content-Disposition"]
    max_age_seconds = 3600
  }
}

# ──────────────────────────────────────────────────────────────
# Pub/Sub — ebook-processing-trigger
# ──────────────────────────────────────────────────────────────

resource "google_pubsub_topic" "processing_trigger" {
  name = "ebook-processing-trigger"

  depends_on = [google_project_service.apis]
}

resource "google_pubsub_topic" "content_processed" {
  name = "ebook-content-processed"

  depends_on = [google_project_service.apis]
}

resource "google_pubsub_topic" "ebook_ready" {
  name = "ebook-ready"

  depends_on = [google_project_service.apis]
}

resource "google_pubsub_subscription" "processor_sub" {
  name  = "ebook-processor-subscription"
  topic = google_pubsub_topic.processing_trigger.id

  ack_deadline_seconds = 600 # 10 minutes for processing

  push_config {
    push_endpoint = "${google_cloud_run_v2_service.content_processor.uri}/api/v1/process"
  }
}

# GCS notification → Pub/Sub (auto-trigger on upload)
resource "google_storage_notification" "raw_upload_notification" {
  bucket         = google_storage_bucket.raw_uploads.name
  payload_format = "JSON_API_V1"
  topic          = google_pubsub_topic.processing_trigger.id
  event_types    = ["OBJECT_FINALIZE"]

  depends_on = [google_pubsub_topic.processing_trigger]
}

# ──────────────────────────────────────────────────────────────
# Cloud SQL — ebook-postgresql-db
# ──────────────────────────────────────────────────────────────

resource "google_sql_database_instance" "postgres" {
  name             = "ebook-postgresql-db"
  database_version = "POSTGRES_15"
  region           = var.region

  settings {
    tier              = "db-f1-micro" # Start small, scale as needed
    availability_type = "ZONAL"

    ip_configuration {
      ipv4_enabled = false
      # Private IP for Cloud Run access
      private_network = google_compute_network.vpc.id
    }

    backup_configuration {
      enabled            = true
      start_time         = "03:00"
      point_in_time_recovery_enabled = true
    }
  }

  deletion_protection = true

  depends_on = [
    google_project_service.apis,
    google_service_networking_connection.private_vpc,
  ]
}

resource "google_sql_database" "ebook_db" {
  name     = "ebook_agent"
  instance = google_sql_database_instance.postgres.name
}

resource "google_sql_user" "ebook_user" {
  name     = "ebook_agent"
  instance = google_sql_database_instance.postgres.name
  password = var.db_password
}

# ──────────────────────────────────────────────────────────────
# VPC — Private networking for Cloud SQL
# ──────────────────────────────────────────────────────────────

resource "google_compute_network" "vpc" {
  name                    = "ebook-agent-vpc"
  auto_create_subnetworks = true

  depends_on = [google_project_service.apis]
}

resource "google_compute_global_address" "private_ip" {
  name          = "ebook-private-ip"
  purpose       = "VPC_PEERING"
  address_type  = "INTERNAL"
  prefix_length = 16
  network       = google_compute_network.vpc.id
}

resource "google_service_networking_connection" "private_vpc" {
  network                 = google_compute_network.vpc.id
  service                 = "servicenetworking.googleapis.com"
  reserved_peering_ranges = [google_compute_global_address.private_ip.name]
}

# ──────────────────────────────────────────────────────────────
# Secret Manager — per-service secrets (matching diagram)
#   - ebook-content-processor-db-secret
#   - ebook-validation-workflow-db-secret
# ──────────────────────────────────────────────────────────────

resource "google_secret_manager_secret" "content_processor_db_secret" {
  secret_id = "ebook-content-processor-db-secret"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "content_processor_db_secret_version" {
  secret      = google_secret_manager_secret.content_processor_db_secret.id
  secret_data = "postgresql://ebook_agent:${var.db_password}@${google_sql_database_instance.postgres.private_ip_address}/ebook_agent"
}

resource "google_secret_manager_secret" "validation_workflow_db_secret" {
  secret_id = "ebook-validation-workflow-db-secret"

  replication {
    auto {}
  }

  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "validation_workflow_db_secret_version" {
  secret      = google_secret_manager_secret.validation_workflow_db_secret.id
  secret_data = "postgresql://ebook_agent:${var.db_password}@${google_sql_database_instance.postgres.private_ip_address}/ebook_agent"
}

# ──────────────────────────────────────────────────────────────
# Service Account for Cloud Run services
# ──────────────────────────────────────────────────────────────

resource "google_service_account" "ebook_agent_sa" {
  account_id   = "ebook-agent-sa"
  display_name = "Ebook Agent Service Account"
}

# Grant necessary roles
resource "google_project_iam_member" "sa_roles" {
  for_each = toset([
    "roles/storage.objectAdmin",
    "roles/pubsub.publisher",
    "roles/pubsub.subscriber",
    "roles/secretmanager.secretAccessor",
    "roles/aiplatform.user",
    "roles/cloudsql.client",
  ])

  project = var.project_id
  role    = each.value
  member  = "serviceAccount:${google_service_account.ebook_agent_sa.email}"
}

# ──────────────────────────────────────────────────────────────
# Cloud Run — ebook-frontend-sales-platform
# ──────────────────────────────────────────────────────────────

resource "google_cloud_run_v2_service" "frontend" {
  name     = "ebook-frontend-sales-platform"
  location = var.region

  template {
    service_account = google_service_account.ebook_agent_sa.email

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/ebook-agent/frontend:latest"

      ports {
        container_port = 8080
      }

      resources {
        limits = {
          cpu    = "1"
          memory = "512Mi"
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }
  }

  depends_on = [google_project_service.apis]
}

# Allow public access to frontend
resource "google_cloud_run_v2_service_iam_member" "frontend_public" {
  project  = var.project_id
  location = var.region
  name     = google_cloud_run_v2_service.frontend.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}

# ──────────────────────────────────────────────────────────────
# Cloud Run — ebook-content-processor
# ──────────────────────────────────────────────────────────────

resource "google_cloud_run_v2_service" "content_processor" {
  name     = "ebook-content-processor"
  location = var.region

  template {
    service_account = google_service_account.ebook_agent_sa.email

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/ebook-agent/backend:latest"

      ports {
        container_port = 8080
      }

      env {
        name  = "EBOOK_AGENT_GCP_PROJECT_ID"
        value = var.project_id
      }
      env {
        name  = "EBOOK_AGENT_GCS_RAW_BUCKET"
        value = google_storage_bucket.raw_uploads.name
      }
      env {
        name  = "EBOOK_AGENT_GCS_PROCESSED_BUCKET"
        value = google_storage_bucket.processed_files.name
      }
      env {
        name  = "EBOOK_AGENT_GCS_EBOOK_BUCKET"
        value = google_storage_bucket.final_files.name
      }
      env {
        name = "EBOOK_AGENT_DATABASE_URL"
        value_source {
          secret_key_ref {
            secret  = google_secret_manager_secret.content_processor_db_secret.secret_id
            version = "latest"
          }
        }
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "2Gi"
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 20
    }

    timeout = "900s" # 15 minutes for heavy processing

    vpc_access {
      network_interfaces {
        network = google_compute_network.vpc.name
      }
      egress = "PRIVATE_RANGES_ONLY"
    }
  }

  depends_on = [google_project_service.apis]
}

# ──────────────────────────────────────────────────────────────
# Cloud Run — ebook-validation-workflow
# ──────────────────────────────────────────────────────────────

resource "google_cloud_run_v2_service" "validation_workflow" {
  name     = "ebook-validation-workflow"
  location = var.region

  template {
    service_account = google_service_account.ebook_agent_sa.email

    containers {
      image = "${var.region}-docker.pkg.dev/${var.project_id}/ebook-agent/validation:latest"

      ports {
        container_port = 8080
      }

      env {
        name  = "EBOOK_AGENT_GCP_PROJECT_ID"
        value = var.project_id
      }

      resources {
        limits = {
          cpu    = "2"
          memory = "1Gi"
        }
      }
    }

    scaling {
      min_instance_count = 0
      max_instance_count = 10
    }

    timeout = "600s"
  }

  depends_on = [google_project_service.apis]
}

# ──────────────────────────────────────────────────────────────
# Artifact Registry (Docker images)
# ──────────────────────────────────────────────────────────────

resource "google_artifact_registry_repository" "docker_repo" {
  location      = var.region
  repository_id = "ebook-agent"
  format        = "DOCKER"

  depends_on = [google_project_service.apis]
}

# ──────────────────────────────────────────────────────────────
# Load Balancers — ebook-lb-frontend & ebook-global-lb-backend
# ──────────────────────────────────────────────────────────────

# Frontend Load Balancer
resource "google_compute_region_network_endpoint_group" "frontend_neg" {
  name                  = "ebook-frontend-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.frontend.name
  }
}

resource "google_compute_backend_service" "frontend_backend" {
  name       = "ebook-frontend-backend"
  protocol   = "HTTP"
  port_name  = "http"
  enable_cdn = true

  backend {
    group = google_compute_region_network_endpoint_group.frontend_neg.id
  }
}

resource "google_compute_url_map" "frontend_urlmap" {
  name            = "ebook-lb-frontend"
  default_service = google_compute_backend_service.frontend_backend.id
}

resource "google_compute_target_http_proxy" "frontend_proxy" {
  name    = "ebook-frontend-proxy"
  url_map = google_compute_url_map.frontend_urlmap.id
}

resource "google_compute_global_forwarding_rule" "frontend_lb" {
  name       = "ebook-lb-frontend-rule"
  target     = google_compute_target_http_proxy.frontend_proxy.id
  port_range = "80"
}

# Backend Load Balancer
resource "google_compute_region_network_endpoint_group" "backend_neg" {
  name                  = "ebook-backend-neg"
  region                = var.region
  network_endpoint_type = "SERVERLESS"

  cloud_run {
    service = google_cloud_run_v2_service.content_processor.name
  }
}

resource "google_compute_backend_service" "backend_backend" {
  name      = "ebook-backend-backend"
  protocol  = "HTTP"
  port_name = "http"

  backend {
    group = google_compute_region_network_endpoint_group.backend_neg.id
  }
}

resource "google_compute_url_map" "backend_urlmap" {
  name            = "ebook-global-lb-backend"
  default_service = google_compute_backend_service.backend_backend.id
}

resource "google_compute_target_http_proxy" "backend_proxy" {
  name    = "ebook-backend-proxy"
  url_map = google_compute_url_map.backend_urlmap.id
}

resource "google_compute_global_forwarding_rule" "backend_lb" {
  name       = "ebook-global-lb-backend-rule"
  target     = google_compute_target_http_proxy.backend_proxy.id
  port_range = "80"
}

# ──────────────────────────────────────────────────────────────
# Outputs
# ──────────────────────────────────────────────────────────────

output "frontend_url" {
  value       = google_cloud_run_v2_service.frontend.uri
  description = "Frontend sales platform URL"
}

output "backend_url" {
  value       = google_cloud_run_v2_service.content_processor.uri
  description = "Content processor API URL"
}

output "validation_url" {
  value       = google_cloud_run_v2_service.validation_workflow.uri
  description = "Validation workflow service URL"
}

output "raw_uploads_bucket" {
  value       = google_storage_bucket.raw_uploads.name
  description = "Raw uploads bucket name"
}

output "final_files_bucket" {
  value       = google_storage_bucket.final_files.name
  description = "Final ebook files bucket name"
}

output "db_connection_name" {
  value       = google_sql_database_instance.postgres.connection_name
  description = "Cloud SQL connection name"
}
