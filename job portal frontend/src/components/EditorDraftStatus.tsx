"use client";

import { formatDraftTimestamp } from "@/lib/editorDrafts";

export function EditorDraftStatus({
  updatedAt,
  recovered,
  storageError,
  onDiscard,
}: {
  updatedAt: string | null;
  recovered: boolean;
  storageError: string | null;
  onDiscard: () => void;
}) {
  if (!updatedAt && !storageError) return null;

  return (
    <div
      className="flex flex-col justify-between gap-2 rounded-xl border border-[var(--border)] bg-[var(--navy-850)] px-4 py-3 text-sm sm:flex-row sm:items-center"
      data-testid="editor-draft-status"
      role="status"
    >
      <div>
        <p className="font-medium text-[var(--navy-100)]">
          {storageError
            ? "Draft could not be saved in this browser."
            : recovered
              ? "Recovered your auto-saved draft."
              : "Draft auto-saved locally."}
        </p>
        <p className="mt-0.5 text-xs text-[var(--muted)]">
          {storageError ||
            `Saved ${formatDraftTimestamp(updatedAt || "")}. It will survive a refresh or closed tab.`}
        </p>
      </div>
      {!storageError && (
        <button type="button" className="btn btn-ghost shrink-0" onClick={onDiscard}>
          Delete draft
        </button>
      )}
    </div>
  );
}
