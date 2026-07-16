"use client";

import Image from "next/image";
import { FormEvent, useEffect, useState } from "react";
import { AdminShell } from "@/components/AdminShell";
import { useAdminAuth } from "@/lib/adminAuth";
import {
  adminChangePassword,
  adminDeleteLogo,
  adminUpdateBranding,
  adminUploadLogo,
  fetchBranding,
} from "@/lib/api";

export default function SettingsPage() {
  const { token } = useAdminAuth();
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [siteTitle, setSiteTitle] = useState("PakJobs Jobs in Pakistan");
  const [siteHeader, setSiteHeader] = useState(
    "Latest government & private job openings in Pakistan"
  );
  const [siteDescription, setSiteDescription] = useState(
    "Hover a job for a summary, then open the full page for complete details and available interview Q&A."
  );
  const [footerCopyright, setFooterCopyright] = useState(
    "Copyrights © {year} - PakistanJobs All rights reserved"
  );
  const [currentPassword, setCurrentPassword] = useState("");
  const [newPassword, setNewPassword] = useState("");
  const [confirmPassword, setConfirmPassword] = useState("");
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState<string | null>(null);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    void fetchBranding().then((branding) => {
      setLogoUrl(branding.logo_url);
      setSiteTitle(branding.site_title);
      setSiteHeader(branding.site_header);
      setSiteDescription(branding.site_description);
      setFooterCopyright(branding.footer_copyright);
    });
  }, []);

  async function saveBranding(event: FormEvent) {
    event.preventDefault();
    if (!token) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const branding = await adminUpdateBranding(token, {
        site_title: siteTitle.trim(),
        site_header: siteHeader.trim(),
        site_description: siteDescription.trim(),
        footer_copyright: footerCopyright.trim(),
      });
      setSiteTitle(branding.site_title);
      setSiteHeader(branding.site_header);
      setSiteDescription(branding.site_description);
      setFooterCopyright(branding.footer_copyright);
      setMessage("Website text and footer updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Website settings update failed");
    } finally {
      setBusy(false);
    }
  }

  async function uploadLogo(event: FormEvent) {
    event.preventDefault();
    if (!token || !logoFile) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      const branding = await adminUploadLogo(token, logoFile);
      setLogoUrl(branding.logo_url);
      setLogoFile(null);
      setMessage("Website logo updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Logo update failed");
    } finally {
      setBusy(false);
    }
  }

  async function removeLogo() {
    if (!token) return;
    setBusy(true);
    setError(null);
    try {
      await adminDeleteLogo(token);
      setLogoUrl(null);
      setMessage("Default logo restored.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Logo removal failed");
    } finally {
      setBusy(false);
    }
  }

  async function changePassword(event: FormEvent) {
    event.preventDefault();
    if (!token) return;
    if (newPassword !== confirmPassword) {
      setError("New passwords do not match.");
      return;
    }
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      await adminChangePassword(token, currentPassword, newPassword);
      setCurrentPassword("");
      setNewPassword("");
      setConfirmPassword("");
      setMessage("Admin password changed.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Password change failed");
    } finally {
      setBusy(false);
    }
  }

  return (
    <AdminShell>
      <div className="mb-6">
        <h2 className="text-xl font-semibold text-[var(--navy-100)]">Settings</h2>
        <p className="mt-1 text-sm text-[var(--muted)]">Manage branding and admin access.</p>
      </div>
      {error && <p className="field-error mb-4">{error}</p>}
      {message && <p className="mb-4 text-sm text-[var(--success)]">{message}</p>}

      <div className="grid gap-5 lg:grid-cols-2">
        <form onSubmit={saveBranding} className="card-panel p-5 lg:col-span-2">
          <h3 className="font-semibold text-[var(--navy-100)]">Website text</h3>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Use <code>{"{year}"}</code> in the footer text to insert the current year automatically.
          </p>
          <div className="mt-4 grid gap-4 lg:grid-cols-2">
            <div>
              <label className="field-label" htmlFor="site-title">Website title</label>
              <input
                id="site-title"
                className="input"
                maxLength={120}
                required
                value={siteTitle}
                onChange={(event) => setSiteTitle(event.target.value)}
              />
            </div>
            <div>
              <label className="field-label" htmlFor="site-header">Website header</label>
              <input
                id="site-header"
                className="input"
                maxLength={240}
                required
                value={siteHeader}
                onChange={(event) => setSiteHeader(event.target.value)}
              />
            </div>
            <div className="lg:col-span-2">
              <label className="field-label" htmlFor="site-description">Website description</label>
              <textarea
                id="site-description"
                className="input min-h-24"
                maxLength={500}
                required
                value={siteDescription}
                onChange={(event) => setSiteDescription(event.target.value)}
              />
            </div>
            <div className="lg:col-span-2">
              <label className="field-label" htmlFor="footer-copyright">Footer copyright</label>
              <input
                id="footer-copyright"
                className="input"
                maxLength={240}
                required
                value={footerCopyright}
                onChange={(event) => setFooterCopyright(event.target.value)}
              />
            </div>
          </div>
          <button type="submit" className="btn btn-primary mt-5" disabled={busy}>
            Save website text
          </button>
        </form>

        <form onSubmit={uploadLogo} className="card-panel p-5">
          <h3 className="font-semibold text-[var(--navy-100)]">Website logo</h3>
          <div className="mt-4 flex h-24 items-center justify-center rounded border border-[var(--border)] bg-[var(--navy-850)]">
            {logoUrl ? (
              <Image
                src={logoUrl}
                alt="Current website logo"
                width={160}
                height={72}
                unoptimized
                className="max-h-16 w-auto object-contain"
              />
            ) : (
              <span className="logo-mark flex h-12 w-12 items-center justify-center rounded-lg bg-[#315fa8] font-bold">PJ</span>
            )}
          </div>
          <label className="field-label mt-5" htmlFor="logo-file">New logo</label>
          <input
            id="logo-file"
            type="file"
            accept="image/png,image/jpeg,image/webp,image/gif"
            className="input"
            onChange={(event) => setLogoFile(event.target.files?.[0] || null)}
          />
          <p className="mt-2 text-xs text-[var(--muted)]">PNG, JPG, WebP, or GIF. Maximum 2MB.</p>
          <div className="mt-5 flex flex-wrap gap-2">
            <button type="submit" className="btn btn-primary" disabled={busy || !logoFile}>Upload logo</button>
            {logoUrl && (
              <button type="button" className="btn btn-ghost" onClick={removeLogo} disabled={busy}>Restore default</button>
            )}
          </div>
        </form>

        <form onSubmit={changePassword} className="card-panel p-5">
          <h3 className="font-semibold text-[var(--navy-100)]">Admin password</h3>
          <div className="mt-4 space-y-4">
            <div>
              <label className="field-label" htmlFor="current-password">Current password</label>
              <input id="current-password" className="input" type="password" autoComplete="current-password" required value={currentPassword} onChange={(event) => setCurrentPassword(event.target.value)} />
            </div>
            <div>
              <label className="field-label" htmlFor="new-password">New password</label>
              <input id="new-password" className="input" type="password" autoComplete="new-password" minLength={12} maxLength={72} required value={newPassword} onChange={(event) => setNewPassword(event.target.value)} />
            </div>
            <div>
              <label className="field-label" htmlFor="confirm-password">Confirm new password</label>
              <input id="confirm-password" className="input" type="password" autoComplete="new-password" minLength={12} maxLength={72} required value={confirmPassword} onChange={(event) => setConfirmPassword(event.target.value)} />
            </div>
          </div>
          <button type="submit" className="btn btn-primary mt-5" disabled={busy}>Change password</button>
        </form>
      </div>
    </AdminShell>
  );
}
