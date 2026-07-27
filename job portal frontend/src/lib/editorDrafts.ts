export type EditorDraftKind = "job" | "blog";

export type EditorDraftRecord<T = unknown> = {
  version: 1;
  kind: EditorDraftKind;
  recordId: string;
  title: string;
  updatedAt: string;
  data: T;
};

export const EDITOR_DRAFT_EVENT = "pakjobs-editor-drafts-change";
const EDITOR_DRAFT_PREFIX = "pakjobs-editor-draft:v1:";

function storageKey(kind: EditorDraftKind, recordId: string) {
  return `${EDITOR_DRAFT_PREFIX}${kind}:${recordId || "new"}`;
}

function isDraftRecord(value: unknown): value is EditorDraftRecord {
  if (!value || typeof value !== "object") return false;
  const record = value as Partial<EditorDraftRecord>;
  return (
    record.version === 1 &&
    (record.kind === "job" || record.kind === "blog") &&
    typeof record.recordId === "string" &&
    typeof record.title === "string" &&
    typeof record.updatedAt === "string" &&
    Boolean(record.data && typeof record.data === "object")
  );
}

function announceDraftChange() {
  window.dispatchEvent(new Event(EDITOR_DRAFT_EVENT));
}

export function readEditorDraft<T>(
  kind: EditorDraftKind,
  recordId: string
): EditorDraftRecord<T> | null {
  if (typeof window === "undefined") return null;
  try {
    const raw = window.localStorage.getItem(storageKey(kind, recordId));
    if (!raw) return null;
    const parsed: unknown = JSON.parse(raw);
    if (!isDraftRecord(parsed) || parsed.kind !== kind || parsed.recordId !== recordId) {
      window.localStorage.removeItem(storageKey(kind, recordId));
      return null;
    }
    return parsed as EditorDraftRecord<T>;
  } catch {
    return null;
  }
}

export function saveEditorDraft<T>({
  kind,
  recordId,
  title,
  data,
}: {
  kind: EditorDraftKind;
  recordId: string;
  title: string;
  data: T;
}): EditorDraftRecord<T> | null {
  if (typeof window === "undefined") return null;
  const draft: EditorDraftRecord<T> = {
    version: 1,
    kind,
    recordId,
    title: title.trim() || `Untitled ${kind} post`,
    updatedAt: new Date().toISOString(),
    data,
  };
  try {
    window.localStorage.setItem(storageKey(kind, recordId), JSON.stringify(draft));
    announceDraftChange();
    return draft;
  } catch {
    return null;
  }
}

export function deleteEditorDraft(kind: EditorDraftKind, recordId: string) {
  if (typeof window === "undefined") return;
  try {
    const key = storageKey(kind, recordId);
    if (window.localStorage.getItem(key) === null) return;
    window.localStorage.removeItem(key);
    announceDraftChange();
  } catch {
    // Storage may be disabled by browser privacy settings.
  }
}

export function listEditorDrafts(kind: EditorDraftKind): EditorDraftRecord[] {
  if (typeof window === "undefined") return [];
  const drafts: EditorDraftRecord[] = [];
  try {
    for (let index = 0; index < window.localStorage.length; index += 1) {
      const key = window.localStorage.key(index);
      if (!key?.startsWith(`${EDITOR_DRAFT_PREFIX}${kind}:`)) continue;
      try {
        const parsed: unknown = JSON.parse(window.localStorage.getItem(key) || "");
        if (isDraftRecord(parsed) && parsed.kind === kind) drafts.push(parsed);
      } catch {
        // Ignore a corrupt or manually modified draft and continue with the rest.
      }
    }
  } catch {
    // Storage may be disabled by browser privacy settings.
  }
  return drafts.sort((a, b) => b.updatedAt.localeCompare(a.updatedAt));
}

export function formatDraftTimestamp(value: string) {
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "recently";
  return new Intl.DateTimeFormat("en-PK", {
    dateStyle: "medium",
    timeStyle: "short",
  }).format(date);
}

export function cloneDraftData<T>(value: T): T {
  return JSON.parse(JSON.stringify(value)) as T;
}
