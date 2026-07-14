"use client";

import { useEffect } from "react";
import { usePathname } from "next/navigation";
import { trackVisit } from "@/lib/api";

const VISITOR_KEY = "pakjobs-visitor-id";

export function VisitTracker() {
  const pathname = usePathname();

  useEffect(() => {
    let visitorId = localStorage.getItem(VISITOR_KEY);
    if (!visitorId) {
      visitorId = crypto.randomUUID();
      localStorage.setItem(VISITOR_KEY, visitorId);
    }
    const path = pathname || "/";
    void trackVisit(visitorId, path);
    const heartbeat = window.setInterval(() => {
      void trackVisit(visitorId, path);
    }, 60_000);
    return () => window.clearInterval(heartbeat);
  }, [pathname]);

  return null;
}
