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

export function EditorDraftsPanel({
  kind,
  onCountChange,
}: {
  kind: EditorDraftKind;
  onCountChange?: (count: number) => void;
}) {
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

  useEffect(() => {
    onCountChange?.(drafts.length);
  }, [drafts.length, onCountChange]);

  if (!drafts.length) return null;

  const noun = kind === "job" ? "job" : "blog";
  const basePath = kind === "job" ? "/admin/jobs" : "/admin/blog";

  return (
    <div
      className="divide-y divide-[var(--border)]"
      aria-label={`Saved ${noun} drafts`}
      role="region"
    >
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
              <div className="flex flex-wrap items-center gap-2">
                <p className="truncate font-medium text-[var(--navy-100)]">{draft.title}</p>
                <span className="badge badge-muted">Local draft</span>
              </div>
              <p className="mt-1 text-xs text-[var(--muted)]">
                Auto-saved {formatDraftTimestamp(draft.updatedAt)}
              </p>
            </div>
            <div className="flex gap-2">
              <AdminRouteLink href={href} className="btn btn-ghost">
                Edit
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
                Delete
              </button>
            </div>
          </div>
        );
      })}
    </div>
  );
}
