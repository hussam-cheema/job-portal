"use client";

const VISITOR_KEY = "pakjobs-visitor-id";
let memoryVisitorId: string | null = null;

function createVisitorId() {
  return typeof globalThis.crypto?.randomUUID === "function"
    ? globalThis.crypto.randomUUID()
    : `${Date.now()}-${Math.random().toString(36).slice(2)}`;
}

export function getVisitorId() {
  if (memoryVisitorId) return memoryVisitorId;

  for (const storageName of ["localStorage", "sessionStorage"] as const) {
    try {
      const storage = window[storageName];
      const existing = storage.getItem(VISITOR_KEY);
      if (existing) {
        memoryVisitorId = existing;
        return existing;
      }
      const created = createVisitorId();
      storage.setItem(VISITOR_KEY, created);
      memoryVisitorId = created;
      return created;
    } catch {
      // Privacy modes can disable storage. Fall through to the next safe option.
    }
  }

  memoryVisitorId = createVisitorId();
  return memoryVisitorId;
}
