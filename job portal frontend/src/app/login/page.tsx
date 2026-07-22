"use client";

import { FormEvent, useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { adminLogin } from "@/lib/api";
import { useAdminAuth } from "@/lib/adminAuth";

export default function LoginPage() {
  const router = useRouter();
  const { login, token, ready } = useAdminAuth();
  const [username, setUsername] = useState("admin");
  const [password, setPassword] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    if (ready && token) router.replace("/admin");
  }, [ready, router, token]);

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    try {
      const res = await adminLogin(username, password);
      login(res.access_token, res.username);
      router.push("/admin");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Login failed");
    } finally {
      setLoading(false);
    }
  }

  return (
    <div className="site-wrap py-16 max-w-md">
      <h1 className="text-3xl font-semibold text-[var(--navy-100)]">Admin login</h1>
      <p className="mt-2 text-sm text-[var(--muted)]">
        Sign in to manage job posts, pages, and messages.
      </p>
      <form onSubmit={onSubmit} className="card-panel mt-8 p-6 space-y-4">
        <div>
          <label className="field-label">Username</label>
          <input
            className="input"
            value={username}
            onChange={(e) => setUsername(e.target.value)}
            autoComplete="username"
            required
          />
        </div>
        <div>
          <label className="field-label">Password</label>
          <input
            className="input"
            type="password"
            value={password}
            onChange={(e) => setPassword(e.target.value)}
            autoComplete="current-password"
            required
          />
        </div>
        {error && <p className="field-error">{error}</p>}
        <button type="submit" className="btn btn-primary w-full" disabled={loading}>
          {loading ? "Signing in…" : "Sign in"}
        </button>
      </form>
    </div>
  );
}
