"use client";

import { useCallback, useEffect, useState } from "react";
import { AdminRouteLink } from "@/components/AdminRouteLink";
import {
  deleteEditorDraft,
  EDITOR_DRAFT_EVENT,
  formatDraftTimestamp,
  listEditorDrafts,
  type EditorDraftKind,
  type EditorDraftRecord,
} from "@/lib/editorDrafts";

export function EditorDraftsPanel({ kind }: { kind: EditorDraftKind }) {
  const [drafts, setDrafts] = useState<EditorDraftRecord[]>([]);

  const refresh = useCallback(() => {
    setDrafts(listEditorDrafts(kind));
  }, [kind]);

  useEffect(() => {
    refresh();
    window.addEventListener(EDITOR_DRAFT_EVENT, refresh);
    window.addEventListener("storage", refresh);
    return () => {
      window.removeEventListener(EDITOR_DRAFT_EVENT, refresh);
      window.removeEventListener("storage", refresh);
    };
  }, [refresh]);

  if (!drafts.length) return null;

  const noun = kind === "job" ? "job" : "blog";
  const basePath = kind === "job" ? "/admin/jobs" : "/admin/blog";

  return (
    <section className="card-panel mb-5 overflow-hidden" aria-label={`Saved ${noun} drafts`}>
      <div className="border-b border-[var(--border)] px-5 py-4">
        <h2 className="font-semibold text-[var(--navy-100)]">
          Saved {noun} {drafts.length === 1 ? "draft" : "drafts"}
        </h2>
        <p className="mt-1 text-xs text-[var(--muted)]">
          Automatically saved in this browser. Continue editing or delete any draft.
        </p>
      </div>
      <div className="divide-y divide-[var(--border)]">
        {drafts.map((draft) => {
          const href =
            draft.recordId === "new"
              ? `${basePath}/new`
              : `${basePath}/${encodeURIComponent(draft.recordId)}`;
          return (
            <div
              key={`${draft.kind}:${draft.recordId}`}
              className="flex flex-col justify-between gap-3 px-5 py-4 sm:flex-row sm:items-center"
            >
              <div className="min-w-0">
                <p className="truncate font-medium text-[var(--navy-100)]">{draft.title}</p>
                <p className="mt-1 text-xs text-[var(--muted)]">
                  Auto-saved {formatDraftTimestamp(draft.updatedAt)}
                </p>
              </div>
              <div className="flex gap-2">
                <AdminRouteLink href={href} className="btn btn-ghost">
                  Edit draft
                </AdminRouteLink>
                <button
                  type="button"
                  className="btn btn-ghost"
                  onClick={() => {
                    if (!window.confirm(`Delete the local draft “${draft.title}”?`)) return;
                    deleteEditorDraft(kind, draft.recordId);
                    refresh();
                  }}
                >
                  Delete draft
                </button>
              </div>
            </div>
          );
        })}
      </div>
    </section>
  );
}
