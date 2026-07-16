"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AdminShell } from "@/components/AdminShell";
import { useAdminAuth } from "@/lib/adminAuth";
import {
  adminCreateTaxonomyTerm,
  adminDeleteTaxonomyTerm,
  adminListTaxonomy,
  adminUpdateTaxonomyTerm,
} from "@/lib/api";
import type { TaxonomyTerm } from "@/lib/types";

export default function TaxonomyPage() {
  const { token } = useAdminAuth();
  const [terms, setTerms] = useState<TaxonomyTerm[]>([]);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editSlug, setEditSlug] = useState("");

  const reload = useCallback(async () => {
    if (!token) return;
    setTerms(await adminListTaxonomy(token));
  }, [token]);

  useEffect(() => { reload().catch((err) => setError(err instanceof Error ? err.message : "Load failed")); }, [reload]);

  async function create(event: FormEvent) {
    event.preventDefault();
    if (!token || !name.trim()) return;
    setBusy(true); setError(null);
    try {
      await adminCreateTaxonomyTerm(token, { name: name.trim(), slug: slug.trim() || undefined });
      setName(""); setSlug(""); await reload();
    } catch (err) { setError(err instanceof Error ? err.message : "Create failed"); }
    finally { setBusy(false); }
  }

  async function toggle(term: TaxonomyTerm) {
    if (!token) return;
    setBusy(true); setError(null);
    try { await adminUpdateTaxonomyTerm(token, term.id, { is_active: !term.is_active }); await reload(); }
    catch (err) { setError(err instanceof Error ? err.message : "Update failed"); }
    finally { setBusy(false); }
  }

  async function remove(term: TaxonomyTerm) {
    if (!token || !window.confirm(`Delete “${term.name}”?`)) return;
    setBusy(true); setError(null);
    try { await adminDeleteTaxonomyTerm(token, term.id); await reload(); }
    catch (err) { setError(err instanceof Error ? err.message : "Delete failed"); }
    finally { setBusy(false); }
  }

  async function saveEdit(term: TaxonomyTerm) {
    if (!token || !editName.trim() || !editSlug.trim()) return;
    setBusy(true); setError(null);
    try {
      await adminUpdateTaxonomyTerm(token, term.id, { name: editName.trim(), slug: editSlug.trim() });
      setEditing(null); await reload();
    } catch (err) { setError(err instanceof Error ? err.message : "Update failed"); }
    finally { setBusy(false); }
  }

  return (
    <AdminShell>
      <div className="space-y-5">
        <section className="card-panel p-5">
          <h2 className="text-xl font-semibold text-[var(--navy-100)]">Tags / categories</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">Define the only categories available when creating or editing job posts.</p>
          {error && <p className="field-error mt-3">{error}</p>}
          <form className="mt-5 grid gap-3 sm:grid-cols-[1fr_1fr_auto]" onSubmit={create}>
            <div><label className="field-label">Name</label><input className="input" value={name} onChange={(e) => setName(e.target.value)} required /></div>
            <div><label className="field-label">Slug (optional)</label><input className="input" value={slug} onChange={(e) => setSlug(e.target.value)} placeholder="auto-generated" /></div>
            <button className="btn btn-primary self-end" type="submit" disabled={busy}>Add category</button>
          </form>
        </section>
        <section className="card-panel overflow-hidden">
          {terms.length === 0 ? <p className="p-5 text-sm text-[var(--muted)]">No tags/categories defined.</p> : (
            <div className="divide-y divide-[var(--border)]">
              {terms.map((term) => (
                <div key={term.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
                  {editing === term.id ? (
                    <div className="grid flex-1 gap-2 sm:grid-cols-2">
                      <input aria-label="Category name" className="input" value={editName} onChange={(e) => setEditName(e.target.value)} />
                      <input aria-label="Category slug" className="input" value={editSlug} onChange={(e) => setEditSlug(e.target.value)} />
                    </div>
                  ) : <div><div className="font-medium text-[var(--navy-100)]">{term.name}</div><code className="text-xs text-[var(--muted)]">/{term.slug}</code></div>}
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-semibold ${term.is_active ? "text-[var(--success)]" : "text-[var(--muted)]"}`}>{term.is_active ? "Active" : "Inactive"}</span>
                    <button className="btn btn-ghost" type="button" disabled={busy} onClick={() => toggle(term)}>{term.is_active ? "Deactivate" : "Activate"}</button>
                    {editing === term.id ? (
                      <><button className="btn btn-primary" type="button" disabled={busy} onClick={() => saveEdit(term)}>Save</button><button className="btn btn-ghost" type="button" onClick={() => setEditing(null)}>Cancel</button></>
                    ) : <button className="btn btn-ghost" type="button" disabled={busy} onClick={() => { setEditing(term.id); setEditName(term.name); setEditSlug(term.slug); }}>Edit</button>}
                    <button className="btn btn-ghost text-red-500" type="button" disabled={busy} onClick={() => remove(term)}>Delete</button>
                  </div>
                </div>
              ))}
            </div>
          )}
        </section>
      </div>
    </AdminShell>
  );
}
