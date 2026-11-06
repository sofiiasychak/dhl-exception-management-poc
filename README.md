# Exception Management · student concept

A clickable proof of concept for coordinating shipment exceptions across courier, Operations,
Support, and depot roles. It uses fictional seed data only; it is not a DHL product and does not
connect to DHL systems.

## Public demo

The GitHub Pages deployment is pending repository authorization. When available, the public link
will be added here.

Choose **Thomas A. · Courier** to start the six-step flow. Use the collapsible Demo guide to move
between roles:

1. **Thomas A. · Courier:** report a failed delivery from stop 6. Choose a reason and submit.
2. **Marta L. · Operations:** assign the redelivery to the route courier.
3. **Kateryna B. · Support:** send one customer update using the prepared template.
4. **Customer choice:** open `/simulator` and submit a redelivery slot.
5. **Thomas A. · Courier:** mark the redelivery delivered.
6. **Marta L. · Operations:** resolve the case.

The demo API runs in the browser. Seed data and workflow changes stay in that browser's
`localStorage`; **Reset demo data** restores the original fixture. No messages are actually sent.

## Run locally

1. Copy `.env.example` to `.env` if you intend to deploy to AWS. Do not commit `.env`.
2. Install Docker with Compose and GNU Make.
3. Run `make up`, then `make seed`.
4. Open <http://localhost:5173>. Local sign-in shows fictional demo users. API docs are at
   <http://localhost:8000/docs>.
5. Run `make test`; stop the stack with `make down`.

The Docker Compose app uses FastAPI, DynamoDB Local, and a local Cognito-compatible emulator.
The public, static demo is separate and does not require installing anything.

## Verify and publish

- `make test` runs backend pytest tests, frontend type checking, and the production build.
- GitHub Actions builds the frontend with `DEMO_MODE=true` and deploys it to GitHub Pages on
  pushes to `main`.
- The public demo uses no AWS credentials, API secrets, real customer data, or third-party
  messaging services.

## Take down

- Stop the local stack with `make down`.
- To unpublish the hosted demo, open the repository's **Settings → Pages** and disable the Pages
  site. The committed source and demo data fixtures remain available in the repository.
