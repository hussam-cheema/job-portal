"use client";

import Link from "next/link";
import type { ComponentProps } from "react";

type Props = Omit<ComponentProps<typeof Link>, "prefetch">;

export function AdminRouteLink(props: Props) {
  // Avoid preloading a route from an older Azure deployment, while preserving
  // Next.js client navigation so an admin click never depends on an SWA SSR
  // backend round trip.
  return <Link {...props} prefetch={false} />;
}
