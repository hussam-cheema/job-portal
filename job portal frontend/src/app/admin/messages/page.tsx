"use client";

import { useEffect, useState } from "react";
import { AdminShell } from "@/components/AdminShell";
import { adminDeleteMessage, adminListMessages } from "@/lib/api";
import { useAdminAuth } from "@/lib/adminAuth";
import type { ContactMessage } from "@/lib/types";
import { formatDate } from "@/lib/format";

export default function AdminMessagesPage() {
  const { token } = useAdminAuth();
  const [items, setItems] = useState<ContactMessage[]>([]);
  const [selected, setSelected] = useState<ContactMessage | null>(null);

  async function load() {
    if (!token) return;
    setItems(await adminListMessages(token));
  }

  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);

  async function onDelete(id: string) {
    if (!token || !confirm("Delete this message?")) return;
    await adminDeleteMessage(token, id);
    if (selected?.id === id) setSelected(null);
    await load();
  }

  return (
    <AdminShell>
      <div className="grid lg:grid-cols-2 gap-5">
        <div className="card-panel">
          <div className="px-5 py-4 border-b border-[var(--border)]">
            <h2 className="font-semibold text-[var(--navy-100)]">Contact messages</h2>
          </div>
          <div className="divide-y divide-[var(--border)]">
            {items.map((m) => (
              <button
                key={m.id}
                type="button"
                className="w-full text-left px-5 py-3 hover:bg-[var(--card-hover)]"
                onClick={() => setSelected(m)}
              >
                <div className="flex items-center justify-between gap-2">
                  <span className="font-medium text-[var(--navy-100)]">{m.name}</span>
                  {!m.is_read && (
                    <span className="text-[10px] uppercase tracking-wide text-[var(--accent)]">
                      new
                    </span>
                  )}
                </div>
                <div className="text-xs text-[var(--muted)] mt-0.5">
                  {m.subject || "(no subject)"} · {formatDate(m.created_at)}
                </div>
              </button>
            ))}
            {items.length === 0 && (
              <p className="p-5 text-sm text-[var(--muted)]">No messages yet.</p>
            )}
          </div>
        </div>

        <div className="card-panel p-5">
          {selected ? (
            <div className="space-y-3">
              <div className="flex justify-between gap-2">
                <h2 className="font-semibold text-[var(--navy-100)]">{selected.subject || "Message"}</h2>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => onDelete(selected.id)}
                >
                  Delete
                </button>
              </div>
              <p className="text-sm text-[var(--muted)]">
                From {selected.name} &lt;{selected.email}&gt; · {formatDate(selected.created_at)}
              </p>
              <div className="whitespace-pre-wrap text-[var(--navy-200)] text-sm leading-relaxed">
                {selected.message}
              </div>
            </div>
          ) : (
            <p className="text-sm text-[var(--muted)]">Select a message to read.</p>
          )}
        </div>
      </div>
    </AdminShell>
  );
}
