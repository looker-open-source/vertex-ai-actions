# Usage: bash deploy.sh

# Set Environment Variables
ACTION_LABEL="Becky Campaign Creator"
ACTION_NAME="becky-campaign-creator"
REGION="asia-southeast1"
PROJECT="joon-sandbox"
                      # todo: change this to the service account email
SERVICE_ACCOUNT_EMAIL=vertex-ai-cloud-function-demo@${PROJECT}.iam.gserviceaccount.com



# Create .env.yaml
printf "ACTION_LABEL: ${ACTION_LABEL}\nACTION_NAME: ${ACTION_NAME}\nREGION: ${REGION}\nPROJECT: ${PROJECT}" > .env.yaml

# Create Secret Manager for Looker Auth Token
# printf ${LOOKER_AUTH_TOKEN} | gcloud secrets create LOOKER_AUTH_TOKEN --data-file=- --replication-policy=user-managed --locations=${REGION} --project=${PROJECT}

# deploy cloud functions
gcloud functions deploy ${ACTION_NAME}-list --entry-point action_list --env-vars-file .env.yaml --trigger-http --runtime=python311 --allow-unauthenticated --no-gen2 --memory=1024MB --timeout=540s --region=${REGION} --project=${PROJECT} --service-account ${SERVICE_ACCOUNT_EMAIL} --set-secrets 'LOOKER_AUTH_TOKEN=LOOKER_AUTH_TOKEN:latest'
# gcloud functions deploy ${ACTION_NAME}-form --entry-point action_form --env-vars-file .env.yaml --trigger-http --runtime=python311 --allow-unauthenticated --no-gen2 --memory=1024MB --timeout=540s --region=${REGION} --project=${PROJECT} --service-account ${SERVICE_ACCOUNT_EMAIL} --set-secrets 'LOOKER_AUTH_TOKEN=LOOKER_AUTH_TOKEN:latest'
# gcloud functions deploy ${ACTION_NAME}-execute --entry-point action_execute --env-vars-file .env.yaml --trigger-http --runtime=python311 --allow-unauthenticated --no-gen2 --memory=8192MB --timeout=540s --region=${REGION} --project=${PROJECT} --service-account ${SERVICE_ACCOUNT_EMAIL} --set-secrets 'LOOKER_AUTH_TOKEN=LOOKER_AUTH_TOKEN:latest'

# gcloud functions deploy ${ACTION_NAME}-print-me-form --entry-point action_print_me_form --env-vars-file .env.yaml --trigger-http --runtime=python311 --allow-unauthenticated --no-gen2 --memory=1024MB --timeout=540s --region=${REGION} --project=${PROJECT} --service-account ${SERVICE_ACCOUNT_EMAIL} --set-secrets 'LOOKER_AUTH_TOKEN=LOOKER_AUTH_TOKEN:latest'
# gcloud functions deploy ${ACTION_NAME}-print-me-execute --entry-point action_print_me_execute --env-vars-file .env.yaml --trigger-http --runtime=python311 --allow-unauthenticated --no-gen2 --memory=8192MB --timeout=540s --region=${REGION} --project=${PROJECT} --service-account ${SERVICE_ACCOUNT_EMAIL} --set-secrets 'LOOKER_AUTH_TOKEN=LOOKER_AUTH_TOKEN:latest'
# gcloud functions deploy ${ACTION_NAME}-print-me-oauth-redirect --entry-point action_print_me_oauth_redirect --env-vars-file .env.yaml --trigger-http --runtime=python311 --allow-unauthenticated --no-gen2 --memory=8192MB --timeout=540s --region=${REGION} --project=${PROJECT} --service-account ${SERVICE_ACCOUNT_EMAIL} --set-secrets 'LOOKER_AUTH_TOKEN=LOOKER_AUTH_TOKEN:latest'
