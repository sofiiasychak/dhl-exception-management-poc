# Exception Management Platform — PoC spec

Source of truth for the proof of concept. If this file and a guess disagree, this file wins.
If something is not covered, pick the simplest option and record it in `docs/decisions.md`.

## 0. What this is

A student project (system analysis course) for DHL Express: a clickable proof of concept of an
internal platform that turns shipment problems into one shared case with a type, priority, owner
and action history, so Support can inform the customer before they call.

- It is a concept, not a DHL product. No DHL logos, no images or text copied from DHL sites.
- No access to DHL systems or data: all data is mock data (spec §7). People are fictional.
- English UI.

## 1. Users and apps

| Role | App | Job |
|---|---|---|
| Operations (ops) | Web, desktop | Owns and coordinates every case; the only role that assigns and reassigns |
| Support | Web, desktop | Keeps the customer informed; read-only on the case except messaging |
| Courier | Field app, phone width | Does delivery actions; reports failed deliveries |
| Depot | Field app, phone width | Handles parcels; reports damage |
| Customer | **Not a user** | Gets SMS/email (mocked) and picks a new delivery in On Demand Delivery (existing DHL system, simulated here) |

In the PoC the field app is the same React app shown at phone width (target per C4: React Native).

## 2. Critical flow (must work end to end)

1. **Courier reports (S1).** At a stop: *Can't deliver* → reason (*Not at home*, *Address wrong or
   incomplete*, *Recipient refused*, *No access to the building*, *Other + note*) → *Report*.
   Exactly 3 taps from the stop screen. GPS distance and time are attached automatically (simulate the
   location), photo optional, *Undo* for 10 s, then a confirmation with the case id.
2. **Platform (automatic, no human).** Creates a case linked to the shipment (or adds to the open
   case for the same shipment and type, R1), type = failed delivery, priority by rule (R3), owner =
   the Ops user of the shipment's region (R4). The case enters Support's *Not informed* queue.
   Target < 5 min (NFR-5); in the PoC it is immediate.
3. **Ops picks it up (S2 → S3).** Queue shows it with a *New case assigned to you* banner. Case card:
   shipment, timeline, *Why High?* (the rule that fired), next action (*Redelivery* → the route's
   courier) → *Assign action*. Status *New → In progress*.
4. **Support informs (S4), in parallel with 3.** Opens the case from *Not informed*; sends **one**
   message (SMS + email) from the template for the type: reason + link to delivery options + the
   return-to-sender date. Duplicate check (R9). Shows whether the customer has contacted us. Status
   → *Waiting for customer*.
5. **Customer chooses (no screen of ours).** On Demand Delivery sends the choice to our webhook
   (simulated, §8). The platform records it and puts the slot on the courier's redelivery action.
   Status → *In progress*. No choice in 5 business days → return to sender (R7).
6. **Courier redelivers (S5).** *My actions* shows the redelivery with the customer's slot first.
   *Delivered* (1 tap) closes the action. *Can't deliver* goes back to step 1; on attempt 3 the next
   action becomes *Return to sender*.
7. **Ops resolves (S6).** Outcome, root cause, time to resolve against 48 h, *Send confirmation to the
   customer* (Support's template). Status → *Resolved*. A resolved case can be reopened (counted).

Also: **Depot reports damage (S7).** Scan or type a parcel number → damage types (multi-select), at
least one photo, contents checked yes/no, optional note → creates a *Damaged parcel* case for Ops
(duplicate check by shipment, R1).

## 3. Business rules (backend core, no AWS imports, unit-tested)

- **R1** Every case links to exactly one shipment. One open case per shipment and type: a new report
  for it is added to the open case's timeline instead of creating a second case.
- **R2** Types: `delay`, `failed_delivery`, `damaged_parcel`, `customs_hold`.
- **R3** Priority, first match wins: P1 key-account shipment → High; P2 time-definite product → High;
  P3 second or later failed attempt → High; P4 delay that still meets the promised delivery date →
  Low; otherwise Medium. Store the rule id and `set_by = auto`. Ops can change it with a mandatory
  reason (`set_by = user`), written to the timeline.
- **R4** Owner: at creation, auto-assign the Ops user of the shipment's region
  (`assignment_type = auto`). Only Ops assigns actions and reassigns the owner; Support, Courier and
  Depot can only *escalate to Operations*.
- **R5** Statuses: `new`, `in_progress`, `waiting_for_customer`, `waiting_for_customs`, `resolved`.
  Every status change writes a timeline entry: old and new status, actor (user or `system`), time.
- **R6** Target: resolve within 48 h. `deadline = created_at + 48h`;
  `resolved_on_time = resolved_at <= deadline`. Queues show time left; overdue in bold.
- **R7** Failed delivery: at most 3 attempts. After a failed attempt the return-to-sender date is
  5 business days later unless the customer chooses an option.
- **R8** GPS check: a courier report more than 150 m from the address is flagged on the case for Ops.
- **R9** Customer messages are sent only by Support (and by the resolve confirmation, using Support's
  template). The same template cannot be sent for the same case twice within 24 h: block it with a
  clear message. Store channel(s), template, body, sender, time.
  `notified_before_customer_contact = yes` if no inbound customer contact was recorded before sending.
- **R10** Support queues: `not_informed` (no message yet), `waiting_for_customer`,
  `confirm_resolution` (resolved, confirmation not sent yet). High first, then oldest.
- **R11** Role checks happen in the API on every endpoint, not only in the UI. Field users see only
  actions assigned to them.

## 4. Data: access patterns (DynamoDB)

Design the table(s) for these access patterns, not for entities:

- **A1** Get a case with its timeline, actions and messages.
- **A2** Ops queue: open cases by owner, High first then deadline; tabs *mine / unassigned / overdue /
  all open*; filters type, priority, region, status.
- **A3** Support queues by state (R10), High first then oldest.
- **A4** A field user's actions for today, in route order.
- **A5** Open case by shipment + type (R1 duplicate check).
- **A6** Shipment by number (lookup, scan).

Entities: Shipment (number, product, key_account, origin, destination, recipient name and masked
phone/email, address, region, route, stop), Case, TimelineEntry, Action (type, assignee, status,
slot), Message, FieldReport (reason, gps_distance_m, photo, taps_count, duration_sec), TrackingEvent,
User (name, role, region or route).

## 5. Tracking plan (exactly these 10 events, same names on web, field app and backend)

| # | Event | When | Properties |
|---|---|---|---|
| 1 | `exception_case_created` | a new case appears | case_id, shipment_id, exception_type, detection_method |
| 2 | `exception_priority_set` | High/Medium/Low set | case_id, priority, set_by (auto/user) |
| 3 | `case_owner_assigned` | a person or team is assigned | case_id, owner_role, assignment_type (auto/manual), seconds_since_created |
| 4 | `case_viewed` | a user opens the case view | case_id, user_role, load_time_ms |
| 5 | `failed_delivery_reported` | courier reports in the field app | case_id, taps_count, duration_sec, photo_attached |
| 6 | `case_action_updated` | an action is added or completed | case_id, action_type, user_role, action_status |
| 7 | `case_status_changed` | status changes | case_id, old_status, new_status, changed_by_role |
| 8 | `customer_notified` | Support sends a message | case_id, channel, notified_before_customer_contact, seconds_since_created |
| 9 | `resolution_option_recorded` | the customer's choice is saved | case_id, option_type |
| 10 | `case_resolved` | case marked resolved | case_id, exception_type, resolution_minutes, resolved_on_time, reopened |

Every event also has `timestamp`, `user_id` (or `system`), `user_role`, `region`.
IDs only: never names, addresses, phone numbers, emails or message text.
Funnel: created → priority_set → owner_assigned → action_updated → customer_notified → resolved.
North Star: cases per week with `resolved_on_time = yes` AND `notified_before_customer_contact = yes`.

## 6. NFRs the PoC must respect

- **NFR-1** Case view loads in < 2 s: measure `load_time_ms` in `case_viewed`.
- **NFR-3** Role-based access on the API; Cognito user pool with optional TOTP MFA. The test sign-in
  exists only locally.
- **NFR-4** Courier failed-delivery report in ≤ 3 taps and < 15 s: record `taps_count` and
  `duration_sec`.
- **NFR-5** Every new exception gets a case and an owner in < 5 min: record `seconds_since_created`.
- Accessibility: real `<button>`, `<input>` and `<label>`, touch targets ≥ 44 px (main field-app
  buttons ≥ 52 px), text contrast ≥ 4.5:1, priority and status always shown as text, not colour only.

## 7. Demo data (seed; `make seed` wipes and reloads it)

Times are relative to "now" when seeding. All people are fictional.

Users: **Marta L.** (ops, region Kyiv-East), **Oleh S.** (ops, Kyiv-West), **Kateryna B.** (support),
**Thomas A.** (courier, route K-14, Kyiv-East), **Ivan S.** (courier, route K-09, Kyiv-East),
**Anna K.** (depot, Kyiv Hub).

Open cases (owner Marta L. unless noted):

| Case | Type | Priority (rule) | Shipment | Status | Next action with | Customer informed | Created |
|---|---|---|---|---|---|---|---|
| EX-10458 | customs hold | High (P1) | 7710389245 | waiting_for_customs | Customs broker | yes | now − 50 h (overdue) |
| EX-10463 | failed delivery | Medium | 5127704361 | waiting_for_customer | Customer (choosing) | yes | now − 30 h |
| EX-10466 | delay | Medium | 3398016627 | in_progress | Linehaul · Warsaw hub | yes | now − 26 h |
| EX-10471 | damaged parcel | High (P2) | 6620145873 | in_progress | Depot · Kyiv Hub (Anna K.) | yes | now − 17 h |
| EX-10477 | delay | Low (P4) | 9054127738 | in_progress | Courier Ivan S. | yes | now − 8 h |
| EX-10480 | damaged parcel | Medium | 2261907345 | new | — | no | now − 9 min |
| EX-10481 | delay | Medium | 8840512276 | new | — | no | now − 4 min |

The next new case gets **EX-10482**.

Thomas A.'s route K-14 today: 23 stops. **Stop 6** is shipment **4836201759**, recipient
*O. Hrytsenko*, *vul. Sadova 14, apt 9, Kyiv*, phone `+380 •• ••• 41 27`, product
*Time-definite · by 12:00*, not attempted yet, region Kyiv-East. The live demo starts here.
Add a few ordinary stops around it (e.g. *vul. Lisova 7*, *vul. Zelena 21, office 4*, *vul. Sadova 30*).

## 8. Integrations in the PoC

- **On Demand Delivery** (existing DHL system): a webhook endpoint receives the customer's choice.
  A separate page `/simulator`, clearly labelled *Simulator: stands in for On Demand Delivery*, lists
  cases waiting for the customer and posts a choice (redelivery slot or pickup point) to the webhook,
  with a shared secret.
- **Notifications** (SMS/email): mocked. Messages go to an outbox stored with the case; nothing is sent.
- **Identity**: Cognito stands in for the company identity provider (C4: DHL Identity Provider, OIDC).

## 9. Screens

`docs/wireframes/` holds the lo-fi screens and the information architecture (`00_IA.png`), and
`docs/wireframes/notes.md` the notes per screen. Follow their structure, labels and content.
S1 courier report · S2 ops queue · S3 ops case card · S4 support notify · S5 courier my actions ·
S6 ops resolve · S7 depot damage. Navigation per IA; *At-risk shipments* and *Dashboards* show as
disabled "later" items.

## 10. Out of scope

AI of any kind (prediction, LLM drafts; see the AI assessment: rules first, AI as a suggestion in a
later phase) · real SMS/email · the real On Demand Delivery · real DHL data · dashboards and
at-risk shipments · the customs process beyond showing the case · React Native.

## 11. Architecture: PoC vs target

The PoC follows the course template: React + Vite + shadcn/ui on S3 + CloudFront, FastAPI on Lambda
behind API Gateway, DynamoDB, Cognito, CloudFormation, Docker Compose locally, Makefile, region
`eu-central-1`. The target in C4 (`docs/diagrams/`) is Java/Spring Boot, React Native, Kafka and a
Node.js notification service. Keep the PoC modules named after the C4 level 3 components: case,
communication, field actions and ODD webhook controllers; exception detection, exception assessment,
resolution management, response coordination and customer communication services; case management
and repository; notification client (mock); ODD adapter (simulator); access control.
