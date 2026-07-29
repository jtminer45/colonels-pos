import { useState, type FormEvent } from "react";
import { useAuth } from "../contexts/AuthContext";
import { api, ApiError } from "../api/client";

export default function ChangePasswordPage() {
  const { user, completePasswordChange, logout } = useAuth();
  const [pw1, setPw1] = useState("");
  const [pw2, setPw2] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitting, setSubmitting] = useState(false);

  async function handleSubmit(e: FormEvent) {
    e.preventDefault();
    setError(null);
    if (pw1.length < 8) {
      setError("Password must be at least 8 characters.");
      return;
    }
    if (pw1 !== pw2) {
      setError("Passwords do not match.");
      return;
    }
    setSubmitting(true);
    try {
      await api.changePassword(pw1);
      completePasswordChange();
    } catch (e) {
      setError(e instanceof ApiError ? e.message : "Could not update password.");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="min-h-screen flex items-center justify-center bg-brand-navy px-6">
      <div className="w-full max-w-sm">
        <div className="flex flex-col items-center mb-8">
          <img src="/logo.png" alt="" className="w-16 h-16 rounded-xl mb-3" />
          <h1 className="text-lg font-semibold text-center">Set a New Password</h1>
          <p className="text-sm text-white/50">Welcome, {user?.username}. This temporary password must be changed.</p>
        </div>

        <form onSubmit={handleSubmit} className="bg-brand-surface rounded-2xl p-6 space-y-4 shadow-xl">
          <div>
            <label className="block text-sm text-white/70 mb-1">New password</label>
            <input
              type="password"
              className="w-full rounded-xl bg-brand-surface2 border border-white/10 px-4 py-3 text-lg outline-none focus:border-brand-red"
              value={pw1}
              onChange={(e) => setPw1(e.target.value)}
            />
          </div>
          <div>
            <label className="block text-sm text-white/70 mb-1">Confirm new password</label>
            <input
              type="password"
              className="w-full rounded-xl bg-brand-surface2 border border-white/10 px-4 py-3 text-lg outline-none focus:border-brand-red"
              value={pw2}
              onChange={(e) => setPw2(e.target.value)}
            />
          </div>

          {error && (
            <div className="text-brand-red text-sm bg-brand-red/10 border border-brand-red/30 rounded-lg px-3 py-2">
              {error}
            </div>
          )}

          <button
            type="submit"
            disabled={submitting}
            className="tap-target w-full rounded-xl bg-brand-red disabled:opacity-40 py-4 text-lg font-semibold"
          >
            {submitting ? "Saving…" : "Set Password"}
          </button>
          <button
            type="button"
            onClick={() => logout()}
            className="tap-target w-full rounded-xl border border-white/15 py-3 text-sm text-white/60"
          >
            Cancel and log out
          </button>
        </form>
      </div>
    </div>
  );
}
