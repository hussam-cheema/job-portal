"use client";

import Image from "next/image";
import { FormEvent, useEffect, useState } from "react";
import { AdminShell } from "@/components/AdminShell";
import { YoastSEOPanel, type YoastSEOValue } from "@/components/YoastSEOPanel";
import { useAdminAuth } from "@/lib/adminAuth";
import {
  adminChangePassword,
  adminDeleteLogo,
  adminUpdateSocialSettings,
  adminUpdateBranding,
  adminUploadLogo,
  fetchBranding,
  fetchSocialSettings,
} from "@/lib/api";
import type { SocialSettings } from "@/lib/types";

export default function SettingsPage() {
  const { token } = useAdminAuth();
  const [logoUrl, setLogoUrl] = useState<string | null>(null);
  const [logoFile, setLogoFile] = useState<File | null>(null);
  const [siteTitle, setSiteTitle] = useState("Pakistan Jobs Market");
  const [siteTitleAlignment, setSiteTitleAlignment] = useState<
    "beside_logo" | "center" | "right"
  >("center");
  const [siteHeader, setSiteHeader] = useState(
    "Latest government & private job openings in Pakistan"
  );
  const [siteDescription, setSiteDescription] = useState(
    "Discover current government and private jobs across Pakistan, search opportunities by city and category, get instant job alerts, and use practical career tools."
  );
  const [footerCopyright, setFooterCopyright] = useState(
    "Copyrights © {year} - Pakistan Jobs Market. All rights reserved."
  );
  const [social, setSocial] = useState<SocialSettings>({
    facebook_url: "",
    youtube_url: "",
    x_url: "",
    linkedin_url: "",
  });
  const [homepageSeo, setHomepageSeo] = useState<YoastSEOValue>({
    focus_keyword: "jobs in Pakistan",
    meta_title: "Jobs in Pakistan 2026 | Pakistan Jobs Market",
    meta_description: "Find latest government and private jobs in Pakistan by city and category. Explore curated listings, deadlines, job alerts, resume tools and career guides.",
    meta_keywords: "jobs in Pakistan, latest jobs in Pakistan, government jobs Pakistan, private jobs Pakistan, newspaper jobs, FPSC jobs, PPSC jobs, jobs by city, Pakistan Jobs Market",
  });
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
      setSiteTitleAlignment(branding.site_title_alignment);
      setSiteHeader(branding.site_header);
      setSiteDescription(branding.site_description);
      setFooterCopyright(branding.footer_copyright);
      setHomepageSeo({
        focus_keyword: branding.homepage_focus_keyword,
        meta_title: branding.homepage_meta_title,
        meta_description: branding.homepage_meta_description,
        meta_keywords: branding.homepage_meta_keywords,
      });
    });
    void fetchSocialSettings().then(setSocial);
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
        site_title_alignment: siteTitleAlignment,
        site_header: siteHeader.trim(),
        site_description: siteDescription.trim(),
        footer_copyright: footerCopyright.trim(),
        homepage_focus_keyword: homepageSeo.focus_keyword.trim(),
        homepage_meta_title: homepageSeo.meta_title.trim(),
        homepage_meta_description: homepageSeo.meta_description.trim(),
        homepage_meta_keywords: homepageSeo.meta_keywords.trim(),
      });
      setSiteTitle(branding.site_title);
      setSiteTitleAlignment(branding.site_title_alignment);
      setSiteHeader(branding.site_header);
      setSiteDescription(branding.site_description);
      setFooterCopyright(branding.footer_copyright);
      setHomepageSeo({
        focus_keyword: branding.homepage_focus_keyword,
        meta_title: branding.homepage_meta_title,
        meta_description: branding.homepage_meta_description,
        meta_keywords: branding.homepage_meta_keywords,
      });
      setMessage("Website text, homepage SEO, and footer updated.");
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

  async function saveSocial(event: FormEvent) {
    event.preventDefault();
    if (!token) return;
    setBusy(true);
    setError(null);
    setMessage(null);
    try {
      setSocial(await adminUpdateSocialSettings(token, social));
      setMessage("Social media links updated.");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Social media settings update failed");
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
            <fieldset>
              <legend className="field-label">Website title position</legend>
              <div className="grid grid-cols-3 gap-2" role="radiogroup" aria-label="Website title position">
                {([
                  ["beside_logo", "Beside logo"],
                  ["center", "Center"],
                  ["right", "Right"],
                ] as const).map(([value, label]) => (
                  <label
                    key={value}
                    className={`cursor-pointer rounded-lg border px-3 py-2 text-center text-sm transition-colors ${
                      siteTitleAlignment === value
                        ? "border-[var(--accent)] bg-[var(--accent-soft)] text-[var(--navy-100)]"
                        : "border-[var(--border)] text-[var(--muted)] hover:border-[var(--navy-500)]"
                    }`}
                  >
                    <input
                      type="radio"
                      name="site-title-alignment"
                      value={value}
                      checked={siteTitleAlignment === value}
                      onChange={() => setSiteTitleAlignment(value)}
                      className="sr-only"
                    />
                    {label}
                  </label>
                ))}
              </div>
            </fieldset>
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
            <div className="lg:col-span-2">
              <div className="mb-3 border-t border-[var(--border)] pt-5">
                <h3 className="font-semibold text-[var(--navy-100)]">Homepage SEO</h3>
                <p className="mt-1 text-xs text-[var(--muted)]">
                  Controls the Google result and social preview for the website homepage.
                </p>
              </div>
              <YoastSEOPanel
                title={siteTitle}
                content={`${siteHeader}\n\n${siteDescription}`}
                slug=""
                value={homepageSeo}
                onChange={setHomepageSeo}
              />
            </div>
          </div>
          <button type="submit" className="btn btn-primary mt-5" disabled={busy}>
            Save website settings
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

        <form onSubmit={saveSocial} className="card-panel p-5">
          <h3 className="font-semibold text-[var(--navy-100)]">Footer social links</h3>
          <p className="mt-1 text-xs text-[var(--muted)]">
            Configured profiles appear as buttons in the public website footer.
          </p>
          <div className="mt-4 space-y-4">
            {([
              ["facebook_url", "Facebook URL", "https://facebook.com/..."],
              ["youtube_url", "YouTube URL", "https://youtube.com/..."],
              ["x_url", "X (Twitter) URL", "https://x.com/..."],
              ["linkedin_url", "LinkedIn URL", "https://linkedin.com/company/..."],
            ] as const).map(([key, label, placeholder]) => (
              <div key={key}>
                <label className="field-label" htmlFor={key}>{label}</label>
                <input
                  id={key}
                  type="url"
                  className="input"
                  value={social[key]}
                  onChange={(event) => setSocial({ ...social, [key]: event.target.value })}
                  placeholder={placeholder}
                />
              </div>
            ))}
          </div>
          <button type="submit" className="btn btn-primary mt-5" disabled={busy}>
            Save social links
          </button>
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
