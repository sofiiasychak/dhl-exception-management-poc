# Decisions

- The local Cognito emulator is a small, local-only OIDC-compatible service used by the same email/password sign-in flow. The demo-user buttons are compiled into the local Vite configuration only; the API rejects demo sign-in when `LOCAL_DEV` is false. AWS deployments use Cognito User Pools.
- DynamoDB uses a single-table layout (`PK`/`SK`) plus three sparse GSIs: operational/support queues, field actions, and shipment lookup/open-case deduplication. Case components share the case partition for case detail reads.
- The foundation includes role-specific empty destinations and API/data/auth scaffolding, but not the workflows or screens described as the next build step in `PROMPTS.md`.
- AWS demo users are not provisioned with reusable passwords. Create employee accounts through the deployed Cognito user pool; local demo credentials are deliberately limited to the local emulator.
