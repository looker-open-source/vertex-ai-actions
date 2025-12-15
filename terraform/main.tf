terraform {
  required_providers {
    google = {
      source  = "hashicorp/google"
      version = ">= 4.34.0"
    }
  }
}

provider "google" {
  project = var.project_id
  region  = var.region
}

# Enable required APIs
resource "google_project_service" "apis" {
  for_each = toset([
    "cloudfunctions.googleapis.com",
    "run.googleapis.com",
    "artifactregistry.googleapis.com",
    "cloudbuild.googleapis.com",
    "secretmanager.googleapis.com",
    "aiplatform.googleapis.com"
  ])
  service = each.key
  disable_on_destroy = false
}

# Service Account
resource "google_service_account" "function_sa" {
  account_id   = "vertex-looker-cf"
  display_name = "Looker Vertex AI Actions Service Account"
  depends_on   = [google_project_service.apis]
}

# IAM Bindings
resource "google_project_iam_member" "sa_roles" {
  for_each = toset([
    "roles/aiplatform.user",
    "roles/secretmanager.secretAccessor",
    "roles/logging.logWriter",
    "roles/artifactregistry.reader"
  ])
  project = var.project_id
  role    = each.key
  member  = "serviceAccount:${google_service_account.function_sa.email}"
}

# Secrets
resource "google_secret_manager_secret" "looker_token" {
  secret_id = "LOOKER_AUTH_TOKEN"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "looker_token_val" {
  secret      = google_secret_manager_secret.looker_token.id
  secret_data = var.looker_auth_token
}

# Optional Mailgun Secret
resource "google_secret_manager_secret" "mailgun_token" {
  count     = var.mailgun_api_token != "" ? 1 : 0
  secret_id = "MAILGUN_API_TOKEN"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "mailgun_token_val" {
  count       = var.mailgun_api_token != "" ? 1 : 0
  secret      = google_secret_manager_secret.mailgun_token[0].id
  secret_data = var.mailgun_api_token
}

# Optional Sendgrid Secret
resource "google_secret_manager_secret" "sendgrid_key" {
  count     = var.sendgrid_api_key != "" ? 1 : 0
  secret_id = "SENDGRID_API_KEY"
  replication {
    auto {}
  }
  depends_on = [google_project_service.apis]
}

resource "google_secret_manager_secret_version" "sendgrid_key_val" {
  count       = var.sendgrid_api_key != "" ? 1 : 0
  secret      = google_secret_manager_secret.sendgrid_key[0].id
  secret_data = var.sendgrid_api_key
}

# Cloud Function Source
data "archive_file" "source_zip" {
  type        = "zip"
  source_dir  = "${path.module}/.."
  output_path = "${path.module}/source.zip"
  excludes    = ["terraform", "venv", ".git", "__pycache__", ".env.yaml", ".env.yaml.example", "deploy.sh", "tests", "Notes.md"]
}

resource "google_storage_bucket" "source_bucket" {
  name                        = "${var.project_id}-gcf-source"
  location                    = var.region
  uniform_bucket_level_access = true
}

resource "google_storage_bucket_object" "source_object" {
  name   = "source-${data.archive_file.source_zip.output_md5}.zip"
  bucket = google_storage_bucket.source_bucket.name
  source = data.archive_file.source_zip.output_path
}

locals {
  secrets_list = concat(
    [
      {
        key        = "LOOKER_AUTH_TOKEN"
        project_id = var.project_id
        secret     = google_secret_manager_secret.looker_token.secret_id
        version    = "latest"
      }
    ],
    var.mailgun_api_token != "" ? [
      {
        key        = "MAILGUN_API_TOKEN"
        project_id = var.project_id
        secret     = google_secret_manager_secret.mailgun_token[0].secret_id
        version    = "latest"
      }
    ] : [],
    var.sendgrid_api_key != "" ? [
      {
        key        = "SENDGRID_API_KEY"
        project_id = var.project_id
        secret     = google_secret_manager_secret.sendgrid_key[0].secret_id
        version    = "latest"
      }
    ] : []
  )
}

# Cloud Function
resource "google_cloudfunctions2_function" "function" {
  name        = var.action_name
  location    = var.region
  description = "Looker Vertex AI Action"

  build_config {
    runtime     = "python311"
    entry_point = "action_handler"
    source {
      storage_source {
        bucket = google_storage_bucket.source_bucket.name
        object = google_storage_bucket_object.source_object.name
      }
    }
  }

  service_config {
    max_instance_count = 10
    available_memory   = "8192M"
    timeout_seconds    = 540
    service_account_email = google_service_account.function_sa.email
    
    environment_variables = {
      ACTION_NAME        = var.action_name
      ACTION_LABEL       = var.action_label
      PROJECT            = var.project_id
      REGION             = var.region
      EMAIL_SENDER       = var.email_sender
      GEN2_ROUTER        = "true"
      MODEL_VARIANT      = var.model_variant
      MAILGUN_DOMAIN     = var.mailgun_domain
    }

    dynamic "secret_environment_variables" {
      for_each = local.secrets_list
      content {
        key        = secret_environment_variables.value.key
        project_id = secret_environment_variables.value.project_id
        secret     = secret_environment_variables.value.secret
        version    = secret_environment_variables.value.version
      }
    }
  }

  depends_on = [
    google_secret_manager_secret_version.looker_token_val,
    google_secret_manager_secret_version.mailgun_token_val,
    google_secret_manager_secret_version.sendgrid_key_val
  ]
}

# Public Access (Action Hub needs to be public to be reachable by Looker potentially, usually valid for these demos)
resource "google_cloud_run_service_iam_member" "public_invoker" {
  location = google_cloudfunctions2_function.function.location
  service  = google_cloudfunctions2_function.function.name
  role     = "roles/run.invoker"
  member   = "allUsers"
}
