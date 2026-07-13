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
    void trackVisit(visitorId, pathname || "/");
  }, [pathname]);

  return null;
}
