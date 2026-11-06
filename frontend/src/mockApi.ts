export const publicDemoMode = __DEMO_MODE__;

export const DEMO_USER_KEY = "exception-management-demo-user";
const DEMO_STATE_KEY = "exception-management-demo-state";
const UPDATED_EVENT = "exception-management-demo-updated";

type Role = "ops" | "support" | "courier" | "depot";
type DemoUser = {
  user_id: string;
  role: Role;
  name: string;
  email: string;
  scope: string;
};
type Shipment = {
  shipment_id: string;
  product: string;
  key_account: boolean;
  origin: string;
  destination: string;
  recipient_name: string;
  masked_phone: string;
  masked_email: string;
  address: string;
  region: string;
  route: string;
  stop: number;
  promised_delivery_date: string;
  open_case?: string;
};
type TimelineEntry = {
  at: string;
  actor: string;
  event: string;
  summary?: string;
  [key: string]: unknown;
};
type Action = {
  action_id: string;
  case_id: string;
  shipment_id: string;
  action_type: string;
  assignee_id: string;
  assignee_role?: Role;
  status: string;
  route_order: number;
  slot?: string | null;
  date: string;
};
type DemoCase = {
  case_id: string;
  shipment_id: string;
  shipment: Shipment;
  exception_type: string;
  priority: "high" | "medium" | "low";
  priority_rule_id: string;
  priority_set_by: string;
  status: string;
  owner_id?: string | null;
  owner_role: string;
  assignment_type: string;
  region: string;
  created_at: string;
  updated_at: string;
  deadline_at: string;
  customer_informed: boolean;
  messages_sent: boolean;
  resolution_message_sent: boolean;
  inbound_contacts: unknown[];
  next_action?: string;
  next_action_assignee_id?: string;
  customer_slot?: string | null;
  resolution_option?: string;
  attempt_count?: number;
  return_to_sender_date?: string | null;
  gps_flagged: boolean;
  timeline: TimelineEntry[];
  actions: Action[];
  messages: Array<{
    template_id: string;
    sent_at: string;
    body: string;
    channel: string;
    channels: string[];
    sender_id: string;
    notified_before_customer_contact: boolean;
  }>;
  [key: string]: unknown;
};
type DemoState = {
  cases: DemoCase[];
  shipments: Shipment[];
  routeActions: Action[];
  flowStage: number;
  flowCaseId: string | null;
  nextCaseNumber: number;
};

const users: DemoUser[] = [
  { user_id: "thomas-a", role: "courier", name: "Thomas A.", email: "thomas.courier@example.com", scope: "K-14" },
  { user_id: "marta-l", role: "ops", name: "Marta L.", email: "marta.ops@example.com", scope: "Kyiv-East" },
  { user_id: "kateryna-b", role: "support", name: "Kateryna B.", email: "kateryna.support@example.com", scope: "Support" },
  { user_id: "anna-k", role: "depot", name: "Anna K.", email: "anna.depot@example.com", scope: "Kyiv Hub" },
  { user_id: "oleh-s", role: "ops", name: "Oleh S.", email: "oleh.ops@example.com", scope: "Kyiv-West" },
  { user_id: "ivan-s", role: "courier", name: "Ivan S.", email: "ivan.courier@example.com", scope: "K-09" },
];

export function getPublicDemoUser(userId: string): DemoUser | undefined {
  return users.find((item) => item.user_id === userId);
}

const now = () => new Date().toISOString();
const clone = <T,>(value: T): T => JSON.parse(JSON.stringify(value)) as T;
const priorityRank = (priority: string) => ({ high: 0, medium: 1, low: 2 }[priority as "high" | "medium" | "low"] ?? 3);

function addBusinessDays(value: Date, count: number): string {
  const date = new Date(value);
  let added = 0;
  while (added < count) {
    date.setDate(date.getDate() + 1);
    if (date.getDay() !== 0 && date.getDay() !== 6) added += 1;
  }
  return date.toISOString().slice(0, 10);
}

function makeShipment(shipmentId: string, updates: Partial<Shipment> = {}): Shipment {
  return {
    shipment_id: shipmentId,
    product: "Standard",
    key_account: false,
    origin: "Warsaw",
    destination: "Kyiv",
    recipient_name: "Mock Recipient",
    masked_phone: "+380 •• ••• •• ••",
    masked_email: "r••••••••@•••.ua",
    address: "Kyiv (fictional address)",
    region: "Kyiv-East",
    route: "K-14",
    stop: 6,
    promised_delivery_date: new Date(Date.now() + 86_400_000).toISOString().slice(0, 10),
    ...updates,
  };
}

function makeSeed(): DemoState {
  const shipmentData: Array<[string, Partial<Shipment>]> = [
    ["7710389245", { key_account: true }],
    ["5127704361", {}],
    ["3398016627", {}],
    ["6620145873", { product: "Time-definite · by 12:00" }],
    ["9054127738", {}],
    ["2261907345", {}],
    ["8840512276", {}],
    ["4836201759", {
      product: "Time-definite · by 12:00",
      recipient_name: "O. Hrytsenko",
      masked_phone: "+380 •• ••• 41 27",
      masked_email: "o.h•••@•••.ua",
      address: "vul. Sadova 14, apt 9, Kyiv",
      stop: 6,
      promised_delivery_date: new Date().toISOString().slice(0, 10),
    }],
  ];
  const shipments = shipmentData.map(([id, details]) => makeShipment(id, details));
  const routeAddresses: Record<number, string> = {
    5: "vul. Lisova 7",
    6: "vul. Sadova 14, apt 9, Kyiv",
    7: "vul. Zelena 21, office 4",
    8: "vul. Sadova 30",
  };
  for (let stop = 1; stop <= 23; stop += 1) {
    const shipmentId = stop === 6 ? "4836201759" : `48362017${String(stop).padStart(2, "0")}`;
    if (!shipments.some((shipment) => shipment.shipment_id === shipmentId)) {
      shipments.push(makeShipment(shipmentId, {
        stop,
        recipient_name: "Demo Recipient",
        address: routeAddresses[stop] ?? `vul. Demo ${stop}, Kyiv`,
        promised_delivery_date: new Date().toISOString().slice(0, 10),
      }));
    }
  }

  const seededCases: Array<{
    id: string; shipment: string; type: string; priority: DemoCase["priority"];
    rule: string; status: string; ageHours: number; informed: boolean; action: string;
  }> = [
    { id: "EX-10458", shipment: "7710389245", type: "customs_hold", priority: "high", rule: "P1", status: "waiting_for_customs", ageHours: 50, informed: true, action: "Customs broker" },
    { id: "EX-10463", shipment: "5127704361", type: "failed_delivery", priority: "medium", rule: "default", status: "waiting_for_customer", ageHours: 30, informed: true, action: "Customer (choosing)" },
    { id: "EX-10466", shipment: "3398016627", type: "delay", priority: "medium", rule: "default", status: "in_progress", ageHours: 26, informed: true, action: "Linehaul · Warsaw hub" },
    { id: "EX-10471", shipment: "6620145873", type: "damaged_parcel", priority: "high", rule: "P2", status: "in_progress", ageHours: 17, informed: true, action: "Depot · Kyiv Hub (Anna K.)" },
    { id: "EX-10477", shipment: "9054127738", type: "delay", priority: "low", rule: "P4", status: "in_progress", ageHours: 8, informed: true, action: "Courier Ivan S." },
    { id: "EX-10480", shipment: "2261907345", type: "damaged_parcel", priority: "medium", rule: "default", status: "new", ageHours: 0.15, informed: false, action: "— not assigned" },
    { id: "EX-10481", shipment: "8840512276", type: "delay", priority: "medium", rule: "default", status: "new", ageHours: 0.07, informed: false, action: "— not assigned" },
  ];
  const cases: DemoCase[] = seededCases.map((definition) => {
    const created = new Date(Date.now() - definition.ageHours * 3_600_000);
    const deadline = new Date(created.getTime() + 48 * 3_600_000);
    const shipment = shipments.find((item) => item.shipment_id === definition.shipment)!;
    const timeline: TimelineEntry[] = [
      { at: created.toISOString(), actor: "system", event: "exception_case_created", summary: "Platform created and classified the case." },
      { at: created.toISOString(), actor: "system", event: "exception_priority_set", priority: definition.priority, rule_id: definition.rule, summary: "Priority set automatically." },
      { at: created.toISOString(), actor: "system", event: "case_owner_assigned", owner_id: "marta-l", assignment_type: "auto", summary: "Case owner assigned." },
    ];
    const messages = definition.informed ? [{
      template_id: definition.type === "failed_delivery" ? "failed-delivery-options" : `${definition.type.replace("_", "-")}-update`,
      sent_at: created.toISOString(),
      body: "Fictional demo message body.",
      channel: "SMS and Email",
      channels: ["sms", "email"],
      sender_id: "kateryna-b",
      notified_before_customer_contact: true,
    }] : [];
    const actions: Action[] = definition.action === "— not assigned" || definition.action === "Customer (choosing)"
      ? []
      : [{
        action_id: `${definition.id}-action`,
        case_id: definition.id,
        shipment_id: definition.shipment,
        action_type: definition.action,
        assignee_id: definition.action.includes("Ivan") ? "ivan-s" : definition.action.includes("Anna") ? "anna-k" : "thomas-a",
        status: "open",
        route_order: shipment.stop,
        date: new Date().toISOString().slice(0, 10),
      }];
    return {
      case_id: definition.id,
      shipment_id: definition.shipment,
      shipment,
      exception_type: definition.type,
      priority: definition.priority,
      priority_rule_id: definition.rule,
      priority_set_by: "auto",
      status: definition.status,
      owner_id: "marta-l",
      owner_role: "ops",
      assignment_type: "auto",
      region: shipment.region,
      created_at: created.toISOString(),
      updated_at: created.toISOString(),
      deadline_at: deadline.toISOString(),
      customer_informed: definition.informed,
      messages_sent: definition.informed,
      resolution_message_sent: false,
      inbound_contacts: [],
      next_action: definition.action,
      next_action_assignee_id: actions[0]?.assignee_id,
      gps_flagged: false,
      timeline,
      actions,
      messages,
      ...(definition.type === "failed_delivery" ? { attempt_count: 1, return_to_sender_date: addBusinessDays(created, 5) } : {}),
    };
  });
  const today = new Date().toISOString().slice(0, 10);
  const routeActions: Action[] = Array.from({ length: 23 }, (_, index) => {
    const stop = index + 1;
    const shipmentId = stop === 6 ? "4836201759" : `48362017${String(stop).padStart(2, "0")}`;
    return {
      action_id: `ROUTE-STOP-${String(stop).padStart(2, "0")}`,
      case_id: `ROUTE-STOP-${String(stop).padStart(2, "0")}`,
      shipment_id: shipmentId,
      action_type: "Delivery",
      assignee_id: "thomas-a",
      assignee_role: "courier",
      status: "open",
      route_order: stop,
      date: today,
    };
  });
  return { cases, shipments, routeActions, flowStage: 0, flowCaseId: null, nextCaseNumber: 10482 };
}

function getState(): DemoState {
  const saved = localStorage.getItem(DEMO_STATE_KEY);
  if (!saved) {
    const state = makeSeed();
    saveState(state);
    return state;
  }
  try {
    return JSON.parse(saved) as DemoState;
  } catch {
    const state = makeSeed();
    saveState(state);
    return state;
  }
}

function saveState(state: DemoState): void {
  localStorage.setItem(DEMO_STATE_KEY, JSON.stringify(state));
  window.dispatchEvent(new Event(UPDATED_EVENT));
}

export function resetPublicDemo(): void {
  saveState(makeSeed());
}

export function getPublicDemoProgress(): { stage: number; caseId: string | null } {
  const state = getState();
  return { stage: state.flowStage, caseId: state.flowCaseId };
}

export function subscribePublicDemo(callback: () => void): () => void {
  window.addEventListener(UPDATED_EVENT, callback);
  return () => window.removeEventListener(UPDATED_EVENT, callback);
}

function currentUser(): DemoUser {
  const userId = localStorage.getItem(DEMO_USER_KEY);
  const user = users.find((item) => item.user_id === userId);
  if (!user) throw new Error("Choose a demo user to continue.");
  return user;
}

function requireRole(...roles: Role[]): DemoUser {
  const user = currentUser();
  if (!roles.includes(user.role)) throw new Error(`This role cannot access this endpoint.`);
  return user;
}

function caseById(state: DemoState, caseId: string): DemoCase {
  const found = state.cases.find((item) => item.case_id === caseId);
  if (!found) throw new Error("Case not found.");
  return found;
}

function shipmentById(state: DemoState, shipmentId: string): Shipment {
  const found = state.shipments.find((item) => item.shipment_id === shipmentId);
  if (!found) throw new Error("Shipment not found.");
  return found;
}

function recordTimeline(item: DemoCase, event: string, actor: string, details: Record<string, unknown> = {}): void {
  item.timeline.push({ at: now(), actor, event, ...details });
  item.updated_at = now();
}

function setStatus(item: DemoCase, status: string, actor: string): void {
  if (item.status === status) return;
  const oldStatus = item.status;
  item.status = status;
  recordTimeline(item, "case_status_changed", actor, {
    old_status: oldStatus,
    new_status: status,
    changed_by_role: actor === "system" ? "system" : currentUser().role,
    summary: `Case status changed from ${oldStatus} to ${status}.`,
  });
}

function autoPriority(shipment: Shipment, exceptionType: string, attempt: number): { priority: DemoCase["priority"]; rule: string } {
  if (shipment.key_account) return { priority: "high", rule: "P1" };
  if (shipment.product.toLowerCase().includes("time-definite")) return { priority: "high", rule: "P2" };
  if (exceptionType === "failed_delivery" && attempt >= 2) return { priority: "high", rule: "P3" };
  if (exceptionType === "delay" && shipment.promised_delivery_date >= new Date().toISOString().slice(0, 10)) {
    return { priority: "low", rule: "P4" };
  }
  return { priority: "medium", rule: "default" };
}

function supportQueue(item: DemoCase): string | null {
  if (item.status === "resolved" && !item.resolution_message_sent) return "confirm_resolution";
  if (!item.messages_sent) return "not_informed";
  if (item.status === "waiting_for_customer") return "waiting_for_customer";
  return null;
}

function sortCases(a: DemoCase, b: DemoCase): number {
  return priorityRank(a.priority) - priorityRank(b.priority)
    || a.created_at.localeCompare(b.created_at);
}

function requestBody(init: RequestInit): Record<string, unknown> {
  if (typeof init.body !== "string") return {};
  try {
    return JSON.parse(init.body) as Record<string, unknown>;
  } catch {
    return {};
  }
}

function asString(value: unknown): string {
  return typeof value === "string" ? value : "";
}

function checkMessageDuplicate(item: DemoCase, templateId: string): boolean {
  const cutoff = Date.now() - 86_400_000;
  return item.messages.some((message) =>
    message.template_id === templateId && new Date(message.sent_at).getTime() > cutoff,
  );
}

function createCase(state: DemoState, shipment: Shipment, type: string, reason: string, actor: string): DemoCase {
  const current = state.cases.find((item) =>
    item.shipment_id === shipment.shipment_id && item.exception_type === type && item.status !== "resolved",
  );
  if (current) {
    current.attempt_count = (current.attempt_count ?? 1) + 1;
    recordTimeline(current, "failed_delivery_reported", actor, {
      reason, taps_count: 3, duration_sec: 5, photo_attached: false, gps_distance_m: 18,
      gps_flagged: false, summary: `Failed delivery reported · ${reason}`,
    });
    if (current.attempt_count >= 3) {
      current.next_action = "Return to sender";
      recordTimeline(current, "return_to_sender_required", "system", {
        attempt_count: current.attempt_count,
        summary: "Maximum delivery attempts reached; return to sender.",
      });
    }
    const priority = autoPriority(shipment, type, current.attempt_count);
    if (priority.priority !== current.priority) {
      current.priority = priority.priority;
      current.priority_rule_id = priority.rule;
      recordTimeline(current, "exception_priority_set", "system", { priority: priority.priority, rule_id: priority.rule, set_by: "auto" });
    }
    return current;
  }
  const id = `EX-${state.nextCaseNumber++}`;
  const createdAt = now();
  const priority = autoPriority(shipment, type, 1);
  const ownerId = users.find((user) => user.role === "ops" && user.scope === shipment.region)?.user_id ?? null;
  const item: DemoCase = {
    case_id: id,
    shipment_id: shipment.shipment_id,
    shipment,
    exception_type: type,
    priority: priority.priority,
    priority_rule_id: priority.rule,
    priority_set_by: "auto",
    status: "new",
    owner_id: ownerId,
    owner_role: "ops",
    assignment_type: "auto",
    region: shipment.region,
    created_at: createdAt,
    updated_at: createdAt,
    deadline_at: new Date(Date.now() + 48 * 3_600_000).toISOString(),
    customer_informed: false,
    messages_sent: false,
    resolution_message_sent: false,
    inbound_contacts: [],
    next_action: "— not assigned",
    attempt_count: 1,
    return_to_sender_date: addBusinessDays(new Date(), 5),
    gps_flagged: false,
    timeline: [],
    actions: [],
    messages: [],
  };
  state.cases.push(item);
  recordTimeline(item, "exception_case_created", actor, {
    detection_method: "failed_delivery",
    shipment_id: shipment.shipment_id,
    summary: "Platform created and classified the case.",
  });
  recordTimeline(item, "exception_priority_set", "system", {
    priority: priority.priority, rule_id: priority.rule, set_by: "auto", summary: "Priority set automatically.",
  });
  recordTimeline(item, "case_owner_assigned", "system", {
    owner_id: ownerId, assignment_type: "auto", summary: "Case owner assigned automatically.",
  });
  recordTimeline(item, "case_status_changed", "system", {
    old_status: "", new_status: "new", changed_by_role: "system", summary: "Case opened.",
  });
  recordTimeline(item, "failed_delivery_reported", actor, {
    reason, taps_count: 3, duration_sec: 5, photo_attached: false, gps_distance_m: 18,
    gps_flagged: false, summary: `Failed delivery reported · ${reason}`,
  });
  state.flowStage = Math.max(state.flowStage, 1);
  state.flowCaseId = id;
  return item;
}

function pickResponse<T>(value: unknown): T {
  return clone(value) as T;
}

export async function mockApiRequest<T>(path: string, init: RequestInit = {}): Promise<T> {
  const normalizedPath = path.replace(/^\/api/, "");
  const routePath = normalizedPath.split("?")[0];
  const method = (init.method ?? "GET").toUpperCase();
  const state = getState();
  const body = requestBody(init);
  const current = currentUser();

  if (method === "GET" && routePath === "/auth/me") {
    return pickResponse({ user_id: current.user_id, role: current.role, email: current.email });
  }
  if (method === "GET" && routePath === "/cases/users") {
    requireRole("ops");
    return pickResponse(users.map(({ user_id, role, name, scope }) => ({ user_id, role, name, scope })));
  }
  if (method === "GET" && routePath === "/cases") {
    requireRole("ops");
    const query = new URLSearchParams(path.split("?")[1] ?? "");
    const tab = query.get("tab") ?? "mine";
    let matches = state.cases.filter((item) => item.status !== "resolved");
    if (tab === "mine") matches = matches.filter((item) => item.owner_id === current.user_id);
    if (tab === "unassigned") matches = matches.filter((item) => !item.owner_id);
    if (tab === "overdue") matches = matches.filter((item) => new Date(item.deadline_at).getTime() < Date.now());
    if (query.has("exception_type")) matches = matches.filter((item) => item.exception_type === query.get("exception_type"));
    if (query.has("priority")) matches = matches.filter((item) => item.priority === query.get("priority"));
    if (query.has("region")) matches = matches.filter((item) => item.region === query.get("region"));
    if (query.has("status")) matches = matches.filter((item) => item.status === query.get("status"));
    return pickResponse(matches.sort((a, b) => priorityRank(a.priority) - priorityRank(b.priority)
      || new Date(a.deadline_at).getTime() - new Date(b.deadline_at).getTime()));
  }
  const caseMatch = routePath.match(/^\/cases\/([^/]+)$/);
  if (method === "GET" && caseMatch) {
    const item = caseById(state, decodeURIComponent(caseMatch[1]));
    if (current.role === "courier" || current.role === "depot") {
      if (!item.actions.some((action) => action.assignee_id === current.user_id)) {
        throw new Error("This case has no action assigned to you.");
      }
    }
    return pickResponse(item);
  }

  const fieldShipment = routePath.match(/^\/field\/shipments\/([^/]+)$/);
  const supportShipment = routePath.match(/^\/communication\/shipments\/([^/]+)$/);
  if (method === "GET" && fieldShipment) {
    requireRole("courier", "depot");
    return pickResponse(shipmentById(state, decodeURIComponent(fieldShipment[1])));
  }
  if (method === "GET" && supportShipment) {
    requireRole("support");
    return pickResponse(shipmentById(state, decodeURIComponent(supportShipment[1])));
  }
  if (method === "GET" && routePath === "/field/actions") {
    requireRole("courier", "depot");
    const active = state.routeActions.filter((action) => action.assignee_id === current.user_id && action.status !== "done");
    const caseActions = state.cases.flatMap((item) => item.actions
      .filter((action) => action.assignee_id === current.user_id && action.status !== "done")
      .map((action) => ({ ...action, case: item })));
    const routeResults = active.map((action) => ({
      ...action,
      shipment: shipmentById(state, action.shipment_id),
      case: state.cases.find((item) => item.case_id === action.case_id) ?? undefined,
    }));
    return pickResponse([...routeResults, ...caseActions].sort((a, b) => a.route_order - b.route_order));
  }
  const completeAction = routePath.match(/^\/field\/actions\/([^/]+)\/complete$/);
  if (method === "POST" && completeAction) {
    requireRole("courier", "depot");
    const actionId = decodeURIComponent(completeAction[1]);
    const item = state.cases.find((candidate) => candidate.actions.some((action) => action.action_id === actionId));
    const action = item?.actions.find((candidate) => candidate.action_id === actionId)
      ?? state.routeActions.find((candidate) => candidate.action_id === actionId);
    if (!action || action.assignee_id !== current.user_id) throw new Error("Assigned action not found.");
    action.status = "done";
    if (item) {
      recordTimeline(item, "case_action_updated", current.user_id, {
        action_type: action.action_type, action_status: "done", summary: `${action.action_type} completed.`,
      });
      state.flowStage = Math.max(state.flowStage, 5);
      state.flowCaseId = item.case_id;
    }
    saveState(state);
    return pickResponse({ action_id: actionId, status: "done" });
  }

  if (method === "POST" && routePath === "/field/reports/failed-delivery") {
    requireRole("courier");
    if (!(init.body instanceof FormData)) throw new Error("A delivery report is required.");
    const shipmentId = asString(init.body.get("shipment_id"));
    const reason = asString(init.body.get("reason"));
    if (asString(init.body.get("taps_count")) !== "3") throw new Error("Failed delivery reports must take exactly 3 taps.");
    const duration = Number(init.body.get("duration_sec"));
    if (!Number.isFinite(duration) || duration < 0 || duration >= 15) throw new Error("The report must take under 15 seconds.");
    const shipment = shipmentById(state, shipmentId);
    const routeAction = state.routeActions.find((action) => action.shipment_id === shipmentId
      && action.assignee_id === current.user_id && action.status === "open");
    if (routeAction) routeAction.status = "done";
    const alreadyOpen = state.cases.some((candidate) =>
      candidate.shipment_id === shipmentId && candidate.exception_type === "failed_delivery" && candidate.status !== "resolved",
    );
    const item = createCase(state, shipment, "failed_delivery", reason, current.user_id);
    saveState(state);
    return pickResponse({ case_id: item.case_id, created: !alreadyOpen, report_id: `report-${Date.now()}` });
  }
  if (method === "POST" && routePath === "/field/reports/damage") {
    requireRole("depot");
    if (!(init.body instanceof FormData)) throw new Error("A damage report is required.");
    const shipment = shipmentById(state, asString(init.body.get("shipment_id")));
    const damageTypes = init.body.getAll("damage_types").map(String);
    if (!damageTypes.length) throw new Error("Select at least one damage type.");
    if (!init.body.getAll("photos").length) throw new Error("At least one photo is required.");
    const item = createCase(state, shipment, "damaged_parcel", damageTypes.join(", "), current.user_id);
    recordTimeline(item, "damage_report_details", current.user_id, {
      damage_types: damageTypes,
      contents_checked: init.body.get("contents_checked") === "true",
      note: asString(init.body.get("note")),
      summary: "Depot damage details recorded.",
    });
    saveState(state);
    return pickResponse({ case_id: item.case_id, created: true });
  }

  const caseActions = routePath.match(/^\/cases\/([^/]+)\/actions$/);
  if (method === "POST" && caseActions) {
    requireRole("ops");
    const item = caseById(state, decodeURIComponent(caseActions[1]));
    const actionType = asString(body.action_type);
    const assignee = users.find((user) => user.user_id === body.assignee_id);
    if (!assignee || (assignee.role !== "courier" && assignee.role !== "depot")) throw new Error("Select an active courier or depot user.");
    if (actionType.toLowerCase() === "redelivery" && (assignee.role !== "courier" || assignee.scope !== item.shipment.route)) {
      throw new Error("Redelivery must be assigned to the courier on the shipment's route.");
    }
    const action: Action = {
      action_id: `ACTION-${Date.now()}`,
      case_id: item.case_id,
      shipment_id: item.shipment_id,
      action_type: actionType,
      assignee_id: assignee.user_id,
      assignee_role: assignee.role,
      status: "open",
      route_order: item.shipment.stop,
      slot: item.customer_slot ?? null,
      date: now().slice(0, 10),
    };
    item.actions.push(action);
    item.next_action = actionType;
    item.next_action_assignee_id = assignee.user_id;
    if (item.status === "new") setStatus(item, "in_progress", current.user_id);
    recordTimeline(item, "case_action_updated", current.user_id, {
      action_id: action.action_id, action_type: actionType, assignee_id: assignee.user_id,
      action_status: "open", summary: `${actionType} assigned to ${assignee.name}.`,
    });
    state.flowStage = Math.max(state.flowStage, 2);
    state.flowCaseId = item.case_id;
    saveState(state);
    return pickResponse(action);
  }

  const sendMessage = routePath.match(/^\/communication\/cases\/([^/]+)\/messages$/);
  if (method === "POST" && sendMessage) {
    requireRole("support");
    const item = caseById(state, decodeURIComponent(sendMessage[1]));
    const templateId = asString(body.template_id);
    if (checkMessageDuplicate(item, templateId)) throw new Error("This update was already sent for this case in the last 24 hours.");
    const channel = asString(body.channel);
    item.messages.push({
      template_id: templateId, sent_at: now(), body: asString(body.body), channel,
      channels: channel.toLowerCase().split(" and "), sender_id: current.user_id,
      notified_before_customer_contact: item.inbound_contacts.length === 0,
    });
    item.messages_sent = true;
    item.customer_informed = true;
    recordTimeline(item, "customer_notified", current.user_id, {
      template_id: templateId, channel,
      notified_before_customer_contact: item.inbound_contacts.length === 0,
      seconds_since_created: Math.max(0, Math.floor((Date.now() - new Date(item.created_at).getTime()) / 1000)),
      summary: "Customer notified by Support.",
    });
    if (item.status !== "resolved" && item.status !== "waiting_for_customs") setStatus(item, "waiting_for_customer", current.user_id);
    state.flowStage = Math.max(state.flowStage, 3);
    state.flowCaseId = item.case_id;
    saveState(state);
    return pickResponse(item);
  }

  const queueMatch = routePath.match(/^\/communication\/queues\/([^/]+)$/);
  if (method === "GET" && queueMatch) {
    requireRole("support");
    const queueName = decodeURIComponent(queueMatch[1]);
    if (!["not_informed", "waiting_for_customer", "confirm_resolution"].includes(queueName)) throw new Error("Unknown Support queue.");
    return pickResponse(state.cases.filter((item) => supportQueue(item) === queueName).sort(sortCases));
  }
  if (method === "GET" && routePath === "/communication/simulator/waiting") {
    requireRole("support");
    return pickResponse(state.cases.filter((item) => item.status === "waiting_for_customer").sort(sortCases));
  }
  if (method === "POST" && routePath === "/communication/simulator/choice") {
    requireRole("support");
    const item = caseById(state, asString(body.case_id));
    const optionType = asString(body.option_type);
    const slot = asString(body.slot);
    if (!["redelivery", "pickup_point"].includes(optionType)) throw new Error("Unsupported resolution option.");
    if (optionType === "redelivery" && !slot) throw new Error("Select a redelivery slot.");
    item.customer_slot = optionType === "redelivery" ? slot : null;
    item.resolution_option = optionType;
    for (const action of item.actions) {
      if (action.action_type.toLowerCase() === "redelivery" && ["open", "pending_assignment"].includes(action.status)) action.slot = slot;
    }
    recordTimeline(item, "resolution_option_recorded", "system", {
      option_type: optionType, slot, summary: `Customer selected ${optionType}${slot ? ` · ${slot}` : ""}.`,
    });
    recordTimeline(item, "case_action_updated", "system", {
      action_type: "redelivery", action_status: "open", summary: "Redelivery action updated with the customer choice.",
    });
    if (item.status === "waiting_for_customer") setStatus(item, "in_progress", "system");
    state.flowStage = Math.max(state.flowStage, 4);
    state.flowCaseId = item.case_id;
    saveState(state);
    return pickResponse(item);
  }

  const priorityMatch = routePath.match(/^\/cases\/([^/]+)\/priority$/);
  if (method === "POST" && priorityMatch) {
    requireRole("ops");
    const item = caseById(state, decodeURIComponent(priorityMatch[1]));
    const reason = asString(body.reason).trim();
    if (!reason) throw new Error("A reason is required to change priority.");
    const oldPriority = item.priority;
    item.priority = asString(body.priority) as DemoCase["priority"];
    item.priority_rule_id = "manual_override";
    item.priority_set_by = "user";
    recordTimeline(item, "exception_priority_set", current.user_id, {
      old_priority: oldPriority, priority: item.priority, set_by: "user", reason,
      summary: `Priority changed to ${item.priority}.`,
    });
    saveState(state);
    return pickResponse(item);
  }
  const ownerMatch = routePath.match(/^\/cases\/([^/]+)\/owner$/);
  if (method === "POST" && ownerMatch) {
    requireRole("ops");
    const item = caseById(state, decodeURIComponent(ownerMatch[1]));
    const newOwner = users.find((user) => user.user_id === body.owner_id && user.role === "ops");
    if (!newOwner) throw new Error("The selected owner must be an Operations user.");
    item.owner_id = newOwner.user_id;
    item.assignment_type = "manual";
    recordTimeline(item, "case_owner_assigned", current.user_id, {
      owner_id: newOwner.user_id, assignment_type: "manual", summary: `Owner reassigned to ${newOwner.name}.`,
    });
    saveState(state);
    return pickResponse(item);
  }
  const resolveMatch = routePath.match(/^\/cases\/([^/]+)\/resolve$/);
  if (method === "POST" && resolveMatch) {
    requireRole("ops");
    const item = caseById(state, decodeURIComponent(resolveMatch[1]));
    if (item.status === "resolved") throw new Error("The case is already resolved.");
    const sendConfirmation = body.send_confirmation !== false;
    if (sendConfirmation && checkMessageDuplicate(item, "resolution-confirmation")) {
      throw new Error("The resolution confirmation template was already sent for this case in the last 24 hours.");
    }
    item.outcome = asString(body.outcome);
    item.root_cause = asString(body.root_cause);
    const resolvedAt = now();
    item.resolved_at = resolvedAt;
    item.resolved_on_time = new Date(resolvedAt).getTime() <= new Date(item.deadline_at).getTime();
    item.resolution_message_sent = sendConfirmation;
    setStatus(item, "resolved", current.user_id);
    recordTimeline(item, "case_resolved", current.user_id, {
      exception_type: item.exception_type,
      resolution_minutes: Math.floor((Date.now() - new Date(item.created_at).getTime()) / 60_000),
      resolved_on_time: item.resolved_on_time,
      reopened: Boolean(item.reopen_count),
      summary: "Case resolved.",
    });
    if (sendConfirmation) {
      item.customer_informed = true;
      item.messages.push({
        template_id: "resolution-confirmation", sent_at: resolvedAt, body: "Delivered, case closed.",
        channel: "SMS and email", channels: ["sms", "email"], sender_id: current.user_id,
        notified_before_customer_contact: item.inbound_contacts.length === 0,
      });
    }
    state.flowStage = Math.max(state.flowStage, 6);
    state.flowCaseId = item.case_id;
    saveState(state);
    return pickResponse(item);
  }
  const reopenMatch = routePath.match(/^\/cases\/([^/]+)\/reopen$/);
  if (method === "POST" && reopenMatch) {
    requireRole("ops");
    const item = caseById(state, decodeURIComponent(reopenMatch[1]));
    if (item.status !== "resolved") throw new Error("Only a resolved case can be reopened.");
    const reason = asString(body.reason).trim();
    if (!reason) throw new Error("A reason is required to reopen the case.");
    item.reopen_count = Number(item.reopen_count ?? 0) + 1;
    item.reopened = true;
    item.resolved_at = null;
    item.resolved_on_time = null;
    setStatus(item, "in_progress", current.user_id);
    recordTimeline(item, "case_reopened", current.user_id, { reason, reopen_count: item.reopen_count, summary: "Case reopened." });
    saveState(state);
    return pickResponse(item);
  }
  const escalateMatch = routePath.match(/^\/cases\/([^/]+)\/escalate$/);
  if (method === "POST" && escalateMatch) {
    requireRole("support", "courier", "depot");
    const item = caseById(state, decodeURIComponent(escalateMatch[1]));
    recordTimeline(item, "escalated_to_operations", current.user_id, { message: asString(body.message), summary: "Escalated to Operations." });
    saveState(state);
    return pickResponse(item);
  }
  throw new Error(`Demo API does not support ${method} ${routePath}.`);
}
