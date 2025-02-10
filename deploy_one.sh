# Usage: bash deploy_one.sh

# Set Environment Variables
ACTION_LABEL="Salesforce Campaign Creator POC"
ACTION_NAME="salesforce-campaign-creator-poc"
REGION="asia-southeast1"
PROJECT="joon-sandbox"
                      # todo: change this to the service account email
SERVICE_ACCOUNT_EMAIL=vertex-ai-cloud-function-demo@${PROJECT}.iam.gserviceaccount.com
# LOOKER_AUTH_TOKEN="6d93f59f7be2969506d89a17eb9efd6c922e337e7b1e86b8fae8311f4b7643ad6abcb4d760bd7902c84aecf5c0d50e2ac56d10a5a4a277ec20a62c8b36d61473"
CLIENT_ID="3MVG9IUPIoRCZley1WC3YN5_t76aAzWV3gHHRnhm3Nn.MEqnhwJPkihZRAq_JLx8U6LQKP5Liz9lyLsni1nPb"
CLIENT_SECRET="D710DA7721CF3F592EB6CD84301678575E872323EC9B1069411ECE940A10A7E2"
USERNAME="oneforce.integration@one-line.com.ofuat"
PASSWORD="Oneline2025!4cax8fezssoeRSLB9oEvsRjnu"


# Create .env.yaml
printf "ACTION_LABEL: ${ACTION_LABEL}\nACTION_NAME: ${ACTION_NAME}\nREGION: ${REGION}\nPROJECT: ${PROJECT}" > .env.yaml

# Create Secret Manager for Looker Auth Token
# printf ${LOOKER_AUTH_TOKEN} | gcloud secrets create LOOKER_AUTH_TOKEN --data-file=- --replication-policy=user-managed --locations=${REGION} --project=${PROJECT}
# printf ${CLIENT_ID} | gcloud secrets create CLIENT_ID --data-file=- --replication-policy=user-managed --locations=${REGION} --project=${PROJECT}
# printf ${CLIENT_SECRET} | gcloud secrets create CLIENT_SECRET --data-file=- --replication-policy=user-managed --locations=${REGION} --project=${PROJECT}
# printf ${USERNAME} | gcloud secrets create USERNAME --data-file=- --replication-policy=user-managed --locations=${REGION} --project=${PROJECT}
# printf ${PASSWORD} | gcloud secrets create PASSWORD --data-file=- --replication-policy=user-managed --locations=${REGION} --project=${PROJECT}

# deploy cloud functions
gcloud functions deploy ${ACTION_NAME}-list --entry-point action_list --env-vars-file .env.yaml --trigger-http --runtime=python311 --allow-unauthenticated --no-gen2 --memory=1024MB --timeout=540s --region=${REGION} --project=${PROJECT} --service-account ${SERVICE_ACCOUNT_EMAIL} --set-secrets 'LOOKER_AUTH_TOKEN=LOOKER_AUTH_TOKEN:latest'
gcloud functions deploy ${ACTION_NAME}-form --entry-point action_form --env-vars-file .env.yaml --trigger-http --runtime=python311 --allow-unauthenticated --no-gen2 --memory=1024MB --timeout=540s --region=${REGION} --project=${PROJECT} --service-account ${SERVICE_ACCOUNT_EMAIL} --set-secrets 'LOOKER_AUTH_TOKEN=LOOKER_AUTH_TOKEN:latest'
gcloud functions deploy ${ACTION_NAME}-execute --entry-point action_execute --env-vars-file .env.yaml --trigger-http --runtime=python311 --allow-unauthenticated --no-gen2 --memory=8192MB --timeout=540s --region=${REGION} --project=${PROJECT} --service-account ${SERVICE_ACCOUNT_EMAIL} --set-secrets 'LOOKER_AUTH_TOKEN=LOOKER_AUTH_TOKEN:latest,SALESFORCE_CLIENT_ID=SALESFORCE_CLIENT_ID:latest,SALESFORCE_CLIENT_SECRET=SALESFORCE_CLIENT_SECRET:latest,SALESFORCE_USERNAME=SALESFORCE_USERNAME:latest,SALESFORCE_PASSWORD=SALESFORCE_PASSWORD:latest'
