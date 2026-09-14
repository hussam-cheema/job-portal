"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { trackVisit, type AnalyticsTrackingResult } from "@/lib/api";
import { getVisitorId } from "@/lib/visitorId";

const FAILURE_REPORT_INTERVAL_MS = 5 * 60_000;
let lastFailureReportAt = 0;

function reportTrackingFailure(result: Exclude<AnalyticsTrackingResult, { ok: true }>) {
  const now = Date.now();
  if (now - lastFailureReportAt < FAILURE_REPORT_INTERVAL_MS) return;
  lastFailureReportAt = now;

  const diagnostic = { reason: result.reason, status: result.status || 0 };
  console.warn("Analytics visit ingestion failed", diagnostic);
  const analyticsWindow = window as typeof window & {
    gtag?: (...args: unknown[]) => void;
  };
  analyticsWindow.gtag?.("event", "analytics_ingestion_failure", {
    failure_reason: result.reason,
    http_status: result.status || 0,
    non_interaction: true,
  });
}

async function sendVisit(visitorId: string, path: string) {
  const result = await trackVisit(visitorId, path);
  if (!result.ok) {
    try {
      reportTrackingFailure(result);
    } catch {
      // Diagnostics must remain invisible to navigation and page rendering.
    }
  }
}

export function VisitTracker() {
  const pathname = usePathname();

  useEffect(() => {
    const visitorId = getVisitorId();
    const path = pathname || "/";
    void sendVisit(visitorId, path);
    const heartbeat = window.setInterval(() => {
      void sendVisit(visitorId, path);
    }, 60_000);
    return () => window.clearInterval(heartbeat);
  }, [pathname]);

  return null;
}
