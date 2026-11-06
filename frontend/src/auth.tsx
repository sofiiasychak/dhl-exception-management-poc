import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? "/api";
const TOKEN_KEY = "exception-management-id-token";

export type Role = "ops" | "support" | "courier" | "depot";
export type User = { user_id: string; role: Role; email: string };

type AuthContextValue = {
  user: User | null;
  loading: boolean;
  error: string | null;
  signIn: (email: string, password: string) => Promise<string | null>;
  completeMfa: (email: string, session: string, code: string) => Promise<void>;
  demoSignIn: (userId: string) => Promise<void>;
  signOut: () => void;
};

const AuthContext = createContext<AuthContextValue | null>(null);

async function fetchUser(token: string): Promise<User> {
  const response = await fetch(`${API_BASE_URL}/auth/me`, {
    headers: { Authorization: `Bearer ${token}` },
  });
  if (!response.ok) throw new Error("Your session has expired. Please sign in again.");
  return response.json() as Promise<User>;
}

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<User | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    const token = localStorage.getItem(TOKEN_KEY);
    if (!token) {
      setLoading(false);
      return;
    }
    fetchUser(token)
      .then(setUser)
      .catch(() => localStorage.removeItem(TOKEN_KEY))
      .finally(() => setLoading(false));
  }, []);

  const authenticate = useCallback(async (endpoint: string, body: object): Promise<string | null> => {
    setError(null);
    const response = await fetch(`${API_BASE_URL}/auth/${endpoint}`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(body),
    });
    if (!response.ok) {
      const payload = (await response.json()) as { detail?: string };
      throw new Error(payload.detail ?? "Unable to sign in.");
    }
    const payload = (await response.json()) as {
      id_token?: string;
      challenge_name?: string;
      session?: string;
    };
    if (!payload.id_token) {
      if (payload.challenge_name === "SOFTWARE_TOKEN_MFA" && payload.session) {
        return payload.session;
      }
      throw new Error("The sign-in challenge is not supported.");
    }
    localStorage.setItem(TOKEN_KEY, payload.id_token);
    const nextUser = await fetchUser(payload.id_token);
    setUser(nextUser);
    return null;
  }, []);

  const signIn = useCallback(async (email: string, password: string) => {
    try {
      return await authenticate("login", { email, password });
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Unable to sign in.";
      setError(message);
      throw cause;
    }
  }, [authenticate]);

  const completeMfa = useCallback(async (email: string, session: string, code: string) => {
    try {
      await authenticate("challenge", { email, session, code });
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Unable to verify the code.";
      setError(message);
      throw cause;
    }
  }, [authenticate]);

  const demoSignIn = useCallback(async (userId: string) => {
    try {
      const challenge = await authenticate("demo-login", { user_id: userId });
      if (challenge) throw new Error("Local demo sign-in cannot require MFA.");
    } catch (cause) {
      const message = cause instanceof Error ? cause.message : "Local sign-in is unavailable.";
      setError(message);
      throw cause;
    }
  }, [authenticate]);

  const signOut = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    setUser(null);
    setError(null);
  }, []);

  const value = useMemo(
    () => ({ user, loading, error, signIn, completeMfa, demoSignIn, signOut }),
    [user, loading, error, signIn, completeMfa, demoSignIn, signOut],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const context = useContext(AuthContext);
  if (!context) throw new Error("useAuth must be used inside AuthProvider.");
  return context;
}
