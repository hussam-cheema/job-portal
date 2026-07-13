"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { AUTH_EVENT, getAdminToken } from "@/lib/adminAuth";

/** Shows Dashboard link only when an admin session token exists. */
export function AdminDashboardLink() {
  const [loggedIn, setLoggedIn] = useState(false);

  useEffect(() => {
    const check = () => setLoggedIn(Boolean(getAdminToken()));
    check();
    window.addEventListener("storage", check);
    window.addEventListener("focus", check);
    window.addEventListener(AUTH_EVENT, check);
    return () => {
      window.removeEventListener("storage", check);
      window.removeEventListener("focus", check);
      window.removeEventListener(AUTH_EVENT, check);
    };
  }, []);

  if (!loggedIn) return null;

  return (
    <Link href="/admin" className="theme-toggle" title="Admin dashboard">
      Dashboard
    </Link>
  );
}
