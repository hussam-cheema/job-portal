"use client";

export default function ReportError({ reset }: { reset: () => void }) {
  return <section className="site-wrap py-16"><h1 className="text-2xl font-bold">The report is temporarily unavailable</h1><p className="my-4">We could not retrieve the published report. Please try again; no placeholder statistics are being shown.</p><button className="btn-primary" onClick={reset}>Try again</button></section>;
}
