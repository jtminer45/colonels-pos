import { useState, type FormEvent } from "react";
import { useAuth } from "../contexts/AuthContext";

export default function LoginPage() {
  const { login, error, clearError } = useAuth();
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    if (!username || !password) return;
    setSubmitting(true);
    try {
      await login(username, password);
    } catch {
      // error is already surfaced via useAuth().error
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-brand-navy px-6">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <img src="/logo.png" alt="Colonel's Bakery and Restaurant" className="w-20 h-20 rounded-xl mb-3" />
          <h1 className="text-xl font-semibold text-center">Colonel's Bakery &amp; Restaurant</h1>
          <p className="text-sm text-white/50">Till Clock-In</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-brand-surface rounded-2xl p-6 space-y-4 shadow-xl">
          <div>
            <label className="block text-sm text-white/70 mb-1">Username</label>
            <input
              className="w-full rounded-xl bg-brand-surface2 border border-white/10 px-4 py-3 text-lg outline-none focus:border-brand-red"
              value={username}
              onChange={(e) => {
                setUsername(e.target.value);
                clearError();
              }}
              autoCapitalize="none"
              autoCorrect="off"
              autoComplete="username"
            />
          </div>
          <div>
            <label className="block text-sm text-white/70 mb-1">Password</label>
            <input
              type="password"
              className="w-full rounded-xl bg-brand-surface2 border border-white/10 px-4 py-3 text-lg outline-none focus:border-brand-red"
              value={password}
              onChange={(e) => {
                setPassword(e.target.value);
                clearError();
              }}
              autoComplete="current-password"
            />
          </div>

          {error && (
            <div className="text-brand-red text-sm bg-brand-red/10 border border-brand-red/30 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting || !username || !password}
            className="tap-target w-full rounded-xl bg-brand-red disabled:opacity-40 py-4 text-lg font-semibold"
          >
            {submitting ? "Logging in…" : "Log In"}
          </button>
        </form>

        <p className="text-center text-xs text-white/30 mt-6">
          Accounts are created by a manager. There is no self sign-up.
        </p>
      </div>
    </div>
  );
}
