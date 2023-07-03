This guide will walk you through integrating Looker with Vertex AI via Cloud Functions using the Looker Action API. Users can use the Looker Explore to examine data, then send the Looker query to a Cloud Function, specifying the Vertex AI prompt and parameters on the form submissions.

There are three Cloud Functions included in this demo that are used to communicate from Looker to Vertex AI via the [Action API](https://github.com/looker-open-source/actions/blob/master/docs/action_api.md):

1. `action_list` - Lists the metadata for the action, including the form and execute endpoints
1. `action_form` - The dynamic form template to presented to users to send parameters to the execute endpoint.
1. `action_execute` - The function to run the prediction model on the data that is being sent, and send an email

## Installation:

_Before following the steps below, make sure you have enabled the [Secret Manager API](https://console.cloud.google.com/flows/enableapi?apiid=secretmanager.googleapis.com), [Cloud Build API](https://console.cloud.google.com/flows/enableapi?apiid=cloudbuild.googleapis.com), [Cloud Functions API](https://console.cloud.google.com/flows/enableapi?apiid=cloudfunctions.googleapis.com), and the [Vertex AI API](https://console.cloud.google.com/flows/enableapi?apiid=aiplatform.googleapis.com). It will take a few minutes after enabling this APIs for it to propagate through the systems._

_Also make sure you have a Sendgrid account and API key to use for sending emails. You can create a free developer account from the [GCP marketplace](https://console.cloud.google.com/marketplace/details/sendgrid-app/sendgrid-email)._

Use [Cloud Shell](https://cloud.google.com/shell) or the [`gcloud CLI`](https://cloud.google.com/sdk/docs/install) for the following steps.

The only variables you need to modify is the `PROJECT` ID you want to deploy the Cloud Functions to and the `EMAIL_SENDER`.

1. Set the variables below:

   ```
   ACTION_LABEL="Looker Vertex AI"
   ACTION_NAME="looker-vertex"
   REGION="us-central1"
   PROJECT="my-project-id"
   EMAIL_SENDER="my-sender-email-address@foo.com"

   ```

1. Clone this repo

   ```
   git clone https://github.com/davidtamaki/vertex-ai-actions.git
   cd vertex-ai-actions/
   ```

1. Create a [.env.yaml](.env.yaml.example) with variables:

   ```
   printf "ACTION_LABEL: ${ACTION_LABEL}\nACTION_NAME: ${ACTION_NAME}\nREGION: ${REGION}\nPROJECT: ${PROJECT}\nEMAIL_SENDER: ${EMAIL_SENDER}" > .env.yaml
   ```

1. Generate the LOOKER_AUTH_TOKEN secret. The auth token secret can be any randomly generated string. You can generate such a string with the openssl command:

   ```
   LOOKER_AUTH_TOKEN="`openssl rand -hex 64`"
   ```

1. Add the Auth Token and [Sendgird API key](https://app.sendgrid.com/settings/api_keys) as Secrets, then create a Service Account to run the Cloud Functions and give it access to the Secrets:

   ```
   SENDGRID_API_KEY="copy your sendgrid api key here"

   printf ${SENDGRID_API_KEY} | gcloud secrets create SENDGRID_API_KEY --data-file=- --replication-policy=user-managed --locations=${REGION} --project=${PROJECT}

   printf ${LOOKER_AUTH_TOKEN} | gcloud secrets create LOOKER_AUTH_TOKEN --data-file=- --replication-policy=user-managed --locations=${REGION} --project=${PROJECT}

   gcloud iam service-accounts create vertex-ai-actions-cloud-functions --display-name="Vertex AI Actions Cloud Functions" --project=${PROJECT}

   SERVICE_ACCOUNT_EMAIL=vertex-ai-actions-cloud-functions@${PROJECT}.iam.gserviceaccount.com

   eval gcloud projects add-iam-policy-binding ${PROJECT} --member=serviceAccount:${SERVICE_ACCOUNT_EMAIL} --role='roles/cloudfunctions.invoker'

   eval gcloud projects add-iam-policy-binding ${PROJECT} --member=serviceAccount:${SERVICE_ACCOUNT_EMAIL} --role='roles/secretmanager.secretAccessor'

   eval gcloud projects add-iam-policy-binding ${PROJECT} --member=serviceAccount:${SERVICE_ACCOUNT_EMAIL} --role='roles/aiplatform.user'

   eval gcloud secrets add-iam-policy-binding SENDGRID_API_KEY --member=serviceAccount:${SERVICE_ACCOUNT_EMAIL} --role='roles/secretmanager.secretAccessor' --project=${PROJECT}

   eval gcloud secrets add-iam-policy-binding LOOKER_AUTH_TOKEN --member=serviceAccount:${SERVICE_ACCOUNT_EMAIL} --role='roles/secretmanager.secretAccessor' --project=${PROJECT}
   ```

1. Deploy 3 cloud functions for action hub listing, action form, and action execute (this may take a few minutes):

   ```
   gcloud functions deploy looker-vertex-list --entry-point action_list --env-vars-file .env.yaml --trigger-http --runtime=python311 --allow-unauthenticated --timeout=540s --region=${REGION} --project=${PROJECT} --service-account ${SERVICE_ACCOUNT_EMAIL} --set-secrets 'LOOKER_AUTH_TOKEN=LOOKER_AUTH_TOKEN:latest'

   gcloud functions deploy looker-vertex-form --entry-point action_form --env-vars-file .env.yaml --trigger-http --runtime=python311 --allow-unauthenticated --timeout=540s --region=${REGION} --project=${PROJECT} --service-account ${SERVICE_ACCOUNT_EMAIL} --set-secrets 'LOOKER_AUTH_TOKEN=LOOKER_AUTH_TOKEN:latest'

   gcloud functions deploy looker-vertex-execute --entry-point action_execute --env-vars-file .env.yaml --trigger-http --runtime=python311 --allow-unauthenticated --timeout=540s --region=${REGION} --project=${PROJECT} --service-account ${SERVICE_ACCOUNT_EMAIL} --set-secrets 'LOOKER_AUTH_TOKEN=LOOKER_AUTH_TOKEN:latest,SENDGRID_API_KEY=SENDGRID_API_KEY:latest'
   ```

1. Copy the Action Hub URL (`action_list` endpoint) and the `LOOKER_AUTH_TOKEN` to input into Looker:

   ```
   echo Action Hub URL: https://${REGION}-${PROJECT}.cloudfunctions.net/${ACTION_NAME}-list
   echo LOOKER_AUTH_TOKEN: $LOOKER_AUTH_TOKEN
   ```

1. In Looker, go to the **Admin > Actions** page and click **Add Action Hub**

   - Enter the Action Hub URL
   - click **Configure Authorization** and enter the `LOOKER_AUTH_TOKEN` value for the Authorization Token and click **Enable**
   - Toggle the **Enabled** button and click **Save**

## Troubleshooting:

If the action build fails, you will receive an email notification. Go to the **Admin > Scheduler History** page to view the error message returned from the Action or use `scheduled_plan` System Activity Explore:

- <details><summary> Explore query to see details on action executions: </summary>

  `https://${YOUR_LOOKER_DOMAIN}.com/explore/system__activity/scheduled_plan?fields=scheduled_job.id,scheduled_job.created_time,scheduled_plan_destination.action_type,scheduled_plan_destination.format,scheduled_job.status,scheduled_plan.run_once,scheduled_plan_destination.parameters,scheduled_job.status_detail&f[scheduled_plan_destination.action_type]=looker-vertex&sorts=scheduled_job.created_time+desc&limit=500&vis=%7B%7D&filter_config=%7B%22scheduled_plan_destination.action_type%22%3A%5B%7B%22type%22%3A%22%3D%22%2C%22values%22%3A%5B%7B%22constant%22%3A%22looker-vertex%22%7D%2C%7B%7D%5D%2C%22id%22%3A1%2C%22error%22%3Afalse%7D%5D%7D&dynamic_fields=%5B%7B%22measure%22%3A%22sum_of_runtime_in_seconds%22%2C%22based_on%22%3A%22scheduled_job_stage.runtime%22%2C%22expression%22%3A%22%22%2C%22label%22%3A%22Sum+of+Runtime+in+Seconds%22%2C%22type%22%3A%22sum%22%2C%22_kind_hint%22%3A%22measure%22%2C%22_type_hint%22%3A%22number%22%7D%5D&origin=share-expanded`

  </details>
