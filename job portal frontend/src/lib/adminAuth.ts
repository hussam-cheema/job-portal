"use client";

import { useEffect, useState } from "react";
import {
  ADMIN_AUTH_EVENT,
  ADMIN_TOKEN_KEY,
  ADMIN_USER_KEY,
  readAdminToken,
  removeAdminSession,
  writeAdminSession,
} from "./adminSession";

export const AUTH_EVENT = ADMIN_AUTH_EVENT;

export function getAdminToken(): string | null {
  if (typeof window === "undefined") return null;
  return readAdminToken();
}

export function setAdminSession(token: string, username: string) {
  writeAdminSession(token, username);
}

export function clearAdminSession() {
  removeAdminSession();
}

export function useAdminAuth() {
  const [token, setToken] = useState<string | null>(null);
  const [username, setUsername] = useState<string | null>(null);
  const [ready, setReady] = useState(false);

  useEffect(() => {
    setToken(localStorage.getItem(ADMIN_TOKEN_KEY));
    setUsername(localStorage.getItem(ADMIN_USER_KEY));
    setReady(true);
    const sync = () => {
      setToken(localStorage.getItem(ADMIN_TOKEN_KEY));
      setUsername(localStorage.getItem(ADMIN_USER_KEY));
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
