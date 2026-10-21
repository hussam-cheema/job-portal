import type { Metadata } from "next";
import { ManagedPage } from "@/components/ManagedPage";

export const metadata: Metadata = {
  title: { absolute: "Privacy Policy | Pakistan Jobs Market" },
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
  <p><strong>Effective date:</strong> 21 October 2026</p>
  <h2>Information we may collect</h2><p>We may process an email address submitted for job alerts, contact-form details, essential preferences, and limited technical information such as requested pages, browser data, IP address, timestamps and error records.</p>
  <h2>How information is used</h2><p>Information supports requested alerts, responses to messages, abuse prevention, security, diagnostics, aggregate analytics and service improvement. We do not sell or rent personal information.</p>
  <h2>Resume Builder and ATS score</h2><p>Information entered in the Resume Builder and the resulting ATS-readiness score are processed in your browser to create the preview, score and downloads. Pakistan Jobs Market does not receive or store that resume content or score. Closing or refreshing the page may remove the information unless your browser preserves it independently.</p>
  <h2>Email alerts and choices</h2><p>Subscribers receive messages about newly published jobs and can use the unsubscribe link in an alert to remove their active subscription.</p>
  <h2>Student API access</h2><p>For the subscriber-only student API, we process the subscribed email, short-lived verification state, one-way code and key hashes, a short key prefix, access status, lifetime quota and request counts, timestamps, and hashed network identifiers used for abuse prevention. Readable codes and full keys are not stored. Unsubscribing disables the key; a minimal inactive quota and security ledger may be retained to prevent abuse and repeated quota creation.</p>
  <h2>Cookies, analytics and advertising</h2><p>Essential storage and third-party services may support preferences, measurement, performance and advertising.</p>
  <h3>Google advertising cookies and personalized advertising</h3>
  <p>Third-party vendors, including Google, use cookies to serve ads based on a visitor's previous visits to Pakistan Jobs Market or other websites. Google's use of advertising cookies enables Google and its partners to serve ads based on visits to this website and/or other websites on the Internet.</p>
  <p>Visitors may manage or opt out of personalized advertising through <a href="https://adssettings.google.com/" rel="noopener noreferrer">Google Ads Settings</a>. Visitors may also use the <a href="https://www.aboutads.info/choices/" rel="noopener noreferrer">YourAdChoices opt-out page</a> to opt out of some third-party vendors' use of cookies for personalized advertising.</p>
  <p>Learn more about <a href="https://policies.google.com/technologies/partner-sites" rel="noopener noreferrer">how Google uses information from sites that use its services</a>, <a href="https://policies.google.com/technologies/ads" rel="noopener noreferrer">Google advertising technologies</a>, and the <a href="https://policies.google.com/privacy" rel="noopener noreferrer">Google Privacy Policy</a>. Where other advertising vendors or networks are enabled, their identities and privacy choices will be disclosed through the applicable consent message or this policy.</p>
  <h3>Consent choices for regulated regions</h3><p>For visitors in the European Economic Area, the United Kingdom and Switzerland, Pakistan Jobs Market uses Google-certified consent-management controls to request applicable choices for advertising cookies, local storage, personalized advertising and related data processing.</p>
  <h2>External services and retention</h2><p>Hosting, database, object-storage, email and analytics providers process limited data required to operate the site. External job links have their own privacy practices. We retain information only as reasonably needed and use appropriate safeguards, although no online system can guarantee absolute security.</p>
  <h2>Your requests</h2><p>You may unsubscribe at any time or contact us to request review, correction or deletion of information you submitted, subject to verification and legitimate retention requirements.</p>
  <h2>Updates and contact</h2><p>This policy may change as features or legal requirements evolve. Questions can be sent through the Pakistan Jobs Market Contact Us page.</p>
`;

export default function PrivacyPage() {
  return (
    <ManagedPage slug="privacy" fallbackTitle="Privacy Policy" fallbackContent={FALLBACK} />
  );
}
