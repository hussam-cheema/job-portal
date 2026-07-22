import type { Metadata } from "next";
import { ManagedPage } from "@/components/ManagedPage";

export const metadata: Metadata = {
  title: "Privacy Policy | Pakistan Jobs Market",
  description: "Read how Pakistan Jobs Market collects, uses, protects and retains contact, subscription, analytics and technical information.",
  keywords: [
    "Pakistan Jobs Market privacy policy",
    "data protection",
    "cookies",
    "analytics",
    "newsletter privacy",
    "job alerts privacy",
  ],
  alternates: { canonical: "/privacy" },
  robots: { index: true, follow: true },
};

const FALLBACK = `
  <p><strong>Pakistan Jobs Market</strong> respects visitor and subscriber privacy. You can browse public listings without creating an account.</p>
  <h2>Information we may collect</h2><p>We may process an email address submitted for job alerts, contact-form details, essential preferences, and limited technical information such as requested pages, browser data, IP address, timestamps and error records.</p>
  <h2>How information is used</h2><p>Information supports requested alerts, responses to messages, abuse prevention, security, diagnostics, aggregate analytics and service improvement. We do not sell personal data.</p>
  <h2>Email alerts and choices</h2><p>Subscribers receive messages about newly published jobs and can use the unsubscribe link in an alert to remove their active subscription.</p>
  <h2>Cookies, analytics and advertising</h2><p>Essential storage and third-party services may support preferences, measurement, performance and advertising. If Google AdSense or similar advertising is enabled, providers may use cookies in accordance with their own policies and available consent controls.</p>
  <h2>External services and retention</h2><p>Hosting, database, object-storage, email and analytics providers process limited data required to operate the site. External job links have their own privacy practices. We retain information only as reasonably needed and use appropriate safeguards, although no online system can guarantee absolute security.</p>
  <h2>Your requests</h2><p>You may unsubscribe at any time or contact us to request review, correction or deletion of information you submitted, subject to verification and legitimate retention requirements.</p>
  <h2>Updates and contact</h2><p>This policy may change as features or legal requirements evolve. Questions can be sent through the Pakistan Jobs Market Contact Us page.</p>
`;

export default function PrivacyPage() {
  return (
    <ManagedPage slug="privacy" fallbackTitle="Privacy Policy" fallbackContent={FALLBACK} />
  );
}
