"use client";

import { useEffect } from "react";

const CHUNK_ERROR =
  /ChunkLoadError|Loading chunk [^ ]+ failed|Failed to fetch dynamically imported module|Importing a module script failed/i;

function errorText(value: unknown): string {
  if (value instanceof Error) return `${value.name}: ${value.message}`;
  return typeof value === "string" ? value : "";
}

export function ClientChunkRecovery() {
  useEffect(() => {
    const recoveryKey = `pakjobs-chunk-recovery:${window.location.pathname}`;

    function recoverOnce() {
      const previousAttempt = Number(sessionStorage.getItem(recoveryKey) || "0");
      if (Date.now() - previousAttempt < 60_000) return;
      sessionStorage.setItem(recoveryKey, String(Date.now()));
      window.location.reload();
    }

    function onRejection(event: PromiseRejectionEvent) {
      if (CHUNK_ERROR.test(errorText(event.reason))) recoverOnce();
    }

    function onError(event: ErrorEvent) {
      const target = event.target as HTMLScriptElement | HTMLLinkElement | null;
      const assetUrl = target && "src" in target ? target.src : target?.href || "";
      const isNextAsset = /\/_next\/static\/(?:chunks|css)\//.test(assetUrl);
      if (isNextAsset || CHUNK_ERROR.test(errorText(event.error) || event.message)) {
        recoverOnce();
      }
    }

    window.addEventListener("unhandledrejection", onRejection);
    window.addEventListener("error", onError, true);
    return () => {
      window.removeEventListener("unhandledrejection", onRejection);
      window.removeEventListener("error", onError, true);
    };
  }, []);

  return null;
}
