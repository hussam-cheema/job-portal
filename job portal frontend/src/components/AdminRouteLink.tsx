"use client";

import Link from "next/link";
import type { ComponentProps, MouseEvent } from "react";

type Props = Omit<ComponentProps<typeof Link>, "prefetch">;

/**
 * Admin routes deliberately use a full document navigation. Azure Static Web
 * Apps replaces immutable Next.js chunks on deployment; a dashboard tab kept
 * open across a revision can otherwise request a chunk from the previous build
 * and crash with a client-side ChunkLoadError.
 */
export function AdminRouteLink({ href, onClick, ...props }: Props) {
  function navigate(event: MouseEvent<HTMLAnchorElement>) {
    onClick?.(event);
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey
    ) {
      return;
    }
    event.preventDefault();
    window.location.assign(typeof href === "string" ? href : href.pathname || "/admin");
  }

  return <Link {...props} href={href} prefetch={false} onClick={navigate} />;
}
