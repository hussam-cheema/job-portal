"use client";

import { useEffect } from "react";

export function ClientErrorReporter() {
  useEffect(() => {
    const reportWindowError = (event: ErrorEvent) => {
      console.error("Unhandled browser error", event.error || event.message);
    };
    const reportRejection = (event: PromiseRejectionEvent) => {
      console.error("Unhandled promise rejection", event.reason);
    };

    window.addEventListener("error", reportWindowError);
    window.addEventListener("unhandledrejection", reportRejection);
    return () => {
      window.removeEventListener("error", reportWindowError);
      window.removeEventListener("unhandledrejection", reportRejection);
    };
  }, []);

  return null;
}
