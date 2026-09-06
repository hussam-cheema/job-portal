"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";
import { requestStudentApiCode, verifyStudentApiCode } from "@/lib/api";
import type { StudentApiKey } from "@/lib/types";

const API_ROOT = "https://api.pakistanjobsmarket.com/api/student/v1";

const ENDPOINTS = [
  ["GET", "/jobs", "List job posts. Supports page, page_size (maximum 25), and q."],
  ["GET", "/jobs/{slug}", "Retrieve one job with its full description, advertisement images, and attachments."],
  ["GET", "/blog-posts", "List published blog posts. Supports page, page_size (maximum 25), and q."],
  ["GET", "/blog-posts/{slug}", "Retrieve one published blog post with its complete content."],
  ["GET", "/quota", "Check your quota without using a data request."],
] as const;

function CopyButton({ value, label = "Copy" }: { value: string; label?: string }) {
  const [copied, setCopied] = useState(false);

  async function copy() {
    try {
      await navigator.clipboard.writeText(value);
      setCopied(true);
      window.setTimeout(() => setCopied(false), 1800);
    } catch {
      setCopied(false);
    }
  }

  return <button type="button" className="student-api-copy" onClick={copy}>{copied ? "Copied" : label}</button>;
}

export function StudentApiAccess() {
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [stage, setStage] = useState<"email" | "code" | "key">("email");
  const [key, setKey] = useState<StudentApiKey | null>(null);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [subscriptionRequired, setSubscriptionRequired] = useState(false);
  const [busy, setBusy] = useState(false);

  const cleanEmail = useMemo(() => email.trim().toLowerCase(), [email]);
  const curlExample = `curl "${API_ROOT}/jobs?page=1&page_size=10" \\\n  -H "X-API-Key: YOUR_API_KEY"`;
  const javascriptExample = `const response = await fetch("${API_ROOT}/blog-posts?page=1", {
  headers: { "X-API-Key": "YOUR_API_KEY" }
});
const data = await response.json();
console.log(data.items, data.quota);`;
  const pythonExample = `import requests

response = requests.get(
    "${API_ROOT}/jobs",
    headers={"X-API-Key": "YOUR_API_KEY"},
    params={"page": 1, "page_size": 10}
)
data = response.json()
print(data["items"])`;

  async function requestCode(event?: FormEvent) {
    event?.preventDefault();
    setError(null);
    setMessage(null);
    setSubscriptionRequired(false);
    if (!/^[^\s@]+@[^\s@]+\.[^\s@]{2,}$/.test(cleanEmail)) {
      setError("Enter a valid subscribed email address.");
      return;
    }
    setBusy(true);
    try {
      const result = await requestStudentApiCode(cleanEmail);
      setMessage(result.message);
      if (result.status === "code_sent") {
        setStage("code");
        setCode("");
      } else {
        setSubscriptionRequired(true);
      }
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to send a verification code.");
    } finally {
      setBusy(false);
    }
  }

  async function verifyCode(event: FormEvent) {
    event.preventDefault();
    setError(null);
    setMessage(null);
    if (!/^\d{6}$/.test(code)) {
      setError("Enter the six-digit code from your email.");
      return;
    }
    setBusy(true);
    try {
      const result = await verifyStudentApiCode(cleanEmail, code);
      setKey(result);
      setStage("key");
      setCode("");
      setMessage(result.message);
    } catch (caught) {
      setError(caught instanceof Error ? caught.message : "Unable to verify this code.");
    } finally {
      setBusy(false);
    }
  }

  function restart() {
    setStage("email");
    setKey(null);
    setCode("");
    setMessage(null);
    setError(null);
    setSubscriptionRequired(false);
  }

  return <div className="student-api-shell">
    <section className="student-api-access-card" aria-labelledby="student-api-access-title">
      <div className="student-api-access-intro">
        <p className="tool-kicker">Subscriber access</p>
        <h2 id="student-api-access-title">Create your student API key</h2>
        <p>Use your active newsletter email. We will send a one-time code before showing a newly generated key.</p>
        <div className="student-api-quota-badge"><strong>50</strong><span>lifetime data requests per subscriber</span></div>
      </div>

      <div className="student-api-access-form">
        {stage === "email" && <form onSubmit={requestCode} noValidate>
          <label className="field-label" htmlFor="student-api-email">Newsletter email</label>
          <div className="student-api-input-action">
            <input id="student-api-email" className="input" type="email" inputMode="email" autoComplete="email" maxLength={320} value={email} onChange={(event) => setEmail(event.target.value)} placeholder="you@example.com" required />
            <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? "Checking…" : "Email me a code"}</button>
          </div>
        </form>}

        {stage === "code" && <form onSubmit={verifyCode} noValidate>
          <div className="student-api-form-heading"><span>Code sent to</span><strong>{cleanEmail}</strong><button type="button" onClick={restart}>Change email</button></div>
          <label className="field-label" htmlFor="student-api-code">Six-digit verification code</label>
          <div className="student-api-input-action">
            <input id="student-api-code" className="input student-api-code-input" type="text" inputMode="numeric" autoComplete="one-time-code" maxLength={6} pattern="[0-9]{6}" value={code} onChange={(event) => setCode(event.target.value.replace(/\D/g, "").slice(0, 6))} placeholder="000000" required />
            <button className="btn btn-primary" type="submit" disabled={busy}>{busy ? "Verifying…" : "Verify and create key"}</button>
          </div>
          <button className="student-api-resend" type="button" disabled={busy} onClick={() => void requestCode()}>Send another code</button>
        </form>}

        {stage === "key" && key && <div className="student-api-key-result" role="status">
          <div className="student-api-key-result-head"><span aria-hidden="true">✓</span><div><strong>API key created</strong><p>Copy it now. For security, the complete key will not be shown again.</p></div></div>
          <div className="student-api-secret"><code>{key.api_key}</code><CopyButton value={key.api_key} label="Copy key" /></div>
          <div className="student-api-key-stats">
            <span><small>Used</small><strong>{key.requests_used}</strong></span>
            <span className="student-api-requests-left"><small>Requests left</small><strong>{key.requests_remaining}</strong></span>
            <span><small>Total</small><strong>{key.quota_total}</strong></span>
          </div>
          <button type="button" className="btn btn-ghost" onClick={restart}>Generate a replacement key</button>
          <p className="student-api-rotation-note">A replacement invalidates the old key but does not reset your lifetime quota.</p>
        </div>}

        {message && <p className="student-api-message" role="status">{message}</p>}
        {error && <p className="student-api-error" role="alert">{error}</p>}
        {subscriptionRequired && <p className="student-api-subscribe-note">Not subscribed yet? <Link href="/#job-alerts">Subscribe to job alerts</Link>, then return here to request your code.</p>}
        <p className="student-api-privacy">Codes expire after 10 minutes. Raw codes and full API keys are never stored by Pakistan Jobs Market.</p>
      </div>
    </section>

    <section className="student-api-docs" aria-labelledby="student-api-docs-title">
      <header>
        <div><p className="tool-kicker">Documentation</p><h2 id="student-api-docs-title">Read jobs and blog posts</h2><p>This read-only API is made especially for students building coursework, portfolio apps, dashboards and data projects.</p></div>
        <div className="student-api-base-url"><span>Base URL</span><code>{API_ROOT}</code><CopyButton value={API_ROOT} /></div>
      </header>

      <div className="student-api-docs-grid">
        <article className="student-api-doc-section">
          <span className="student-api-doc-number">01</span>
          <h3>Authenticate every request</h3>
          <p>Send the key in an <code>X-API-Key</code> header. A Bearer token in the <code>Authorization</code> header also works.</p>
          <pre><code>{curlExample}</code></pre>
        </article>
        <article className="student-api-doc-section">
          <span className="student-api-doc-number">02</span>
          <h3>Available endpoints</h3>
          <div className="student-api-endpoints">
            {ENDPOINTS.map(([method, path, description]) => <div key={path}><span>{method}</span><code>{path}</code><p>{description}</p></div>)}
          </div>
        </article>
      </div>

      <article className="student-api-examples">
        <h3>Starter examples</h3>
        <div>
          <section><header><strong>JavaScript (Node.js)</strong><CopyButton value={javascriptExample} /></header><pre><code>{javascriptExample}</code></pre></section>
          <section><header><strong>Python</strong><CopyButton value={pythonExample} /></header><pre><code>{pythonExample}</code></pre></section>
        </div>
      </article>

      <aside className="student-api-response-guide">
        <div><strong>Complete content</strong><p>Jobs include HTML in <code>description</code>, extracted <code>advertisement_images</code>, and public attachment metadata. Blogs include full HTML in <code>content</code>. Sanitize HTML before displaying it in your own app.</p></div>
        <div><strong>Pagination and search</strong><p>List endpoints accept <code>page</code>, <code>page_size</code> up to 25, and optional <code>q</code>. Every response includes pagination and remaining quota.</p></div>
        <div><strong>Quota and safety</strong><p>Each data call uses one of 50 lifetime requests. The quota endpoint is free. Never expose your key in public browser code or commit it to Git.</p></div>
      </aside>
    </section>
  </div>;
}
