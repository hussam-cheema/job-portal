"use client";

import Link from "next/link";
import { FormEvent, useEffect, useState } from "react";
import { resetAdminCredentials } from "@/lib/api";

export default function ResetPasswordPage() {
  const [token, setToken] = useState("");
  const [tokenReady, setTokenReady] = useState(false);
  const [username, setUsername] = useState("");
  const [password, setPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    const resetToken = new URLSearchParams(window.location.search).get("token") || "";
    setToken(resetToken);
    setTokenReady(true);
  }, []);

  async function onSubmit(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    if (password !== confirmPassword) {
      setError("Passwords do not match.");
      return;
    }
    setLoading(true);
    try {
      const response = await resetAdminCredentials(token, username, password);
      setMessage(response.message);
      setPassword("");
      setConfirmPassword("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Unable to reset credentials");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="site-wrap py-16 max-w-md">
      <h1 className="text-3xl font-semibold text-[var(--navy-100)]">Reset admin credentials</h1>
      <p className="mt-2 text-sm text-[var(--muted)]">
        Choose a new username and password. Your old password is not required.
      </p>

      {tokenReady && !token ? (
        <div className="card-panel mt-8 p-6">
          <p className="field-error">This reset link is missing its security token.</p>
          <Link href="/login" className="btn btn-secondary mt-5 inline-flex">
            Return to login
          </Link>
        </div>
      ) : (
        <form onSubmit={onSubmit} className="card-panel mt-8 p-6 space-y-4">
          <div>
            <label className="field-label" htmlFor="reset-username">New username</label>
            <input
              id="reset-username"
              className="input"
              value={username}
              onChange={(event) => setUsername(event.target.value)}
              autoComplete="username"
              minLength={3}
              maxLength={100}
              pattern="[A-Za-z0-9_.-]+"
              required
            />
          </div>
          <div>
            <label className="field-label" htmlFor="reset-password">New password</label>
            <input
              id="reset-password"
              className="input"
              type="password"
              value={password}
              onChange={(event) => setPassword(event.target.value)}
              autoComplete="new-password"
              minLength={12}
              maxLength={72}
              required
            />
          </div>
          <div>
            <label className="field-label" htmlFor="reset-confirm-password">
              Confirm new password
            </label>
            <input
              id="reset-confirm-password"
              className="input"
              type="password"
              value={confirmPassword}
              onChange={(event) => setConfirmPassword(event.target.value)}
              autoComplete="new-password"
              minLength={12}
              maxLength={72}
              required
            />
          </div>
          {error && <p className="field-error">{error}</p>}
          {message && (
            <p className="text-sm text-emerald-700">
              {message} <Link href="/login" className="underline">Open login</Link>
            </p>
          )}
          <button type="submit" className="btn btn-primary w-full" disabled={loading || !token}>
            {loading ? "Updating credentials…" : "Update username and password"}
          </button>
        </form>
      )}
    </div>
  );
}
