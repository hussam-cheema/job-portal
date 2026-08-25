"use client";

import { usePathname } from "next/navigation";

const ADSENSE_SRC =
  "https://pagead2.googlesyndication.com/pagead/js/adsbygoogle.js?client=ca-pub-1209296651546868";

/** Keep advertising code off the privacy policy used by Google's consent flow. */
export function AdSenseScript() {
  const pathname = usePathname();

  if (pathname === "/privacy") return null;

  return <script async src={ADSENSE_SRC} crossOrigin="anonymous" />;
}
