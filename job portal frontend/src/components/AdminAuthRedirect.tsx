"use client";

import { usePathname, useRouter } from "next/navigation";
import { useEffect } from "react";
import { ADMIN_AUTH_EVENT, readAdminToken } from "@/lib/adminSession";

/**
 * Keeps expired-session redirects inside the Next.js router. A client-side
 * transition avoids reloading the document while still protecting every admin
 * route, including pages whose data request fails before AdminShell updates.
 */
export function AdminAuthRedirect() {
  const pathname = usePathname();
  const router = useRouter();

  useEffect(() => {
    const redirectExpiredAdmin = () => {
      if (pathname.startsWith("/admin") && !readAdminToken()) {
        router.replace("/login");
      }
    };

    window.addEventListener(ADMIN_AUTH_EVENT, redirectExpiredAdmin);
    return () => window.removeEventListener(ADMIN_AUTH_EVENT, redirectExpiredAdmin);
  }, [pathname, router]);

  return null;
}
