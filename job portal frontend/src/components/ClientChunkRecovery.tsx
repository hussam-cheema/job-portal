"use client";

import { useEffect } from "react";
import { ADMIN_NAVIGATION_TARGET_KEY } from "@/components/AdminRouteLink";

const CHUNK_ERROR =
  /ChunkLoadError|Loading chunk [^ ]+ failed|Failed to fetch dynamically imported module|Importing a module script failed/i;

function errorText(value: unknown): string {
  if (value instanceof Error) return `${value.name}: ${value.message}`;
  return typeof value === "string" ? value : "";
}

export function ClientChunkRecovery() {
  useEffect(() => {
    function completePendingNavigation() {
      const pendingTarget = window.sessionStorage.getItem(ADMIN_NAVIGATION_TARGET_KEY);
      if (!pendingTarget) return;
      const target = new URL(pendingTarget, window.location.origin);
      if (
        target.origin === window.location.origin &&
        (target.pathname !== window.location.pathname ||
          target.search !== window.location.search)
      ) {
        window.location.assign(target.href);
      }
    }

    function onRejection(event: PromiseRejectionEvent) {
      if (!CHUNK_ERROR.test(errorText(event.reason))) return;
      event.preventDefault();
      completePendingNavigation();
    }

    function onError(event: ErrorEvent) {
      const target = event.target as HTMLScriptElement | HTMLLinkElement | null;
      const assetUrl = target && "src" in target ? target.src : target?.href || "";
      const isNextAsset = /\/_next\/static\/(?:chunks|css)\//.test(assetUrl);
      if (isNextAsset || CHUNK_ERROR.test(errorText(event.error) || event.message)) {
        event.preventDefault();
        completePendingNavigation();
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
