# Claude Code prompts for the PoC (A5)

Paste one prompt at a time, in order. Wait until Claude Code finishes, run the app, then go to the next one.
Short on time? Prompts 1–3 give a working, styled prototype; 4 and 5 add analytics, tests and deployment.

---

## Prompt 1: Foundation (stack, data, sign-in, local run)

```
Read docs/spec.md and look at the images in docs/wireframes and docs/diagrams. docs/spec.md is the source of truth; if something is unclear, choose the simplest option and write it down in docs/decisions.md.

Build a simple web app: an internal exception-management platform where Operations, Support, couriers and depot staff work on one shared case per shipment problem. After signing in, each user sees and does only what their role allows (spec §1, R4, R11).

In this step build the foundation, not the screens:
- Backend: Python, FastAPI on Lambda (Mangum) behind API Gateway HTTP API. Feature folders (cases, communication, field, webhooks, auth), each with router, service, repository and tests. Business rules R1–R11 live in a core package with no AWS imports and are covered by pytest unit tests.
- Database: DynamoDB, designed for the access patterns in spec §4. A seed script with the demo data in spec §7; running it again wipes and reloads the demo.
- Sign-in: Cognito, email and password, one group per role (ops, support, courier, depot). The API checks the JWT and the group on every endpoint.
- Frontend: Vite, React, TypeScript, stock shadcn/ui components with no custom design. For now only: sign-in, role-based routing (web layout for ops and support, phone-width field app for courier and depot) and an empty page per role.
- Infrastructure: everything defined in CloudFormation: S3 + CloudFront for the site with /api/* routed to API Gateway, Lambda, DynamoDB, Cognito. Region eu-central-1.
- Folders: backend, frontend, infra, docs.
- Local run: Docker Compose runs everything locally, including DynamoDB Local and a Cognito emulator. Add a test sign-in available only locally: one button per demo user from spec §7.
- Makefile: help, up, down, seed, test, deploy, destroy. AWS profile and region in .env; add .env.example and never commit .env.
- CLAUDE.md: how to run, test and deploy; conventions; no-go zones: no DHL logos or images, no personal customer data in logs or analytics (IDs only), no AI making decisions, docs/spec.md wins over guesses.

Done when: make up starts the stack, make seed loads the demo, the test sign-in opens the right empty page for each demo user, and make test passes. Then git init (if needed) and commit. Tell me the commands to run and anything you could not finish.
```

---

## Prompt 2: Screens and the critical flow

```
Build the critical flow from docs/spec.md §2 end to end, using the wireframes in docs/wireframes (and notes.md) for structure, labels and content. Stock shadcn/ui only, no custom design yet. Every screen reads and writes through the real API; nothing is hard-coded.

Operations (web):
- Cases queue (S2): tabs mine / unassigned / overdue / all open; filters type, priority, region, status; High first, then least time left; "New case assigned to you" banner; refresh every 10 s.
- Case card (S3): shipment, timeline, "Why High?" with the rule and Change priority (reason required), Next action (type + responsible) → Assign action, customer status, Reassign case owner.
- Resolve (S6): outcome, root cause, time to resolve against 48 h, send-confirmation toggle; a resolved case can be reopened.

Support (web):
- Customer updates (S4): queues not informed / waiting for customer / confirm resolution; read-only case summary; Notify customer with channels, the template picked from the type, a preview filled from the case (editable), the duplicate check (R9), the "customer hasn't contacted us yet" indicator, Send and Escalate to Operations.
- Shipment lookup by number.

Courier (phone width):
- My actions (S5): today's actions in route order, the customer's chosen slot on the redelivery, Delivered, Can't deliver.
- Report failed delivery (S1): Can't deliver → reason → Report, exactly 3 taps from the stop; simulated GPS distance and time attached; optional photo; 10-second Undo; confirmation with the case id.

Depot (phone width):
- Scan or type a parcel number → Report damage (S7): damage types, at least one photo (file input; local storage in Docker, S3 in AWS), contents checked, note → creates a Damaged parcel case.

On Demand Delivery simulator: the /simulator page from spec §8.

On a desktop, show the field app inside a centred 390 px phone frame. Disabled "later" menu items as in the IA.

Done when I can run the whole flow of spec §2 in two browser windows (courier in one, Ops and Support in the other) and every step appears in the case timeline. Add pytest API tests for each step of the flow, run make test, then commit.
```

---

## Prompt 3: DHL style

```
Restyle the UI after https://www.dhl.com/ua-uk/home.html: colours, fonts, buttons, layout. Keep the logic unchanged and do not use other brands' logos.

Details:
- Look at the page yourself. Take the style, not the brand: no DHL logo, no images or text from the site. Where the wireframes show LOGO, write "Exception Management" in text.
- Put the palette in design tokens (CSS variables and the Tailwind theme behind shadcn/ui): yellow #FFCC00 for the top bar and highlight bands, always with black text; red #D40511 for primary buttons, links and the High chip, with white text; white cards on a light grey page #F2F2F2; text #1A1A1A, secondary text #595959, borders #D1D1D1. Medium = yellow chip with black text, Low = grey chip. Priority and status keep their text labels.
- Font: DHL's own typeface is not free, so use a free humanist sans with Cyrillic, self-hosted through @fontsource (for example Source Sans 3), with bold headlines.
- Buttons and cards in the spirit of the reference: small corner radius (about 4 px), bold labels, generous white space. In the courier and depot screens keep the main buttons large (at least 52 px high) and at the bottom, in thumb reach.
- Add a small permanent label in the footer of the web app and under the phone frame: "Student concept · not a DHL product".
- Accessibility: text contrast at least 4.5:1, visible focus states, touch targets at least 44 px.

Then take Playwright screenshots of the screens that match S1–S7 into docs/screenshots, compare them with docs/wireframes and fix anything that broke. The logic and the API stay exactly the same: make test must still pass. Commit.
```

---

## Prompt 4: Tracking plan

```
Add the product-analytics tracking plan from docs/spec.md §5: exactly those 10 events with those properties and the same names on the web app, the field app and the backend.

- Every event also carries timestamp, user_id (or "system"), user_role and region. IDs only: never names, addresses, phone numbers, emails or message text.
- The backend emits each event as one structured JSON log line (CloudWatch in AWS) and stores it in DynamoDB. The frontend sends its UI events (case_viewed with load_time_ms; failed_delivery_reported with taps_count and duration_sec) to one API endpoint.
- Add an Ops-only page "Event log (PoC check)" that lists the latest events and shows two numbers computed from them: the funnel from spec §5 (how many cases reached each step) and the North Star for this week.
- Tests: run the critical flow through the API and assert that all 10 events fire with the right properties and that the funnel counts match.

Run make test and commit.
```

---

## Prompt 5: Check, clean up, deploy

```
Check the PoC, clean it up and deploy it.

1. Write a Playwright end-to-end test of the critical flow in spec §2 across roles: the courier reports in 3 taps → Ops sees the case and assigns the redelivery → Support sends one message → the simulator sends the customer's choice → the courier marks it delivered → Ops resolves it on time. Also test that a second message with the same template is blocked, that a second report for the same shipment is added to the open case, and that Support gets 403 when it tries to assign or reassign. Run all tests and fix what fails.
2. Review the code as a strict reviewer: remove dead code and unused dependencies, confirm every endpoint checks the role, no personal data in logs or events, no secrets in the repository. List what you changed.
3. Update README.md: what the PoC is, how to run it (make up, make seed, make test), a 3-minute demo script (who clicks what, in which window), and a table mapping code modules to the C4 level 3 components in docs/diagrams.
4. If an AWS profile is set in .env: make deploy to eu-central-1, create one Cognito user per demo user with a temporary password and print them, print the CloudFront URL, and add an AWS Budgets alert at $5. If not, skip this step and tell me what to set up.

Commit, and remind me that make destroy removes everything from AWS after the demo.
```
