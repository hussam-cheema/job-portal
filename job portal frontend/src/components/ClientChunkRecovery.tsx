"use client";

import { useEffect, useState } from "react";
import { ADMIN_NAVIGATION_TARGET_KEY } from "@/components/AdminRouteLink";

const CHUNK_ERROR =
  /ChunkLoadError|Loading chunk [^ ]+ failed|Failed to fetch dynamically imported module|Importing a module script failed/i;

function errorText(value: unknown): string {
  if (value instanceof Error) return `${value.name}: ${value.message}`;
  return typeof value === "string" ? value : "";
}

export function ClientChunkRecovery() {
  const [updateRequired, setUpdateRequired] = useState(false);

  useEffect(() => {
    function recoverWithoutLosingWork() {
      const pendingTarget = window.sessionStorage.getItem(ADMIN_NAVIGATION_TARGET_KEY);
      if (pendingTarget) {
        const target = new URL(pendingTarget, window.location.origin);
        if (
          target.origin === window.location.origin &&
          (target.pathname !== window.location.pathname ||
            target.search !== window.location.search)
        ) {
          window.location.assign(target.href);
          return;
        }
      }
      setUpdateRequired(true);
    }

    function onRejection(event: PromiseRejectionEvent) {
      if (!CHUNK_ERROR.test(errorText(event.reason))) return;
      event.preventDefault();
      recoverWithoutLosingWork();
    }

    function onError(event: ErrorEvent) {
      const target = event.target as HTMLScriptElement | HTMLLinkElement | null;
      const assetUrl = target && "src" in target ? target.src : target?.href || "";
      const isNextAsset = /\/_next\/static\/(?:chunks|css)\//.test(assetUrl);
      if (isNextAsset || CHUNK_ERROR.test(errorText(event.error) || event.message)) {
        event.preventDefault();
        recoverWithoutLosingWork();
      }
    }

    window.addEventListener("unhandledrejection", onRejection);
    window.addEventListener("error", onError, true);
    return () => {
      window.removeEventListener("unhandledrejection", onRejection);
      window.removeEventListener("error", onError, true);
    };
  }, []);

  if (!updateRequired) return null;

  return (
    <div
      role="alert"
      className="fixed inset-x-3 top-3 z-[1000] mx-auto flex max-w-3xl flex-col justify-between gap-3 rounded-2xl border border-amber-400/60 bg-[var(--navy-900)] px-4 py-3 text-sm shadow-2xl sm:flex-row sm:items-center"
    >
      <div>
        <p className="font-semibold text-[var(--navy-100)]">A website update is available.</p>
        <p className="mt-0.5 text-xs text-[var(--muted)]">
          Your job and blog editor drafts are protected. Update only when you are ready.
        </p>
      </div>
      <div className="flex gap-2">
        <button
          type="button"
          className="btn btn-primary"
          onClick={() => window.location.reload()}
        >
          Update website
        </button>
        <button
          type="button"
          className="btn btn-ghost"
          onClick={() => setUpdateRequired(false)}
        >
          Not now
        </button>
      </div>
    </div>
  );
}
