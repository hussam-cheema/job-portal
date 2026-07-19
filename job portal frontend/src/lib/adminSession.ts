export const ADMIN_TOKEN_KEY = "pakjobs-admin-token";
export const ADMIN_USER_KEY = "pakjobs-admin-user";
export const ADMIN_AUTH_EVENT = "pakjobs-auth-change";

export function readAdminToken(): string | null {
  if (typeof window === "undefined") return null;
  return window.localStorage.getItem(ADMIN_TOKEN_KEY);
}

export function writeAdminSession(token: string, username: string) {
  if (typeof window === "undefined") return;
  window.localStorage.setItem(ADMIN_TOKEN_KEY, token);
  window.localStorage.setItem(ADMIN_USER_KEY, username);
  window.dispatchEvent(new Event(ADMIN_AUTH_EVENT));
}

export function removeAdminSession() {
  if (typeof window === "undefined") return;
  window.localStorage.removeItem(ADMIN_TOKEN_KEY);
  window.localStorage.removeItem(ADMIN_USER_KEY);
  window.dispatchEvent(new Event(ADMIN_AUTH_EVENT));
}
