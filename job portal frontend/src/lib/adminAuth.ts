"use client";

import { useEffect, useState } from "react";

const TOKEN_KEY = "pakjobs-admin-token";
const USER_KEY = "pakjobs-admin-user";
export const AUTH_EVENT = "pakjobs-auth-change";

export function getAdminToken(): string | null {
  if (typeof window === "undefined") return null;
  return localStorage.getItem(TOKEN_KEY);
}

export function setAdminSession(token: string, username: string) {
  localStorage.setItem(TOKEN_KEY, token);
  localStorage.setItem(USER_KEY, username);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(AUTH_EVENT));
  }
}

export function clearAdminSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(USER_KEY);
  if (typeof window !== "undefined") {
    window.dispatchEvent(new Event(AUTH_EVENT));
  }
}

export function useAdminAuth() {
  const [token, setToken] = useState<string | null>(null);
  const [username, setUsername] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setToken(localStorage.getItem(TOKEN_KEY));
    setUsername(localStorage.getItem(USER_KEY));
    setReady(true);
    const sync = () => {
      setToken(localStorage.getItem(TOKEN_KEY));
      setUsername(localStorage.getItem(USER_KEY));
    };
    window.addEventListener(AUTH_EVENT, sync);
    window.addEventListener("storage", sync);
    return () => {
      window.removeEventListener(AUTH_EVENT, sync);
      window.removeEventListener("storage", sync);
    };
  }, []);

  return {
    token,
    username,
    ready,
    login: (t: string, u: string) => {
      setAdminSession(t, u);
      setToken(t);
      setUsername(u);
    },
    logout: () => {
      clearAdminSession();
      setToken(null);
      setUsername(null);
    },
  };
}
