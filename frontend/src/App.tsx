import { useCallback, useEffect, useMemo, useState, type FormEvent, type ReactNode } from "react";
import {
  Link,
  Navigate,
  NavLink,
  Route,
  Routes,
  useNavigate,
  useParams,
  useSearchParams,
} from "react-router-dom";

import { AuthProvider, useAuth, type Role } from "./auth";
import { apiRequest, postForm, postJson } from "./api";
import { Button } from "./components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "./components/ui/card";
import { Input } from "./components/ui/input";

const localDemoEnabled = import.meta.env.VITE_LOCAL_DEMO_LOGIN === "true";
const demoUsers: Array<{ id: string; name: string; role: Role; scope: string }> = [
  { id: "marta-l", name: "Marta L.", role: "ops", scope: "Kyiv-East" },
  { id: "oleh-s", name: "Oleh S.", role: "ops", scope: "Kyiv-West" },
  { id: "kateryna-b", name: "Kateryna B.", role: "support", scope: "Support" },
  { id: "thomas-a", name: "Thomas A.", role: "courier", scope: "Route K-14" },
  { id: "ivan-s", name: "Ivan S.", role: "courier", scope: "Route K-09" },
  { id: "anna-k", name: "Anna K.", role: "depot", scope: "Kyiv Hub" },
];
const roleTitles: Record<Role, string> = {
  ops: "Operations",
  support: "Support",
  courier: "Courier",
  depot: "Depot",
};
const exceptionTypes = ["delay", "failed_delivery", "damaged_parcel", "customs_hold"];
const statuses = ["new", "in_progress", "waiting_for_customer", "waiting_for_customs", "resolved"];
const typeLabels: Record<string, string> = {
  delay: "Delay",
  failed_delivery: "Failed delivery",
  damaged_parcel: "Damaged parcel",
  customs_hold: "Customs hold",
};
const statusLabels: Record<string, string> = {
  new: "New",
  in_progress: "In progress",
  waiting_for_customer: "Waiting for customer",
  waiting_for_customs: "Waiting for customs",
  resolved: "Resolved",
};

type UserSummary = { user_id: string; role: Role; name: string; scope: string };
type Shipment = {
  shipment_id: string;
  product: string;
  origin: string;
  destination: string;
  open_case?: string;
  key_account?: boolean;
  region: string;
  route: string;
  stop: number;
  recipient_name: string;
  address: string;
  masked_phone: string;
  masked_email: string;
  promised_delivery_date: string;
};
type TimelineEntry = {
  at: string;
  actor: string;
  event: string;
  summary?: string;
  reason?: unknown;
  priority?: unknown;
  rule_id?: unknown;
  slot?: unknown;
  [key: string]: unknown;
};
type CaseAction = {
  action_id: string;
  action_type: string;
  assignee_id: string;
  status: string;
  slot?: string;
  [key: string]: unknown;
};
type CaseItem = {
  case_id: string;
  shipment_id: string;
  shipment: Shipment;
  exception_type: string;
  priority: string;
  priority_rule_id: string;
  status: string;
  owner_id?: string;
  region: string;
  created_at: string;
  deadline_at: string;
  customer_informed?: boolean;
  inbound_contacts?: unknown[];
  messages_sent?: boolean;
  resolution_message_sent?: boolean;
  messages?: Array<{ template_id: string; sent_at: string; body: string; channel?: string }>;
  timeline?: TimelineEntry[];
  actions?: CaseAction[];
  attempt_count?: number;
  return_to_sender_date?: string;
  customer_slot?: string;
  next_action?: string;
  next_action_assignee_id?: string;
  gps_flagged?: boolean;
  [key: string]: unknown;
};
type FieldAction = {
  action_id: string;
  shipment_id: string;
  action_type: string;
  status: string;
  route_order: number;
  slot?: string;
  case?: CaseItem;
  shipment?: Shipment;
};

function useResource<T>(load: () => Promise<T>, dependencies: unknown[] = [], refreshMs = 0) {
  const [data, setData] = useState<T | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const refresh = useCallback(async () => {
    try {
      setData(await load());
      setError(null);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The request failed.");
    } finally {
      setLoading(false);
    }
  // load is intentionally supplied by callers with its dependencies.
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, dependencies);
  useEffect(() => {
    void refresh();
    if (!refreshMs) return undefined;
    const timer = window.setInterval(() => void refresh(), refreshMs);
    return () => window.clearInterval(timer);
  }, [refresh, refreshMs]);
  return { data, error, loading, refresh, setData, setError };
}

function ErrorMessage({ children }: { children: ReactNode }) {
  return <p className="rounded-md border border-destructive/40 bg-destructive/5 p-3 text-sm text-destructive" role="alert">{children}</p>;
}

function Loading({ label = "Loading…" }: { label?: string }) {
  return <p aria-live="polite" className="p-4 text-sm text-muted-foreground">{label}</p>;
}

function PriorityChip({ priority }: { priority: string }) {
  const label = priority.charAt(0).toUpperCase() + priority.slice(1);
  return <span className={`priority-chip priority-${priority.toLowerCase()}`}>{label}</span>;
}

function StatusChip({ status }: { status: string }) {
  return <span className="status-chip">{status}</span>;
}

function PageTitle({ title, description, children }: {
  title: ReactNode; description?: string; children?: ReactNode;
}) {
  return (
    <div className="mb-6 flex flex-wrap items-end justify-between gap-4">
      <div>
        <h1 className="text-3xl font-bold tracking-tight">{title}</h1>
        {description && <p className="mt-1 text-sm text-muted-foreground">{description}</p>}
      </div>
      {children}
    </div>
  );
}

function SignInPage() {
  const { signIn, completeMfa, demoSignIn, error } = useAuth();
  const navigate = useNavigate();
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [mfaCode, setMfaCode] = useState("");
  const [mfaSession, setMfaSession] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setSubmitting(true);
    try {
      if (mfaSession) {
        await completeMfa(email, mfaSession, mfaCode);
        navigate("/app", { replace: true });
      } else {
        const session = await signIn(email, password);
        if (session) setMfaSession(session);
        else navigate("/app", { replace: true });
      }
    } catch {
      // The authentication context exposes the error to the form.
    } finally {
      setSubmitting(false);
    }
  }

  async function signInDemo(userId: string) {
    setSubmitting(true);
    try {
      await demoSignIn(userId);
      navigate("/app", { replace: true });
    } catch {
      // The authentication context exposes the error to the form.
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="flex min-h-screen flex-col">
      <header className="app-header flex min-h-16 items-center px-5">
        <span className="text-xl font-bold">Exception Management</span>
      </header>
      <main className="flex flex-1 items-center justify-center p-4">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <CardTitle>Exception Management</CardTitle>
          <CardDescription>Sign in with your company account.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={(event) => void submit(event)}>
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="email">Email</label>
              <Input autoComplete="username" disabled={mfaSession !== null} id="email"
                onChange={(event) => setEmail(event.target.value)} required type="email" value={email} />
            </div>
            {mfaSession ? (
              <div className="space-y-2">
                <label className="text-sm font-medium" htmlFor="mfa-code">Authenticator code</label>
                <Input autoComplete="one-time-code" id="mfa-code" inputMode="numeric" maxLength={6}
                  onChange={(event) => setMfaCode(event.target.value)} pattern="[0-9]{6}" required value={mfaCode} />
              </div>
            ) : (
              <div className="space-y-2">
                <label className="text-sm font-medium" htmlFor="password">Password</label>
                <Input autoComplete="current-password" id="password"
                  onChange={(event) => setPassword(event.target.value)} required type="password" value={password} />
              </div>
            )}
            {error && <ErrorMessage>{error}</ErrorMessage>}
            <Button className="w-full" disabled={submitting} type="submit">{mfaSession ? "Verify code" : "Sign in"}</Button>
            {mfaSession && <Button className="w-full" disabled={submitting}
              onClick={() => { setMfaSession(null); setMfaCode(""); }} type="button" variant="outline">
              Use a different account
            </Button>}
          </form>
          {localDemoEnabled && !mfaSession && (
            <section aria-labelledby="demo-users-title" className="mt-8 border-t pt-6">
              <h2 className="mb-1 text-lg font-semibold" id="demo-users-title">Local test sign-in</h2>
              <p className="mb-4 text-sm text-muted-foreground">Fictional demo users · local environment only</p>
              <div className="grid gap-2 sm:grid-cols-2">
                {demoUsers.map((demo) => (
                  <Button className="h-auto min-h-11 justify-start whitespace-normal py-3 text-left"
                    disabled={submitting} key={demo.id} onClick={() => void signInDemo(demo.id)}
                    type="button" variant="outline">
                    {demo.name} · {roleTitles[demo.role]} · {demo.scope}
                  </Button>
                ))}
              </div>
            </section>
          )}
        </CardContent>
      </Card>
      </main>
      <footer className="app-footer">Student concept · not a DHL product</footer>
    </div>
  );
}

function AppLayout() {
  const { user, signOut } = useAuth();
  if (!user) return <Navigate replace to="/sign-in" />;
  const field = user.role === "courier" || user.role === "depot";
  const links: Record<Role, Array<[string, string]>> = {
    ops: [["Cases", "/app/cases"], ["At-risk shipments · later", "#"], ["Dashboards · later", "#"]],
    support: [["Customer updates", "/app/updates"], ["Shipment lookup", "/app/shipments"], ["Simulator", "/simulator"]],
    courier: [["My actions", "/app/actions"]],
    depot: [["My actions", "/app/actions"], ["Scan / report damage", "/app/damage"]],
  };
  const defaultPath = user.role === "ops" ? "/app/cases"
    : user.role === "support" ? "/app/updates" : "/app/actions";

  const content = (
    <div className={field ? "field-shell" : "min-h-screen"}>
      <header className="app-header flex min-h-16 items-center justify-between border-b px-4 py-3">
        <Link className="font-semibold" to={defaultPath}>Exception Management</Link>
        <div className="flex items-center gap-3">
          {!field && <span className="hidden text-sm text-muted-foreground sm:inline">{roleTitles[user.role]} · {user.email}</span>}
          <Button onClick={signOut} type="button" variant="outline">Sign out</Button>
        </div>
      </header>
      {field ? (
        <div className="field-content flex flex-col p-4">
          <p className="mb-4 text-sm text-muted-foreground">{roleTitles[user.role]} · {user.email}</p>
          <Routes>
            <Route element={<FieldActionsPage />} path="/app/actions" />
            <Route element={<FailedDeliveryPage />} path="/app/report/:shipmentId" />
            <Route element={<DamageReportPage />} path="/app/damage" />
            <Route element={<Navigate replace to={defaultPath} />} path="*" />
          </Routes>
          <nav aria-label="Field navigation" className="field-nav mt-auto grid grid-cols-2 gap-2">
            {links[user.role].map(([label, path]) => (
              <NavLink className={({ isActive }) => `rounded-md px-2 py-2 text-center text-sm ${isActive ? "bg-muted font-semibold" : "text-muted-foreground"}`}
                key={path} to={path}>{label}</NavLink>
            ))}
          </nav>
        </div>
      ) : (
        <div className="grid min-h-[calc(100vh-7rem)] md:grid-cols-[15rem_1fr]">
          <nav aria-label={`${roleTitles[user.role]} navigation`} className="border-b bg-card p-3 md:border-b-0 md:border-r">
            <ul className="flex flex-wrap gap-2 md:flex-col">
              {links[user.role].map(([label, path]) => (
                <li key={label}>
                  {path === "#" ? (
                    <button className="min-h-11 rounded-md px-3 text-sm text-muted-foreground" disabled type="button">{label}</button>
                  ) : (
                    <NavLink className={({ isActive }) => `block min-h-11 rounded-md px-3 py-3 text-sm ${isActive ? "bg-muted font-semibold" : "hover:bg-muted"}`}
                      to={path}>{label}</NavLink>
                  )}
                </li>
              ))}
            </ul>
          </nav>
          <main className="p-4 md:p-8">
            <Routes>
              <Route element={<CaseQueuePage />} path="/app/cases" />
              <Route element={<CaseDetailsPage />} path="/app/cases/:caseId" />
              <Route element={<SupportUpdatesPage />} path="/app/updates" />
              <Route element={<ShipmentLookupPage />} path="/app/shipments" />
              <Route element={<SimulatorPage />} path="/simulator" />
              <Route element={<Navigate replace to={defaultPath} />} path="*" />
            </Routes>
          </main>
        </div>
      )}
    </div>
  );
  if (field) {
    return (
      <div className="field-preview">
        {content}
        <footer className="app-footer field-footer">Student concept · not a DHL product</footer>
      </div>
    );
  }
  return (
    <div className="web-app">
      {content}
      <footer className="app-footer">Student concept · not a DHL product</footer>
    </div>
  );
}

function CaseQueuePage() {
  const tabs = ["mine", "unassigned", "overdue", "all_open"] as const;
  const tabLabels: Record<(typeof tabs)[number], string> = {
    mine: "My cases", unassigned: "Unassigned", overdue: "Overdue", all_open: "All open",
  };
  const [tab, setTab] = useState<(typeof tabs)[number]>("mine");
  const [exceptionType, setExceptionType] = useState("");
  const [priority, setPriority] = useState("");
  const [region, setRegion] = useState("");
  const [status, setStatus] = useState("");
  const params = new URLSearchParams({ tab });
  if (exceptionType) params.set("exception_type", exceptionType);
  if (priority) params.set("priority", priority);
  if (region) params.set("region", region);
  if (status) params.set("status", status);
  const resource = useResource(
    () => apiRequest<CaseItem[]>(`/cases?${params.toString()}`),
    [tab, exceptionType, priority, region, status], 10_000,
  );
  const recent = resource.data?.find((item) => Date.now() - new Date(item.created_at).getTime() < 5 * 60_000);
  return (
    <>
      {recent && <Card className="mb-5 border-2 border-accent bg-accent text-accent-foreground"><CardContent className="flex flex-wrap items-center justify-between gap-3 pt-5">
        <strong>New case assigned to you</strong>
        <span>{recent.case_id} · {typeLabels[recent.exception_type]} · <PriorityChip priority={recent.priority} /></span>
        <Link className="font-semibold underline" to={`/app/cases/${recent.case_id}`}>Open case</Link>
      </CardContent></Card>}
      <PageTitle title="Cases" description="High first, then least time left. Refreshes every 10 seconds." />
      <div className="mb-4 flex flex-wrap gap-2" role="tablist" aria-label="Case queue">
        {tabs.map((value) => <Button aria-selected={tab === value} key={value}
          onClick={() => setTab(value)} role="tab" variant={tab === value ? "default" : "outline"}>
          {tabLabels[value]}
        </Button>)}
      </div>
      <div className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <label className="text-sm">Type<select className="mt-1 h-11 w-full rounded-md border bg-background px-2" onChange={(e) => setExceptionType(e.target.value)} value={exceptionType}>
          <option value="">All types</option>{exceptionTypes.map((type) => <option key={type} value={type}>{typeLabels[type]}</option>)}
        </select></label>
        <label className="text-sm">Priority<select className="mt-1 h-11 w-full rounded-md border bg-background px-2" onChange={(e) => setPriority(e.target.value)} value={priority}>
          <option value="">All priorities</option><option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
        </select></label>
        <label className="text-sm">Region<select className="mt-1 h-11 w-full rounded-md border bg-background px-2" onChange={(e) => setRegion(e.target.value)} value={region}>
          <option value="">All regions</option><option value="Kyiv-East">Kyiv-East</option><option value="Kyiv-West">Kyiv-West</option>
        </select></label>
        <label className="text-sm">Status<select className="mt-1 h-11 w-full rounded-md border bg-background px-2" onChange={(e) => setStatus(e.target.value)} value={status}>
          <option value="">All open statuses</option>{statuses.filter((item) => item !== "resolved").map((item) => <option key={item} value={item}>{statusLabels[item]}</option>)}
        </select></label>
      </div>
      {resource.error && <ErrorMessage>{resource.error}</ErrorMessage>}
      {resource.loading && !resource.data ? <Loading /> : (
        <div className="overflow-x-auto rounded-lg border">
          <table className="w-full min-w-[850px] border-collapse text-left text-sm">
            <thead><tr className="border-b bg-accent text-accent-foreground">
              {["Priority", "Case", "Type", "Shipment", "Status", "Next action with", "Customer informed", "Time left (48 h)"].map((item) => <th className="p-3" key={item}>{item}</th>)}
            </tr></thead>
            <tbody>{(resource.data ?? []).map((item) => {
              const hours = Math.floor((new Date(item.deadline_at).getTime() - Date.now()) / 3_600_000);
              const overdue = hours < 0;
              return <tr className="border-b last:border-0" key={item.case_id}>
                <td className="p-3"><PriorityChip priority={item.priority} /></td>
                <td className="p-3"><Link className="underline" to={`/app/cases/${item.case_id}`}>{item.case_id}</Link></td>
                <td className="p-3">{typeLabels[item.exception_type]}</td>
                <td className="p-3">{item.shipment_id}</td>
                <td className="p-3"><StatusChip status={statusLabels[item.status]} /></td>
                <td className="p-3">{item.owner_id ? item.next_action ?? "— not assigned" : "— not assigned"}</td>
                <td className="p-3">{item.customer_informed ? "Yes" : "No"}</td>
                <td className={`p-3 ${overdue ? "font-bold" : ""}`}>{overdue ? `Overdue ${Math.abs(hours)} h` : `${hours} h`}</td>
              </tr>;
            })}</tbody>
          </table>
          {!resource.data?.length && <p className="p-6 text-sm text-muted-foreground">No cases match this queue.</p>}
        </div>
      )}
    </>
  );
}

function CaseDetailsPage() {
  const { caseId = "" } = useParams();
  const { user } = useAuth();
  const [priority, setPriority] = useState("high");
  const [priorityReason, setPriorityReason] = useState("");
  const [ownerId, setOwnerId] = useState("");
  const [actionType, setActionType] = useState("Redelivery");
  const [assigneeId, setAssigneeId] = useState("thomas-a");
  const [outcome, setOutcome] = useState("Delivered");
  const [rootCause, setRootCause] = useState("Recipient not at home");
  const [sendConfirmation, setSendConfirmation] = useState(true);
  const [reason, setReason] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const caseResource = useResource(() => apiRequest<CaseItem>(`/cases/${caseId}`), [caseId]);
  const usersResource = useResource(() => apiRequest<UserSummary[]>("/cases/users"), []);
  const caseItem = caseResource.data;
  const owners = usersResource.data?.filter((item) => item.role === "ops") ?? [];
  const fieldUsers = usersResource.data?.filter((item) => item.role === "courier" || item.role === "depot") ?? [];
  const actionAssignees = actionType.toLowerCase() === "redelivery"
    ? fieldUsers.filter((item) => item.role === "courier" && item.scope === caseItem?.shipment.route)
    : fieldUsers;

  async function update(path: string, value: unknown, success: string) {
    setFeedback(null);
    try {
      const updated = await postJson<CaseItem>(path, value);
      if (updated?.case_id) caseResource.setData(updated);
      setFeedback(success);
    } catch (cause) {
      setFeedback(cause instanceof Error ? cause.message : "The update failed.");
    }
  }

  if (caseResource.loading && !caseItem) return <Loading />;
  if (caseResource.error) return <ErrorMessage>{caseResource.error}</ErrorMessage>;
  if (!caseItem) return null;
  const deadlineHours = Math.floor((new Date(caseItem.deadline_at).getTime() - Date.now()) / 3_600_000);
  const ruleLabel: Record<string, string> = {
    P1: "Key-account shipment → High",
    P2: "Time-definite product → High",
    P3: "Second or later failed attempt → High",
    P4: "Delay that still meets the promised date → Low",
    default: "No priority rule matched → Medium",
    manual_override: "Operations changed the priority",
  };
  return (
    <>
      <p className="mb-4 text-sm"><Link className="underline" to="/app/cases">Cases</Link> / {caseItem.case_id}</p>
      <PageTitle title={<span className="flex flex-wrap items-center gap-3">
        {caseItem.case_id} · {typeLabels[caseItem.exception_type]}
        <PriorityChip priority={caseItem.priority} />
        <StatusChip status={statusLabels[caseItem.status]} />
      </span>}
        description={`Shipment ${caseItem.shipment_id} · owner ${caseItem.owner_id ?? "unassigned"}`}>
        <Card><CardContent className="p-3 text-sm">Resolve by {new Date(caseItem.deadline_at).toLocaleString()}<br />
          <strong>{deadlineHours < 0 ? `Overdue ${Math.abs(deadlineHours)} h` : `${deadlineHours} h left`}</strong>
        </CardContent></Card>
      </PageTitle>
      {feedback && <p className="mb-4 text-sm" role="status">{feedback}</p>}
      <div className="grid gap-5 xl:grid-cols-[minmax(0,1.7fr)_minmax(18rem,1fr)]">
        <div className="space-y-5">
          <Card><CardHeader><CardTitle>Shipment</CardTitle></CardHeader><CardContent className="grid gap-4 text-sm sm:grid-cols-2">
            <p><strong>Product</strong><br />{caseItem.shipment.product}</p>
            <p><strong>Route</strong><br />{caseItem.shipment.route} · {caseItem.region}</p>
            <p><strong>Recipient</strong><br />{caseItem.shipment.recipient_name} · {caseItem.shipment.masked_phone}</p>
            <p><strong>Address</strong><br />{caseItem.shipment.address}</p>
            {caseItem.attempt_count && <p><strong>Attempt</strong><br />{caseItem.attempt_count} of 3</p>}
            {caseItem.return_to_sender_date && <p><strong>Return to sender</strong><br />{caseItem.return_to_sender_date} if no new option is chosen</p>}
            {caseItem.gps_flagged && <p className="font-semibold">GPS report is more than 150 m from the address.</p>}
          </CardContent></Card>
          <Card><CardHeader><CardTitle>Timeline</CardTitle></CardHeader><CardContent className="space-y-0">
            {caseItem.timeline?.map((entry, index) => <div className="grid grid-cols-[7rem_1fr] gap-3 border-t py-3 text-sm" key={`${entry.at}-${index}`}>
              <time dateTime={entry.at}>{new Date(entry.at).toLocaleString()}</time>
              <div><strong>{String(entry.actor)}</strong> · {String(entry.summary ?? entry.event.replaceAll("_", " "))}
                {entry.reason !== undefined && entry.reason !== null && <p>{String(entry.reason)}</p>}
                {entry.priority !== undefined && <p>Priority: {String(entry.priority)} · {String(entry.rule_id ?? "")}</p>}
                {entry.slot !== undefined && <p>Customer slot: {String(entry.slot)}</p>}
              </div>
            </div>)}
            {!caseItem.timeline?.length && <p className="text-sm text-muted-foreground">No timeline events.</p>}
          </CardContent></Card>
        </div>
        <div className="space-y-5">
          <Card><CardHeader><CardTitle>Why {caseItem.priority === "high" ? "High?" : `${caseItem.priority}?`}</CardTitle></CardHeader>
            <CardContent className="space-y-3">
              <p><strong>Rule {caseItem.priority_rule_id}</strong> · {ruleLabel[caseItem.priority_rule_id] ?? "Automatically assessed"}</p>
              {user?.role === "ops" && <form className="space-y-3" onSubmit={(event) => {
                event.preventDefault();
                void update(`/cases/${caseId}/priority`, { priority, reason: priorityReason }, "Priority updated.");
              }}>
                <label className="block text-sm">Change priority
                  <select className="mt-1 h-11 w-full rounded-md border bg-background px-2" onChange={(e) => setPriority(e.target.value)} value={priority}>
                    <option value="high">High</option><option value="medium">Medium</option><option value="low">Low</option>
                  </select>
                </label>
                <label className="block text-sm">Reason (required)
                  <Input onChange={(e) => setPriorityReason(e.target.value)} required value={priorityReason} />
                </label>
                <Button type="submit" variant="outline">Save priority</Button>
              </form>}
            </CardContent>
          </Card>
          {user?.role === "ops" && caseItem.status !== "resolved" && <>
            <Card><CardHeader><CardTitle>Next action</CardTitle></CardHeader><CardContent>
              <form className="space-y-3" onSubmit={(event) => {
                event.preventDefault();
                void update(`/cases/${caseId}/actions`, { action_type: actionType, assignee_id: assigneeId }, "Action assigned.");
              }}>
                <label className="block text-sm">Action
                  <select className="mt-1 h-11 w-full rounded-md border bg-background px-2" onChange={(e) => setActionType(e.target.value)} value={actionType}>
                    <option>Redelivery</option><option>Inspect parcel</option><option>Repack parcel</option><option>Return to sender</option>
                  </select>
                </label>
                <label className="block text-sm">Responsible
                  <select className="mt-1 h-11 w-full rounded-md border bg-background px-2" onChange={(e) => setAssigneeId(e.target.value)} value={assigneeId}>
                    {actionAssignees.map((fieldUser) => <option key={fieldUser.user_id} value={fieldUser.user_id}>
                      {fieldUser.name} · {fieldUser.role} · {fieldUser.scope}
                    </option>)}
                  </select>
                </label>
                <Button className="w-full" type="submit">Assign action</Button>
              </form>
            </CardContent></Card>
            <Card><CardHeader><CardTitle>Case owner</CardTitle></CardHeader><CardContent>
              <form className="space-y-3" onSubmit={(event) => {
                event.preventDefault();
                void update(`/cases/${caseId}/owner`, { owner_id: ownerId }, "Case owner reassigned.");
              }}>
                <label className="block text-sm">Reassign case owner
                  <select className="mt-1 h-11 w-full rounded-md border bg-background px-2" onChange={(e) => setOwnerId(e.target.value)} required value={ownerId}>
                    <option value="">Choose an Operations user</option>
                    {owners.map((owner) => <option key={owner.user_id} value={owner.user_id}>{owner.name} · {owner.scope}</option>)}
                  </select>
                </label><Button variant="outline" type="submit">Reassign owner</Button>
              </form>
            </CardContent></Card>
            <Card><CardHeader><CardTitle>Resolve case</CardTitle></CardHeader><CardContent>
              <form className="space-y-3" onSubmit={(event) => {
                event.preventDefault();
                void update(`/cases/${caseId}/resolve`, { outcome, root_cause: rootCause, send_confirmation: sendConfirmation }, "Case resolved.");
              }}>
                <label className="block text-sm">Outcome<Input onChange={(e) => setOutcome(e.target.value)} required value={outcome} /></label>
                <label className="block text-sm">Root cause<Input onChange={(e) => setRootCause(e.target.value)} required value={rootCause} /></label>
                <label className="flex min-h-11 items-center gap-2 text-sm"><input checked={sendConfirmation} onChange={(e) => setSendConfirmation(e.target.checked)} type="checkbox" />
                  Send confirmation to the customer (Support template)
                </label>
                <Button className="w-full" type="submit">Resolve case</Button>
              </form>
            </CardContent></Card>
          </>}
          {user?.role === "ops" && caseItem.status === "resolved" && (
            <Card><CardHeader><CardTitle>Resolved</CardTitle><CardDescription>
              {caseItem.resolved_on_time ? "Resolved within 48 h." : "Resolved after the 48 h target."}
            </CardDescription></CardHeader><CardContent>
              <label className="mb-3 block text-sm">Reopen reason
                <Input onChange={(e) => setReason(e.target.value)} value={reason} />
              </label>
              <Button onClick={() => void update(`/cases/${caseId}/reopen`, { reason }, "Case reopened.")} variant="outline">Reopen case</Button>
            </CardContent></Card>
          )}
          <Card><CardHeader><CardTitle>Customer</CardTitle></CardHeader><CardContent className="text-sm">
            <p><strong>{caseItem.customer_informed ? "Informed" : "Not informed yet"}</strong></p>
            <p className="mt-2">{caseItem.customer_slot ? `Customer slot: ${caseItem.customer_slot}` : "No customer slot recorded."}</p>
            {caseItem.messages?.map((message, index) => <p className="mt-3 border-t pt-2" key={`${message.sent_at}-${index}`}>{message.template_id} · {message.channel}</p>)}
          </CardContent></Card>
        </div>
      </div>
    </>
  );
}

function SupportUpdatesPage() {
  const queueNames = ["not_informed", "waiting_for_customer", "confirm_resolution"] as const;
  const labels = ["Not informed", "Waiting for customer", "Confirm resolution"];
  const [queue, setQueue] = useState<(typeof queueNames)[number]>("not_informed");
  const casesResource = useResource(() => apiRequest<CaseItem[]>(`/communication/queues/${queue}`), [queue], 10_000);
  const [selectedId, setSelectedId] = useState("");
  const [templateId, setTemplateId] = useState("");
  const [channels, setChannels] = useState<string[]>(["SMS", "Email"]);
  const [body, setBody] = useState("");
  const [feedback, setFeedback] = useState<string | null>(null);
  const selected = casesResource.data?.find((item) => item.case_id === selectedId) ?? casesResource.data?.[0];
  const currentTemplate = selected?.exception_type === "failed_delivery" ? "failed-delivery-options"
    : selected?.exception_type === "damaged_parcel" ? "damaged-parcel-update"
      : selected?.exception_type === "customs_hold" ? "customs-hold-update" : "delay-update";
  const initialMessage = useMemo(() => selected ? (
    `Hello, we have an update about parcel ${selected.shipment_id}. ${typeLabels[selected.exception_type]}: ` +
    `${selected.timeline?.find((item) => item.reason)?.reason ?? "we are working on the next step"}. ` +
    `Please choose a delivery option by ${selected.return_to_sender_date ?? "the date shown in your shipment update"}.`
  ) : "", [selected]);
  useEffect(() => {
    if (selected) {
      setTemplateId(currentTemplate);
      setBody(initialMessage);
    }
  }, [selected?.case_id, currentTemplate, initialMessage]);
  const duplicate = selected?.messages?.some((message) =>
    message.template_id === templateId && Date.now() - new Date(message.sent_at).getTime() < 86_400_000,
  ) ?? false;

  async function sendMessage(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!selected) return;
    setFeedback(null);
    try {
      await postJson(`/communication/cases/${selected.case_id}/messages`, {
        template_id: templateId, channel: channels.join(" and "), body,
      });
      setFeedback("Customer update saved to the case outbox.");
      await casesResource.refresh();
    } catch (cause) {
      setFeedback(cause instanceof Error ? cause.message : "The message could not be saved.");
    }
  }

  return (
    <>
      <PageTitle title="Customer updates" description="Queues are ordered High first, then oldest." />
      <div className="grid gap-5 xl:grid-cols-[19rem_1fr]">
        <aside className="space-y-2">
          {queueNames.map((name, index) => <Button className="w-full justify-between" key={name}
            onClick={() => { setQueue(name); setSelectedId(""); }} variant={queue === name ? "default" : "outline"}>
            {labels[index]} <span>{queue === name ? casesResource.data?.length ?? 0 : ""}</span>
          </Button>)}
          {casesResource.error && <ErrorMessage>{casesResource.error}</ErrorMessage>}
          {casesResource.loading && !casesResource.data ? <Loading /> : casesResource.data?.map((item) => (
            <button className={`w-full rounded-lg border p-4 text-left ${selected?.case_id === item.case_id ? "border-foreground bg-muted" : ""}`}
              key={item.case_id} onClick={() => setSelectedId(item.case_id)} type="button">
              <strong>{item.case_id} · {typeLabels[item.exception_type]}</strong>
              <span className="mt-2 block"><PriorityChip priority={item.priority} /></span>
              <span className="mt-1 block text-sm text-muted-foreground">{item.shipment_id}</span>
            </button>
          ))}
        </aside>
        {selected ? (
          <section>
            <h2 className="mb-3 flex flex-wrap items-center gap-2 text-xl font-bold">{selected.case_id} · {typeLabels[selected.exception_type]} <PriorityChip priority={selected.priority} /></h2>
            <Card className="mb-4"><CardContent className="space-y-2 p-4 text-sm">
              <p><strong>Shipment:</strong> {selected.shipment_id} · {selected.shipment.product} · {selected.shipment.region}</p>
              <p><strong>What happened:</strong> {String(selected.timeline?.find((item) => item.reason)?.reason ?? typeLabels[selected.exception_type])}</p>
              <p><strong>What’s next:</strong> {selected.next_action ?? "Operations will assign the next action."}</p>
              <p><strong>No choice by:</strong> {selected.return_to_sender_date ?? "See shipment details"}</p>
              <p><strong>{selected.inbound_contacts?.length ? "Customer has contacted us" : "The customer hasn't contacted us about this yet"}</strong></p>
            </CardContent></Card>
            <Card><CardHeader><CardTitle>Notify customer</CardTitle><CardDescription>Messages are stored in the case outbox; nothing is sent.</CardDescription></CardHeader>
              <CardContent>
                <form className="space-y-5" onSubmit={(event) => void sendMessage(event)}>
                  <fieldset><legend className="mb-2 text-sm">Channel</legend><div className="flex flex-wrap gap-4">
                    {["SMS", "Email"].map((channel) => <label className="flex min-h-11 items-center gap-2" key={channel}>
                      <input checked={channels.includes(channel)} onChange={(event) => setChannels((value) =>
                        event.target.checked ? [...value, channel] : value.filter((item) => item !== channel))} type="checkbox" />
                      {channel}
                    </label>)}
                  </div></fieldset>
                  <label className="block text-sm">Template · picked from the case type
                    <select className="mt-1 h-11 w-full rounded-md border bg-background px-2" onChange={(event) => setTemplateId(event.target.value)} value={templateId}>
                      <option value={currentTemplate}>{typeLabels[selected.exception_type]} · customer update</option>
                      <option value="resolution-options">Resolution options</option>
                    </select>
                  </label>
                  <label className="block text-sm">Message preview
                    <textarea className="mt-1 min-h-36 w-full rounded-md border bg-background p-3" onChange={(event) => setBody(event.target.value)} required value={body} />
                  </label>
                  <div className="rounded-md border border-dashed p-3 text-sm">
                    <strong>Sent for this case so far:</strong> {selected.messages?.length ?? 0}
                    <p>The same template can't go to this customer twice within 24 h.</p>
                    {duplicate && <p className="mt-2 font-semibold text-destructive">This template was sent within the last 24 h.</p>}
                  </div>
                  {feedback && <p role="status">{feedback}</p>}
                  <div className="flex flex-wrap gap-3">
                    <Button disabled={duplicate || !body.trim() || !channels.length} type="submit">Send to customer</Button>
                    <Button onClick={async () => {
                      try {
                        await postJson(`/cases/${selected.case_id}/escalate`, { message: "Support requests Operations review." });
                        setFeedback("Escalated to Operations.");
                      } catch (cause) { setFeedback(cause instanceof Error ? cause.message : "Escalation failed."); }
                    }} type="button" variant="outline">Escalate to Operations</Button>
                  </div>
                </form>
              </CardContent>
            </Card>
          </section>
        ) : <p className="p-6 text-muted-foreground">{casesResource.data?.length === 0 ? "No cases in this queue." : "Select a case to view its summary."}</p>}
      </div>
    </>
  );
}

function ShipmentLookupPage() {
  const [shipmentId, setShipmentId] = useState("");
  const [shipment, setShipment] = useState<Shipment | null>(null);
  const [error, setError] = useState<string | null>(null);
  async function search(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setShipment(null);
    try {
      setShipment(await apiRequest<Shipment>(`/communication/shipments/${encodeURIComponent(shipmentId)}`));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Shipment lookup failed.");
    }
  }
  return <>
    <PageTitle title="Shipment lookup" description="Search using a shipment number." />
    <form className="mb-5 flex max-w-xl gap-2" onSubmit={(event) => void search(event)}>
      <label className="sr-only" htmlFor="shipment-number">Shipment number</label>
      <Input id="shipment-number" onChange={(event) => setShipmentId(event.target.value)} required value={shipmentId} />
      <Button type="submit">Search</Button>
    </form>
    {error && <ErrorMessage>{error}</ErrorMessage>}
    {shipment && <Card><CardHeader><CardTitle>{shipment.shipment_id}</CardTitle></CardHeader>
      <CardContent className="grid gap-3 text-sm sm:grid-cols-2">
        <p>Product: {shipment.product}</p><p>Region: {shipment.region}</p>
        <p>Route: {shipment.route}</p><p>Recipient: {shipment.recipient_name}</p>
        <p>Address: {shipment.address}</p><p>Phone: {shipment.masked_phone}</p>
      </CardContent></Card>}
  </>;
}

function FieldActionsPage() {
  const { user } = useAuth();
  const resource = useResource(() => apiRequest<FieldAction[]>("/field/actions"), [user?.user_id], 10_000);
  const [error, setError] = useState<string | null>(null);
  async function complete(actionId: string) {
    setError(null);
    try {
      await postJson(`/field/actions/${actionId}/complete`, {});
      await resource.refresh();
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Unable to update action.");
    }
  }
  return <>
    <PageTitle title="My actions" description={`${new Date().toLocaleDateString()} · today's assigned work`} />
    {resource.error && <ErrorMessage>{resource.error}</ErrorMessage>}
    {error && <ErrorMessage>{error}</ErrorMessage>}
    {resource.loading && !resource.data ? <Loading /> : (
      <div className="space-y-4">
        {(resource.data ?? []).map((action) => {
          const shipment = action.shipment ?? action.case?.shipment;
          return           <Card className="border-2 bg-card" key={action.action_id}>
            <CardHeader><div className="flex justify-between gap-3">
              <CardTitle className="text-lg">Stop {action.route_order} · {action.action_type}</CardTitle>
              {action.case?.attempt_count && <span className="whitespace-nowrap text-sm">Attempt {action.case.attempt_count} of 3</span>}
            </div></CardHeader>
            <CardContent className="space-y-3">
              {action.slot && <div className="rounded-sm bg-accent p-3 text-accent-foreground"><strong>Customer’s slot: {action.slot}</strong></div>}
              <p className="font-semibold">{shipment?.recipient_name ?? "Depot handling action"}</p>
              <p>{shipment?.address ?? shipment?.region}</p>
              <p className="text-sm text-muted-foreground">Parcel {action.shipment_id}{action.case && ` · case ${action.case.case_id}`}</p>
              {action.case?.return_to_sender_date && <p className="text-sm">Return to sender if no choice by {action.case.return_to_sender_date}</p>}
              <div className="grid grid-cols-2 gap-2">
                <Button className="min-h-[52px]" onClick={() => void complete(action.action_id)} type="button">Delivered / Done</Button>
                {user?.role === "courier" && action.action_type.toLowerCase().includes("delivery")
                  ? <Button className="min-h-[52px]" onClick={() => window.location.assign(`/app/report/${action.shipment_id}?action_id=${action.action_id}`)}
                    type="button" variant="outline">Can’t deliver</Button>
                  : <span />}
              </div>
            </CardContent>
          </Card>;
        })}
        {!resource.data?.length && <Card><CardContent className="pt-6 text-sm text-muted-foreground">No actions assigned to you today.</CardContent></Card>}
      </div>
    )}
  </>;
}

const failReasons = [
  ["not_at_home", "Not at home"],
  ["address_wrong", "Address wrong or incomplete"],
  ["recipient_refused", "Recipient refused"],
  ["no_access", "No access to the building"],
  ["other", "Other, add a note"],
] as const;

function FailedDeliveryPage() {
  const { shipmentId = "" } = useParams();
  const [searchParams] = useSearchParams();
  const actionId = searchParams.get("action_id");
  const { user } = useAuth();
  const shipmentResource = useResource(() => apiRequest<Shipment>(`/field/shipments/${encodeURIComponent(shipmentId)}`), [shipmentId]);
  const [reason, setReason] = useState("");
  const [note, setNote] = useState("");
  const [photo, setPhoto] = useState<File | null>(null);
  const [reportStart] = useState(Date.now());
  const [report, setReport] = useState<{ case_id: string; report_id?: string; created?: boolean } | null>(null);
  const [secondsLeft, setSecondsLeft] = useState(10);
  const [error, setError] = useState<string | null>(null);
  const [busy, setBusy] = useState(false);
  const navigate = useNavigate();
  useEffect(() => {
    if (!report || secondsLeft <= 0) return undefined;
    const timer = window.setInterval(() => setSecondsLeft((value) => value - 1), 1000);
    return () => window.clearInterval(timer);
  }, [report, secondsLeft]);

  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    if (!reason || (reason === "other" && !note.trim())) return;
    setBusy(true);
    setError(null);
    const form = new FormData();
    form.set("shipment_id", shipmentId);
    form.set("reason", reason === "other" ? note : failReasons.find(([key]) => key === reason)?.[1] ?? reason);
    form.set("note", note);
    form.set("taps_count", "3");
    form.set("duration_sec", String(Math.floor((Date.now() - reportStart) / 1000)));
    if (photo) form.set("photo", photo);
    try {
      const result = await postForm<{ case_id: string; report_id?: string; created?: boolean }>("/field/reports/failed-delivery", form);
      setReport(result);
      window.history.replaceState({}, "", `/app/report/${shipmentId}?case_id=${result.case_id}`);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The report could not be saved.");
    } finally {
      setBusy(false);
    }
  }
  async function undo() {
    if (!report?.report_id) return;
    setBusy(true);
    try {
      await postJson(`/field/reports/${report.case_id}/undo`, { report_id: report.report_id });
      setReport(null);
      navigate("/app/actions");
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "The report could not be undone.");
    } finally {
      setBusy(false);
    }
  }
  if (shipmentResource.loading && !shipmentResource.data) return <Loading />;
  if (shipmentResource.error) return <ErrorMessage>{shipmentResource.error}</ErrorMessage>;
  const shipment = shipmentResource.data;
  if (!shipment) return null;
  return report ? (
    <section className="flex min-h-[70vh] flex-col items-center justify-center text-center">
      <div className="mb-4 grid h-16 w-16 place-items-center rounded-full border-2 text-3xl" aria-hidden="true">✓</div>
      <h1 className="text-2xl font-semibold">Reported</h1>
      <p className="mt-3 font-medium">
        {report.created ? `Case ${report.case_id} created` : `New delivery attempt added to case ${report.case_id}`}
      </p>
      <p className="mt-2 max-w-sm text-sm text-muted-foreground">Operations and Support see it now. The customer will get new delivery options.</p>
      {error && <ErrorMessage>{error}</ErrorMessage>}
      {secondsLeft > 0 && <Button className="mt-5" disabled={busy} onClick={() => void undo()} type="button" variant="outline">Undo · {secondsLeft} s</Button>}
      <div className="field-sticky-action mt-5 w-full">
        <Button className="min-h-[52px] w-full" onClick={() => navigate("/app/actions")} type="button">Next stop</Button>
      </div>
    </section>
  ) : (
    <>
      <p className="mb-2 text-sm text-muted-foreground">Stop {shipment.stop} · Route {shipment.route}</p>
      <h1 className="text-2xl font-semibold">Why couldn’t you deliver?</h1>
      <Card className="mt-4"><CardContent className="space-y-2 p-4">
        <strong>{shipment.recipient_name}</strong><p>{shipment.address}</p>
        <p>Parcel {shipment.shipment_id}</p><p className="text-sm">{shipment.product}</p>
        <p className="text-sm">Location and time are added automatically · simulated GPS: 18 m from the address</p>
      </CardContent></Card>
      <form className="mt-4 space-y-3" onSubmit={(event) => void submit(event)}>
        <fieldset className="space-y-2">
          <legend className="mb-2 font-semibold">Pick the reason</legend>
          {failReasons.map(([key, label]) => <label className={`flex min-h-[52px] items-center gap-3 rounded-md border px-3 ${reason === key ? "border-foreground" : ""}`} key={key}>
            <input checked={reason === key} name="reason" onChange={() => setReason(key)} required type="radio" value={key} />{label}
          </label>)}
        </fieldset>
        {reason === "other" && <label className="block text-sm">Note required
          <Input onChange={(event) => setNote(event.target.value)} required value={note} />
        </label>}
        <label className="block text-sm">Add photo (optional)
          <Input accept="image/jpeg,image/png,image/webp" onChange={(event) => setPhoto(event.target.files?.[0] ?? null)} type="file" />
        </label>
        {photo && <p className="text-sm">{photo.name}</p>}
        {error && <ErrorMessage>{error}</ErrorMessage>}
        <div className="field-sticky-action">
          <Button className="min-h-[52px] w-full" disabled={busy || !reason || (reason === "other" && !note.trim())} type="submit">Report</Button>
        </div>
      </form>
      {actionId && <p className="mt-4 text-xs text-muted-foreground">Action {actionId}</p>}
      <p className="mt-3 text-center text-xs text-muted-foreground">Three taps from the stop · under 15 seconds</p>
      {user?.role !== "courier" && <ErrorMessage>Courier access required.</ErrorMessage>}
    </>
  );
}

function DamageReportPage() {
  const [shipmentId, setShipmentId] = useState("");
  const [shipment, setShipment] = useState<Shipment | null>(null);
  const [damageTypes, setDamageTypes] = useState<string[]>([]);
  const [contentsChecked, setContentsChecked] = useState("");
  const [note, setNote] = useState("");
  const [photos, setPhotos] = useState<File[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState<string | null>(null);
  async function scan(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    try {
      setShipment(await apiRequest<Shipment>(`/field/shipments/${encodeURIComponent(shipmentId)}`));
    } catch (cause) { setError(cause instanceof Error ? cause.message : "Shipment not found."); }
  }
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setError(null);
    setSuccess(null);
    const form = new FormData();
    form.set("shipment_id", shipmentId);
    damageTypes.forEach((value) => form.append("damage_types", value));
    form.set("contents_checked", contentsChecked);
    form.set("note", note);
    photos.forEach((file) => form.append("photos", file));
    try {
      const result = await postForm<{ case_id: string }>("/field/reports/damage", form);
      setSuccess(`Damaged parcel case ${result.case_id} created for Operations.`);
    } catch (cause) { setError(cause instanceof Error ? cause.message : "The damage report could not be saved."); }
  }
  return <>
    <h1 className="text-2xl font-semibold">Report damage</h1>
    <form className="mt-4 flex gap-2" onSubmit={(event) => void scan(event)}>
      <label className="sr-only" htmlFor="parcel-number">Parcel number</label>
      <Input id="parcel-number" onChange={(event) => setShipmentId(event.target.value)} placeholder="Scan or enter parcel number" required value={shipmentId} />
      <Button type="submit" variant="outline">Scan</Button>
    </form>
    {error && <div className="mt-4"><ErrorMessage>{error}</ErrorMessage></div>}
    {success && <p className="mt-4 font-medium" role="status">{success}</p>}
    {shipment && <Card className="mt-4"><CardContent className="p-4">
      <p>Parcel scanned · {shipment.shipment_id}</p><strong>{shipment.shipment_id}</strong>
      <p>{shipment.origin} → {shipment.destination} · {shipment.region}</p>
      <p>{shipment.open_case ? `Open case: ${String(shipment.open_case)}` : "Shipment loaded · existing case check runs on report."}</p>
    </CardContent></Card>}
    {shipment && <form className="mt-5 space-y-5" onSubmit={(event) => void submit(event)}>
      <fieldset><legend className="mb-2 font-semibold">What’s damaged?</legend><div className="flex flex-wrap gap-2">
        {["Crushed box", "Torn packaging", "Wet", "Contents damaged"].map((type) => <label className="flex min-h-11 items-center gap-2 rounded-full border px-4" key={type}>
          <input checked={damageTypes.includes(type)} onChange={(event) => setDamageTypes((current) =>
            event.target.checked ? [...current, type] : current.filter((value) => value !== type))} type="checkbox" />{type}
        </label>)}
      </div></fieldset>
      <label className="block text-sm">Photos · at least 1
        <Input accept="image/jpeg,image/png,image/webp" multiple onChange={(event) => setPhotos(Array.from(event.target.files ?? []))} required type="file" />
      </label>
      {photos.map((file) => <p className="text-sm" key={`${file.name}-${file.size}`}>{file.name}</p>)}
      <fieldset><legend className="mb-2 font-semibold">Contents checked?</legend><div className="flex gap-4">
        {["yes", "no"].map((value) => <label className="flex min-h-11 items-center gap-2" key={value}>
          <input checked={contentsChecked === value} name="contents" onChange={() => setContentsChecked(value)} required type="radio" value={value} />{value === "yes" ? "Yes" : "No"}
        </label>)}
      </div></fieldset>
      <label className="block text-sm">Note · optional
        <textarea className="mt-1 min-h-24 w-full rounded-md border p-3" onChange={(event) => setNote(event.target.value)} value={note} />
      </label>
      <div className="field-sticky-action">
        <Button className="min-h-[52px] w-full" disabled={!damageTypes.length || !photos.length || !contentsChecked} type="submit">Report damage</Button>
      </div>
      <p className="text-center text-sm text-muted-foreground">Creates a Damaged parcel case for Operations</p>
    </form>}
  </>;
}

function SimulatorPage() {
  const resource = useResource(() => apiRequest<CaseItem[]>("/communication/simulator/waiting"), [], 10_000);
  const [caseId, setCaseId] = useState("");
  const [optionType, setOptionType] = useState("redelivery");
  const [slot, setSlot] = useState("09:00–12:00");
  const [feedback, setFeedback] = useState<string | null>(null);
  useEffect(() => {
    if (!caseId && resource.data?.length) setCaseId(resource.data[0].case_id);
  }, [caseId, resource.data]);
  async function submit(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    setFeedback(null);
    try {
      await postJson("/communication/simulator/choice", {
        case_id: caseId, option_type: optionType, slot: optionType === "redelivery" ? slot : null,
      });
      setFeedback("Customer choice recorded in the case timeline.");
      await resource.refresh();
    } catch (cause) { setFeedback(cause instanceof Error ? cause.message : "Choice could not be recorded."); }
  }
  return <>
    <PageTitle title="Simulator: stands in for On Demand Delivery" description="Select a waiting case and submit the customer’s resolution option." />
    {resource.error && <ErrorMessage>{resource.error}</ErrorMessage>}
    {feedback && <p className="mb-4" role="status">{feedback}</p>}
    <Card><CardContent className="p-5">
      <form className="max-w-xl space-y-4" onSubmit={(event) => void submit(event)}>
        <label className="block text-sm">Case waiting for the customer
          <select className="mt-1 h-11 w-full rounded-md border bg-background px-2" onChange={(event) => setCaseId(event.target.value)} required value={caseId}>
            {(resource.data ?? []).map((item) => <option key={item.case_id} value={item.case_id}>{item.case_id} · {typeLabels[item.exception_type]} · {item.shipment_id}</option>)}
          </select>
        </label>
        <label className="block text-sm">Customer choice
          <select className="mt-1 h-11 w-full rounded-md border bg-background px-2" onChange={(event) => setOptionType(event.target.value)} value={optionType}>
            <option value="redelivery">Redelivery</option><option value="pickup_point">Pickup point</option>
          </select>
        </label>
        {optionType === "redelivery" && <label className="block text-sm">Delivery slot
          <select className="mt-1 h-11 w-full rounded-md border bg-background px-2" onChange={(event) => setSlot(event.target.value)} value={slot}>
            <option>09:00–12:00</option><option>12:00–15:00</option><option>15:00–18:00</option>
          </select>
        </label>}
        <Button disabled={!resource.data?.length} type="submit">Send choice to webhook</Button>
      </form>
      {!resource.data?.length && <p className="mt-4 text-sm text-muted-foreground">No cases are waiting for a customer choice.</p>}
    </CardContent></Card>
  </>;
}

function AuthenticatedApp() {
  const { user, loading } = useAuth();
  if (loading) return <Loading label="Loading session…" />;
  if (!user) {
    return <Routes><Route element={<SignInPage />} path="/sign-in" /><Route element={<Navigate replace to="/sign-in" />} path="*" /></Routes>;
  }
  return <Routes>
    <Route element={<AppLayout />} path="/*" />
  </Routes>;
}

export default function App() {
  return <AuthProvider><AuthenticatedApp /></AuthProvider>;
}
