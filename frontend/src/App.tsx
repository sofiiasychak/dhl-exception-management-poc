import { useState, type FormEvent } from "react";
import { Navigate, Route, Routes, useNavigate } from "react-router-dom";

import { AuthProvider, useAuth, type Role } from "./auth";
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
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <main className="flex min-h-screen items-center justify-center p-4">
      <Card className="w-full max-w-lg">
        <CardHeader>
          <CardTitle>Exception Management</CardTitle>
          <CardDescription>Sign in with your company account.</CardDescription>
        </CardHeader>
        <CardContent>
          <form className="space-y-4" onSubmit={(event) => void submit(event)}>
            <div className="space-y-2">
              <label className="text-sm font-medium" htmlFor="email">Email</label>
              <Input
                autoComplete="username"
                disabled={mfaSession !== null}
                id="email"
                onChange={(event) => setEmail(event.target.value)}
                required
                type="email"
                value={email}
              />
            </div>
            {mfaSession ? (
              <div className="space-y-2">
                <label className="text-sm font-medium" htmlFor="mfa-code">Authenticator code</label>
                <Input
                  autoComplete="one-time-code"
                  id="mfa-code"
                  inputMode="numeric"
                  maxLength={6}
                  onChange={(event) => setMfaCode(event.target.value)}
                  pattern="[0-9]{6}"
                  required
                  value={mfaCode}
                />
              </div>
            ) : (
              <div className="space-y-2">
                <label className="text-sm font-medium" htmlFor="password">Password</label>
                <Input
                  autoComplete="current-password"
                  id="password"
                  onChange={(event) => setPassword(event.target.value)}
                  required
                  type="password"
                  value={password}
                />
              </div>
            )}
            {error && <p className="text-sm font-medium text-destructive" role="alert">{error}</p>}
            <Button className="w-full" disabled={submitting} type="submit">
              {mfaSession ? "Verify code" : "Sign in"}
            </Button>
            {mfaSession && (
              <Button
                className="w-full"
                disabled={submitting}
                onClick={() => {
                  setMfaSession(null);
                  setMfaCode("");
                }}
                type="button"
                variant="outline"
              >
                Use a different account
              </Button>
            )}
          </form>

          {localDemoEnabled && !mfaSession && (
            <section aria-labelledby="demo-users-title" className="mt-8 border-t pt-6">
              <h2 className="mb-1 text-lg font-semibold" id="demo-users-title">Local test sign-in</h2>
              <p className="mb-4 text-sm text-muted-foreground">Fictional demo users · local environment only</p>
              <div className="grid gap-2 sm:grid-cols-2">
                {demoUsers.map((demo) => (
                  <Button
                    className="h-auto min-h-11 justify-start whitespace-normal py-3 text-left"
                    disabled={submitting}
                    key={demo.id}
                    onClick={() => void signInDemo(demo.id).catch(() => undefined)}
                    type="button"
                    variant="outline"
                  >
                    {demo.name} · {roleTitles[demo.role]} · {demo.scope}
                  </Button>
                ))}
              </div>
            </section>
          )}
        </CardContent>
      </Card>
    </main>
  );
}

function RolePage() {
  const { user, signOut } = useAuth();
  if (!user) return <Navigate replace to="/sign-in" />;

  const isFieldApp = user.role === "courier" || user.role === "depot";
  const navigation: Record<Role, Array<{ label: string; disabled?: boolean }>> = {
    ops: [
      { label: "Cases" },
      { label: "At-risk shipments", disabled: true },
      { label: "Create case" },
      { label: "Dashboards", disabled: true },
    ],
    support: [
      { label: "Customer updates" },
      { label: "Shipment lookup" },
      { label: "Report a problem" },
    ],
    courier: [{ label: "My actions" }, { label: "Scan" }, { label: "Profile" }],
    depot: [{ label: "My actions" }, { label: "Scan" }, { label: "Profile" }],
  };

  return (
    <div className={isFieldApp ? "mx-auto min-h-screen w-full max-w-[390px] border-x bg-background" : "min-h-screen"}>
      <header className="flex min-h-16 items-center justify-between border-b px-5 py-3">
        <div>
          <p className="font-semibold">Exception Management</p>
          <p className="text-sm text-muted-foreground">
            {roleTitles[user.role]} · {user.email}
          </p>
        </div>
        <Button onClick={signOut} type="button" variant="outline">Sign out</Button>
      </header>
      <div className={isFieldApp ? "p-5" : "grid min-h-[calc(100vh-4rem)] grid-cols-[15rem_1fr]"}>
        {!isFieldApp && (
          <nav aria-label={`${roleTitles[user.role]} navigation`} className="border-r p-4">
            <ul className="space-y-2">
              {navigation[user.role].map((item) => (
                <li key={item.label}>
                  <button
                    className="min-h-11 w-full rounded-md px-3 text-left text-sm disabled:cursor-not-allowed disabled:text-muted-foreground"
                    disabled={item.disabled}
                    type="button"
                  >
                    {item.label}{item.disabled ? " · later" : ""}
                  </button>
                </li>
              ))}
            </ul>
          </nav>
        )}
        <main className={isFieldApp ? "" : "p-8"}>
          <h1 className="text-2xl font-semibold">{roleTitles[user.role]}</h1>
          <p className="mt-2 text-muted-foreground">Your {roleTitles[user.role].toLowerCase()} workspace is ready.</p>
          <Card className="mt-6">
            <CardContent className="pt-6">
              <p className="text-sm text-muted-foreground">No work items are shown in this foundation build.</p>
            </CardContent>
          </Card>
        </main>
      </div>
    </div>
  );
}

function AuthenticatedApp() {
  const { user, loading } = useAuth();
  if (loading) return <main className="p-8" aria-live="polite">Loading session…</main>;
  return (
    <Routes>
      <Route element={user ? <Navigate replace to="/app" /> : <SignInPage />} path="/sign-in" />
      <Route element={user ? <RolePage /> : <Navigate replace to="/sign-in" />} path="/app" />
      <Route element={<Navigate replace to={user ? "/app" : "/sign-in"} />} path="*" />
    </Routes>
  );
}

export default function App() {
  return (
    <AuthProvider>
      <AuthenticatedApp />
    </AuthProvider>
  );
}
