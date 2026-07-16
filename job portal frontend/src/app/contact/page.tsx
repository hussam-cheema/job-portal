"use client";

import { FormEvent, useEffect, useState } from "react";
import Link from "next/link";
import { fetchPage, submitContact } from "@/lib/api";

const LIMITS = {
  name: 50,
  subject: 50,
  email: 100,
  message: 300,
};

function isValidEmail(email: string): boolean {
  return /^[a-zA-Z0-9._%+\-]+@[a-zA-Z0-9.\-]+\.[a-zA-Z]{2,}$/.test(email);
}

export default function ContactPage() {
  const [pageTitle, setPageTitle] = useState("Contact Us");
  const [pageContent, setPageContent] = useState(
    "<p>Questions, partnership ideas, or corrections to a listing? Send a message below.</p>"
  );
  const [name, setName] = useState("");
  const [email, setEmail] = useState("");
  const [subject, setSubject] = useState("");
  const [message, setMessage] = useState("");
  const [status, setStatus] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);

  useEffect(() => {
    void fetchPage("contact").then((page) => {
      if (!page) return;
      setPageTitle(page.title);
      setPageContent(page.content);
    });
  }, []);

  function clientValidate(): string | null {
    if (!name.trim()) return "Name is required";
    if (name.trim().length > LIMITS.name) return `Name must be ≤ ${LIMITS.name} characters`;
    if (!email.trim()) return "Email is required";
    if (email.trim().length > LIMITS.email) return `Email must be ≤ ${LIMITS.email} characters`;
    if (!isValidEmail(email.trim())) return "Enter a valid email address";
    if (subject.trim().length > LIMITS.subject)
      return `Subject must be ≤ ${LIMITS.subject} characters`;
    if (!message.trim()) return "Message is required";
    if (message.trim().length > LIMITS.message)
      return `Message must be ≤ ${LIMITS.message} characters`;
    return null;
  }

  async function onSubmit(e: FormEvent) {
    e.preventDefault();
    setLoading(true);
    setError(null);
    setStatus(null);
    const v = clientValidate();
    if (v) {
      setError(v);
      setLoading(false);
      return;
    }
    const res = await submitContact({
      name: name.trim().slice(0, LIMITS.name),
      email: email.trim().slice(0, LIMITS.email),
      subject: subject.trim().slice(0, LIMITS.subject),
      message: message.trim().slice(0, LIMITS.message),
    });
    setLoading(false);
    if (!res.ok) {
      setError(res.error || "Failed to send");
      return;
    }
    setStatus("Message sent. We will get back to you soon.");
    setName("");
    setEmail("");
    setSubject("");
    setMessage("");
  }

  return (
    <div className="site-wrap max-w-3xl py-12">
      <Link href="/" className="text-sm text-[var(--muted)] hover:text-[var(--navy-200)]">
        ← Jobs
      </Link>
      <h1 className="mt-6 text-3xl font-semibold text-[var(--navy-100)]">{pageTitle}</h1>
      <div
        className="prose-job mt-3 text-[var(--navy-200)] leading-relaxed"
        dangerouslySetInnerHTML={{ __html: pageContent }}
      />

      <form onSubmit={onSubmit} className="card-panel mt-8 p-6 space-y-4">
        <div className="grid sm:grid-cols-2 gap-4">
          <div>
            <label className="field-label">Name (max {LIMITS.name})</label>
            <input
              className="input"
              value={name}
              maxLength={LIMITS.name}
              onChange={(e) => setName(e.target.value)}
              required
            />
            <p className="text-xs text-[var(--muted)] mt-1">
              {name.length}/{LIMITS.name}
            </p>
          </div>
          <div>
            <label className="field-label">Email (max {LIMITS.email})</label>
            <input
              className="input"
              type="email"
              value={email}
              maxLength={LIMITS.email}
              onChange={(e) => setEmail(e.target.value)}
              required
            />
            <p className="text-xs text-[var(--muted)] mt-1">
              {email.length}/{LIMITS.email}
            </p>
          </div>
        </div>
        <div>
          <label className="field-label">Subject (max {LIMITS.subject})</label>
          <input
            className="input"
            value={subject}
            maxLength={LIMITS.subject}
            onChange={(e) => setSubject(e.target.value)}
          />
          <p className="text-xs text-[var(--muted)] mt-1">
            {subject.length}/{LIMITS.subject}
          </p>
        </div>
        <div>
          <label className="field-label">Message (max {LIMITS.message})</label>
          <textarea
            className="input min-h-[140px]"
            value={message}
            maxLength={LIMITS.message}
            onChange={(e) => setMessage(e.target.value)}
            required
          />
          <p className="text-xs text-[var(--muted)] mt-1">
            {message.length}/{LIMITS.message}
          </p>
        </div>
        {error && <p className="field-error">{error}</p>}
        {status && <p className="text-sm text-[var(--success)]">{status}</p>}
        <button type="submit" className="btn btn-primary" disabled={loading}>
          {loading ? "Sending…" : "Send message"}
        </button>
      </form>
    </div>
  );
}
