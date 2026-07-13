"use client";

import { useEffect, useState } from "react";
import { API_BASE } from "@/lib/api";

type Social = { facebook_url?: string; youtube_url?: string; x_url?: string };

export function SocialFooterIcons() {
  const [social, setSocial] = useState<Social>({});

  useEffect(() => {
    fetch(`${API_BASE}/api/settings/social`, { next: { revalidate: 60 } } as RequestInit)
      .then((r) => (r.ok ? r.json() : {}))
      .then(setSocial)
      .catch(() => undefined);
  }, []);

  const items = [
    { href: social.facebook_url, label: "Facebook", icon: "f" },
    { href: social.youtube_url, label: "YouTube", icon: "▶" },
    { href: social.x_url, label: "X", icon: "𝕏" },
  ].filter((i) => i.href);

  if (!items.length) return null;

  return (
    <div className="flex gap-2 mt-4">
      {items.map((i) => (
        <a
          key={i.label}
          href={i.href}
          target="_blank"
          rel="noreferrer"
          className="social-icon"
          title={i.label}
          aria-label={i.label}
        >
          {i.icon}
        </a>
      ))}
    </div>
  );
}
