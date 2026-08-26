"use client";

import { FormEvent, useCallback, useEffect, useState } from "react";
import { AdminShell } from "@/components/AdminShell";
import { useAdminAuth } from "@/lib/adminAuth";
import {
  adminCreateCity,
  adminDeleteTaxonomyTerm,
  adminListCities,
  adminUpdateTaxonomyTerm,
} from "@/lib/api";
import type { TaxonomyTerm } from "@/lib/types";

export default function CitiesPage() {
  const { token } = useAdminAuth();
  const [cities, setCities] = useState<TaxonomyTerm[]>([]);
  const [name, setName] = useState("");
  const [slug, setSlug] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [editing, setEditing] = useState<string | null>(null);
  const [editName, setEditName] = useState("");
  const [editSlug, setEditSlug] = useState("");

  const reload = useCallback(async () => {
    if (!token) return;
    setCities(await adminListCities(token));
  }, [token]);

  useEffect(() => {
    reload().catch((err) => setError(err instanceof Error ? err.message : "Load failed"));
  }, [reload]);

  async function create(event: FormEvent) {
    event.preventDefault();
    if (!token || !name.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await adminCreateCity(token, {
        name: name.trim(),
        slug: slug.trim() || undefined,
      });
      setName("");
      setSlug("");
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Create failed");
    } finally {
      setBusy(false);
    }
  }

  async function toggle(city: TaxonomyTerm) {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      await adminUpdateTaxonomyTerm(token, city.id, { is_active: !city.is_active });
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }

  async function remove(city: TaxonomyTerm) {
    if (!token || !window.confirm(`Delete city “${city.name}”?`)) return;
    setBusy(true);
    setError(null);
    try {
      await adminDeleteTaxonomyTerm(token, city.id);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Delete failed");
    } finally {
      setBusy(false);
    }
  }

  async function saveEdit(city: TaxonomyTerm) {
    if (!token || !editName.trim() || !editSlug.trim()) return;
    setBusy(true);
    setError(null);
    try {
      await adminUpdateTaxonomyTerm(token, city.id, {
        name: editName.trim(),
        slug: editSlug.trim(),
      });
      setEditing(null);
      await reload();
    } catch (err) {
      setError(err instanceof Error ? err.message : "Update failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AdminShell>
      <div className="space-y-5">
        <section className="card-panel p-5">
          <h2 className="text-xl font-semibold text-[var(--navy-100)]">Cities</h2>
          <p className="mt-1 text-sm text-[var(--muted)]">
            Define the cities available in the City / Cities field when creating or editing job posts.
          </p>
          {error && <p className="field-error mt-3">{error}</p>}
          <form className="mt-5 grid gap-3 sm:grid-cols-[1fr_1fr_auto]" onSubmit={create}>
            <div>
              <label className="field-label" htmlFor="city-name">Name</label>
              <input id="city-name" className="input" value={name} onChange={(event) => setName(event.target.value)} required />
            </div>
            <div>
              <label className="field-label" htmlFor="city-slug">Slug (optional)</label>
              <input id="city-slug" className="input" value={slug} onChange={(event) => setSlug(event.target.value)} placeholder="auto-generated" />
            </div>
            <button className="btn btn-primary self-end" type="submit" disabled={busy}>Add city</button>
          </form>
        </section>

        <section className="card-panel overflow-hidden">
          {cities.length === 0 ? (
            <p className="p-5 text-sm text-[var(--muted)]">No cities defined.</p>
          ) : (
            <div className="divide-y divide-[var(--border)]">
              {cities.map((city) => (
                <div key={city.id} className="flex flex-wrap items-center justify-between gap-3 p-4">
                  {editing === city.id ? (
                    <div className="grid flex-1 gap-2 sm:grid-cols-2">
                      <input aria-label="City name" className="input" value={editName} onChange={(event) => setEditName(event.target.value)} />
                      <input aria-label="City slug" className="input" value={editSlug} onChange={(event) => setEditSlug(event.target.value)} />
                    </div>
                  ) : (
                    <div>
                      <div className="font-medium text-[var(--navy-100)]">{city.name}</div>
                      <code className="text-xs text-[var(--muted)]">/{city.slug}</code>
                    </div>
                  )}
                  <div className="flex items-center gap-2">
                    <span className={`text-xs font-semibold ${city.is_active ? "text-[var(--success)]" : "text-[var(--muted)]"}`}>
                      {city.is_active ? "Active" : "Inactive"}
                    </span>
                    <button className="btn btn-ghost" type="button" disabled={busy} onClick={() => toggle(city)}>
                      {city.is_active ? "Deactivate" : "Activate"}
                    </button>
                    {editing === city.id ? (
                      <>
                        <button className="btn btn-primary" type="button" disabled={busy} onClick={() => saveEdit(city)}>Save</button>
                        <button className="btn btn-ghost" type="button" onClick={() => setEditing(null)}>Cancel</button>
                      </>
                    ) : (
                      <button className="btn btn-ghost" type="button" disabled={busy} onClick={() => { setEditing(city.id); setEditName(city.name); setEditSlug(city.slug); }}>Edit</button>
                    )}
                    <button className="btn btn-ghost text-red-500" type="button" disabled={busy} onClick={() => remove(city)}>Delete</button>
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
