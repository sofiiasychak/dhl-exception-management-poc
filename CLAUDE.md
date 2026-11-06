# Exception Management Platform PoC

## Run locally

1. Copy `.env.example` to `.env` and set `AWS_PROFILE` / `AWS_REGION` only if you intend to deploy.
2. Install Docker with Compose and GNU Make.
3. Run `make up`, then `make seed`.
4. Open http://localhost:5173. Local sign-in shows one button for each fictional demo user. API docs are at http://localhost:8000/docs.
5. Run `make test`; stop the stack with `make down`.

The local Compose stack contains Vite/React, FastAPI, DynamoDB Local, and the local Cognito-compatible emulator. Local demo sign-in is never enabled in an AWS deployment.

## Test and deploy

- `make test`: backend pytest rules/API tests plus frontend TypeScript and production build checks.
- `make deploy`: build and upload the Lambda package, deploy `infra/template.yaml` with CloudFormation in `AWS_REGION` (default `eu-central-1`), then publish the static site.
- `make destroy`: delete the CloudFormation stack. S3 buckets may need manual emptying if deployment populated them; the command explains this rather than deleting user data.
- AWS deployment requires the AWS CLI, Docker, and configured credentials for the selected `AWS_PROFILE`.

## Conventions

- `docs/spec.md` is authoritative. Record uncovered choices in `docs/decisions.md`.
- Keep business rules in `backend/app/core/` framework- and AWS-independent.
- Keep each API feature in its own router/service/repository module and test role boundaries.
- Store case history, actions, and messages under the case partition; design indexes for the documented query patterns.
- Keep role authorization in API dependencies, not merely in frontend routing.
- Keep the initial UI to sign-in, role-based navigation/layout, and empty role pages.

## No-go zones

- No DHL logos, branding, or copied images.
- Never put customer names, addresses, contact details, or message bodies in logs or analytics; IDs only.
- No AI making decisions.
- Do not guess against `docs/spec.md`.
