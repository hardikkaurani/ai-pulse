# From demonstration to a limited client pilot

The current build supports a local synthetic demonstration. Moving to real employee data needs decisions and operational evidence, not additional dashboard features.

## First agree on the data boundary

Confirm employee consent and purpose, what deletion includes, whether department names may be shown, acceptable refresh delay, and how long provider systems and backups retain data. Confirm the client accepts the residual inference risks of threshold suppression. Do not describe the score as validated for employment decisions.

## Then validate the selected model

Run the ten synthetic smoke cases with the intended model and record the actual results. Add independently labelled examples with domain reviewers, including negation, mixed safe and unsafe behaviour, multilingual answers and adversarial instructions. Inspect disagreements instead of tuning only to a small known set. Retain model and rubric versions when making changes.

## Prepare the deployment

Use HTTPS, a secret manager, real identity provisioning, restricted database access and a tested backup/restore procedure. Remove synthetic accounts from the real environment. Define account deletion and provider-erasure procedures. Add security-relevant audit events without storing raw employee answers in logs.

For multiple workers, replace process-local rate limits with a shared limiter. Move scoring to durable jobs when throughput or automatic recovery requires it. Test deletes, retries and old-job completion again in that architecture.

## Run a deliberately small pilot

Use a consenting cohort, explain exactly who can see which outputs, and collect feedback on question clarity and activity usefulness. Track operational failures and completion friction. Evaluate whether the activities help people, rather than equating checkbox completion with improved AI capability.
