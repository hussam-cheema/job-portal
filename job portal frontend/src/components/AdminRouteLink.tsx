"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useEffect, type ComponentProps, type MouseEvent } from "react";

type Props = Omit<ComponentProps<typeof Link>, "prefetch">;

export const ADMIN_NAVIGATION_TARGET_KEY = "pakjobs-admin-navigation-target";

function linkTarget(href: Props["href"]): string | null {
  if (typeof href === "string") return href;
  if (!href.pathname) return null;
  const query = href.query ? `?${new URLSearchParams(href.query as Record<string, string>)}` : "";
  return `${href.pathname}${query}${href.hash || ""}`;
}

export function AdminRouteLink({ onClick, href, ...props }: Props) {
  const pathname = usePathname();

  useEffect(() => {
    const pendingTarget = window.sessionStorage.getItem(ADMIN_NAVIGATION_TARGET_KEY);
    if (!pendingTarget) return;
    const pendingUrl = new URL(pendingTarget, window.location.origin);
    if (
      pendingUrl.pathname === window.location.pathname &&
      pendingUrl.search === window.location.search
    ) {
      window.sessionStorage.removeItem(ADMIN_NAVIGATION_TARGET_KEY);
    }
  }, [pathname]);

  function handleClick(event: MouseEvent<HTMLAnchorElement>) {
    onClick?.(event);
    if (
      event.defaultPrevented ||
      event.button !== 0 ||
      event.metaKey ||
      event.ctrlKey ||
      event.shiftKey ||
      event.altKey ||
      props.target === "_blank"
    ) {
      return;
    }

    const target = linkTarget(href);
    if (!target) return;
    const targetUrl = new URL(target, window.location.origin);
    if (targetUrl.origin !== window.location.origin) return;
    if (
      targetUrl.pathname === window.location.pathname &&
      targetUrl.search === window.location.search
    ) {
      return;
    }

    const startingUrl = window.location.href;
    window.sessionStorage.setItem(ADMIN_NAVIGATION_TARGET_KEY, targetUrl.href);
    window.setTimeout(() => {
      const pendingTarget = window.sessionStorage.getItem(ADMIN_NAVIGATION_TARGET_KEY);
      if (pendingTarget !== targetUrl.href) return;
      if (window.location.href === startingUrl) {
        window.location.assign(targetUrl.href);
      } else {
        window.sessionStorage.removeItem(ADMIN_NAVIGATION_TARGET_KEY);
      }
    }, 4_000);
  }

  // Avoid preloading a route from an older Azure deployment, while preserving
  // fast client navigation. If a stale deployment chunk prevents the route
  // transition, complete the user's requested navigation with a fresh document
  // instead of silently doing nothing or reloading the current editor.
  return <Link {...props} href={href} onClick={handleClick} prefetch={false} />;
}
