"use client";

import { useEffect } from "react";

export default function GlobalError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("Unhandled root application error", error);
  }, [error]);

  return (
    <html lang="en">
      <body>
        <main style={{ maxWidth: 720, margin: "64px auto", padding: 24, textAlign: "center" }}>
          <h1>Pakistan Jobs Market could not be loaded</h1>
          <p>An unexpected error occurred. Please try loading the application again.</p>
          <button type="button" onClick={reset} style={{ marginTop: 16, padding: "10px 18px" }}>
            Try again
          </button>
        </main>
      </body>
    </html>
  );
}
