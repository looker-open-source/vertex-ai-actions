import {
  id = "projects/${var.project_id}/serviceAccounts/vertex-looker@${var.project_id}.iam.gserviceaccount.com"
  to = google_service_account.function_sa
}

import {
  id = "projects/${var.project_id}/secrets/LOOKER_AUTH_TOKEN"
  to = google_secret_manager_secret.looker_token
}

import {
  id = "projects/${var.project_id}/secrets/MAILGUN_API_TOKEN"
  to = google_secret_manager_secret.mailgun_token[0]
}

# Optional: If you also need to import the SendGrid key, uncomment/add below when relevant
# import {
#   id = "projects/${var.project_id}/secrets/SENDGRID_API_KEY"
#   to = google_secret_manager_secret.sendgrid_key[0]
# }
