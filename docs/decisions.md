# Decisions

- The local Cognito emulator is a minimal, local-only email/password service that issues short-lived JWTs with Cognito-style group claims; the API verifies them with a local-only signing key. The demo-user buttons are compiled into the local Vite configuration only; the API rejects demo sign-in when `LOCAL_DEV` is false. AWS deployments use Cognito User Pools.
- DynamoDB uses a single-table layout (`PK`/`SK`) plus three sparse GSIs: operational/support queues, field actions, and shipment lookup/open-case deduplication. Case components share the case partition for case detail reads.
- Failed-delivery reports use a simulated GPS distance of 18 m and server UTC timestamps. The report flow enforces three taps in under 15 seconds.
- The On Demand Delivery simulator is a Support-authenticated adapter to the same webhook service used by the shared-secret external webhook; the shared secret is never exposed to the browser.
- Customer messages are persisted to the case outbox only; this PoC does not integrate an SMS or email provider.
- Evidence uploads accept JPEG, PNG, and WebP files up to 10 MB each. The AWS evidence bucket is retained on stack deletion to avoid silently deleting uploaded photos.
- AWS demo users are not provisioned with reusable passwords. Create employee accounts through the deployed Cognito user pool; local demo credentials are deliberately limited to the local emulator.
