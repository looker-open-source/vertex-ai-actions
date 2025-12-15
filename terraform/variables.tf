variable "project_id" {
  description = "The Google Cloud Project ID"
  type        = string
}

variable "region" {
  description = "The Google Cloud region to deploy to"
  type        = string
  default     = "us-central1"
}

variable "action_name" {
  description = "The name of the Cloud Function and Action"
  type        = string
  default     = "vertex-ai"
}

variable "action_label" {
  description = "The label for the Looker Action"
  type        = string
  default     = "Vertex AI"
}

variable "email_sender" {
  description = "Email address of the sender"
  type        = string
}

variable "model_variant" {
  description = "Default Vertex AI model to use"
  type        = string
  default     = "gemini-2.5-flash"
}

variable "looker_auth_token" {
  description = "Authentication token for Looker"
  type        = string
  sensitive   = true
}

variable "mailgun_api_token" {
  description = "Mailgun API Token (optional if using SendGrid)"
  type        = string
  sensitive   = true
  default     = ""
}

variable "mailgun_domain" {
  description = "Mailgun Domain (required if using Mailgun)"
  type        = string
  default     = ""
}

variable "sendgrid_api_key" {
  description = "SendGrid API Key (optional if using Mailgun)"
  type        = string
  sensitive   = true
  default     = ""
}
