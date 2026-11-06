# Wireframe notes

Lo-fi screens S1–S7 (PNG files in this folder). Each note maps the screen to the BPMN task, FRs, tracking events and NFRs.

Note: docs/diagrams/bpmn-to-be-original.png is the original BPMN; docs/spec.md §2 describes the corrected flow these screens follow.

## S1 · Courier · Report failed delivery

- BPMN: Report failed delivery (new start event, Courier lane). The Platform lane then creates, classifies, prioritizes and assigns the case.
- FR1 · FR2
- Events: failed_delivery_reported (taps_count, duration_sec, photo_attached) → exception_case_created · exception_priority_set (auto) · case_owner_assigned (auto)
- NFR-4: ≤ 3 taps, < 15 s, 90% succeed on the first try
- ①②③ The three taps
- ④ GPS and time are added automatically, photo optional. A report far from the address is flagged to Ops.
- ⑤ Undo for 10 s after a wrong tap

## S2 · Operations · Case queue

- BPMN: Assign responsibility (Ops picks up the case)
- FR3 · FR4 · FR5
- Events: case_viewed (load_time_ms) when a case is opened
- NFR-1: case view < 2 s at p95 · NFR-5: case and owner < 5 min
- ① The platform created the case and assigned an owner
- ② High first, then least time left (BPMN business rule)
- ③ Customer informed? Feeds the North Star metric
- ④ Who acts now; '— not assigned' is Ops' next job
- ⑤ Time left against the 48 h target; overdue in bold

## S3 · Operations · Case card

- BPMN: Assign responsibility (in parallel with Notify customer)
- FR1 · FR2 · FR3 · FR4 · FR5
- Events: case_owner_assigned (manual) · case_action_updated · case_status_changed (New → In progress)
- NFR-1: opens in < 2 s
- ① GPS and photo on the courier's report, so Ops can trust or question the attempt
- ② The rule behind the priority. Ops can change it with a reason (set_by = user)
- ③ Only Ops assigns and reassigns; other roles escalate
- ④ Support informs the customer at the same time; Ops only sees the status

## S4 · Support · Notify customer

- BPMN: Notify customer about exception, now with the resolution options
- FR6
- Events: customer_notified (channel, notified_before_customer_contact, seconds_since_created) · case_status_changed (→ Waiting for customer)
- ① Queue of cases with no customer update yet
- ② Template picked from the type; facts filled in from the case
- ③ One message: reason + delivery options (the BPMN had two)
- ④ Duplicate check: shows what was sent; the same update is blocked for 24 h
- ⑤ The customer hasn't contacted us yet, so this counts for the North Star
- Next, outside the platform: the customer picks a slot in On Demand Delivery → resolution_option_recorded, and the slot goes onto the courier's action (case_action_updated)

## S5 · Courier · My actions

- BPMN: Re-deliver & update action status → Delivered? (new gateway)
- FR5
- Events: case_action_updated (action_status = done)
- ① The slot the customer picked in On Demand Delivery, added automatically
- ② Delivered in one tap; main buttons sit low, in thumb reach
- ③ Can't deliver opens the S1 report; after attempt 3 the parcel returns to sender

## S6 · Operations · Resolve case

- BPMN: Mark case as resolved → Inform customer: issue resolved
- FR5 · FR6
- Events: case_status_changed (→ Resolved) · case_resolved (resolution_minutes, resolved_on_time, reopened) · customer_notified
- ① Full history: who did what and when, every status change
- ② Time to resolve against the 48 h target → North Star
- ③ The confirmation uses Support's approved template
- ④ A case can be reopened; reopens are counted

## S7 · Depot · Report damage (outside the flow; the 4th role view)

- BPMN: Handle parcel & update action status, with a depot report as a start event
- FR1 · FR2 · FR5
- Events: exception_case_created (exception_type = damaged parcel, detection_method = depot report) · case_action_updated
- ① The scan finds the parcel and any open case, so no duplicate is created
- ② At least one photo, kept as evidence for Claims
- ③ Ops decides the next step, including handover to Claims Management (C4: Claims Adapter)
- This report created EX-10471 in the S2 queue.
