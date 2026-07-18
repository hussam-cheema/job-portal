"use client";

import { useRef, useState } from "react";

type CoverLetterData = {
  documentTitle: string;
  subtitle: string;
  fullName: string;
  phone: string;
  email: string;
  address: string;
  letterDate: string;
  contactName: string;
  companyName: string;
  companyAddress: string;
  contactSurname: string;
  openingParagraph: string;
  bodyParagraphOne: string;
  bodyParagraphTwo: string;
  closingParagraph: string;
  signOff: string;
};

const initialData: CoverLetterData = {
  documentTitle: "",
  subtitle: "",
  fullName: "",
  phone: "",
  email: "",
  address: "",
  letterDate: "",
  contactName: "",
  companyName: "",
  companyAddress: "",
  contactSurname: "",
  openingParagraph: "",
  bodyParagraphOne: "",
  bodyParagraphTwo: "",
  closingParagraph: "",
  signOff: "",
};

function formatLetterDate(value: string) {
  if (!value) return "31 August 20XX";
  const [year, month, day] = value.split("-").map(Number);
  if (!year || !month || !day) return value;
  return new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "long",
    year: "numeric",
    timeZone: "UTC",
  }).format(new Date(Date.UTC(year, month - 1, day)));
}

export function CoverLetterBuilder() {
  const previewRef = useRef<HTMLDivElement>(null);
  const [data, setData] = useState(initialData);
  const [downloading, setDownloading] = useState(false);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  function update<K extends keyof CoverLetterData>(key: K, value: CoverLetterData[K]) {
    setData((current) => ({ ...current, [key]: value }));
  }

  async function downloadPdf() {
    if (!previewRef.current) return;
    setDownloading(true);
    setDownloadError(null);
    try {
      await document.fonts.ready;
      const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
        import("html2canvas"),
        import("jspdf"),
      ]);
      const canvas = await html2canvas(previewRef.current, {
        backgroundColor: "#ffffff",
        scale: 2.4,
        useCORS: true,
        logging: false,
      });
      const pageWidth = 210;
      const pageHeight = 297;
      const naturalImageHeight = (canvas.height * pageWidth) / canvas.width;
      const imageHeight = naturalImageHeight <= pageHeight * 1.01 ? pageHeight : naturalImageHeight;
      const pages = Math.max(1, Math.ceil((imageHeight - 0.1) / pageHeight));
      const pdf = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4", compress: true });
      const image = canvas.toDataURL("image/jpeg", 0.98);
      for (let page = 0; page < pages; page += 1) {
        if (page > 0) pdf.addPage("a4", "portrait");
        pdf.addImage(image, "JPEG", 0, -(page * pageHeight), pageWidth, imageHeight, undefined, "FAST");
      }
      const safeName = (data.fullName || "professional")
        .trim()
        .toLowerCase()
        .replace(/[^a-z0-9]+/g, "-")
        .replace(/^-|-$/g, "");
      pdf.save(`${safeName || "professional"}-cover-letter.pdf`);
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : "The PDF could not be created.");
    } finally {
      setDownloading(false);
    }
  }

  return (
    <div className="site-wrap py-10">
      <div className="mb-8 max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--accent)]">
          Free career tool
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[var(--navy-100)] sm:text-4xl">
          Cover Letter
        </h1>
        <p className="mt-3 text-[var(--muted)]">
          Enter your information, review the live A4 letter, and download the finished PDF. Your
          information remains in this browser and is not submitted to PakistanJobs.
        </p>
      </div>

      <div className="grid gap-8 xl:grid-cols-[minmax(22rem,0.78fr)_minmax(0,1.22fr)] xl:items-start">
        <div className="space-y-5">
          <FormSection title="Document heading">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Cover letter title" value={data.documentTitle} placeholder="Google Cover Letter" onChange={(value) => update("documentTitle", value)} />
              <Field label="Subtitle" value={data.subtitle} placeholder="by CV Genius" onChange={(value) => update("subtitle", value)} />
            </div>
          </FormSection>

          <FormSection title="Your contact information">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Full name" value={data.fullName} placeholder="Your name" onChange={(value) => update("fullName", value)} />
              <Field label="Phone" type="tel" value={data.phone} placeholder="07123 456 789" onChange={(value) => update("phone", value)} />
              <Field label="Email" type="email" value={data.email} placeholder="your.email@gmail.com" onChange={(value) => update("email", value)} />
              <Field label="Address" value={data.address} placeholder="Street, city, postcode" onChange={(value) => update("address", value)} />
            </div>
          </FormSection>

          <FormSection title="Recipient information">
            <div className="grid gap-4 sm:grid-cols-2">
              <Field label="Letter date" type="date" value={data.letterDate} onChange={(value) => update("letterDate", value)} />
              <Field label="Contact person's name" value={data.contactName} onChange={(value) => update("contactName", value)} />
              <Field label="Company name" value={data.companyName} onChange={(value) => update("companyName", value)} />
              <Field label="Contact person's surname" value={data.contactSurname} onChange={(value) => update("contactSurname", value)} />
              <div className="sm:col-span-2">
                <TextArea label="Company address" value={data.companyAddress} rows={3} onChange={(value) => update("companyAddress", value)} />
              </div>
            </div>
          </FormSection>

          <FormSection title="Letter content">
            <div className="space-y-4">
              <TextArea label="Opening paragraph" value={data.openingParagraph} onChange={(value) => update("openingParagraph", value)} />
              <TextArea label="Experience paragraph 1" value={data.bodyParagraphOne} onChange={(value) => update("bodyParagraphOne", value)} />
              <TextArea label="Experience paragraph 2" value={data.bodyParagraphTwo} onChange={(value) => update("bodyParagraphTwo", value)} />
              <TextArea label="Closing paragraph" value={data.closingParagraph} onChange={(value) => update("closingParagraph", value)} />
              <Field label="Sign-off" value={data.signOff} placeholder="Yours sincerely," onChange={(value) => update("signOff", value)} />
            </div>
          </FormSection>
        </div>

        <aside className="xl:sticky xl:top-20">
          <div className="mb-3">
            <h2 className="font-semibold text-[var(--navy-100)]">A4 cover letter preview</h2>
            <p className="text-xs text-[var(--muted)]">The downloaded PDF uses this exact layout.</p>
          </div>
          <div className="cover-letter-preview-shell">
            <div ref={previewRef} className="cover-letter-paper" data-testid="cover-letter-preview">
              <header className="cover-letter-document-header">
                <h1>{data.documentTitle || "GOOGLE COVER LETTER"}</h1>
                <p>{data.subtitle || "by CV Genius"}</p>
              </header>
              <div className="cover-letter-contact-line">
                <span>{data.phone || "07123 456 789"}</span>
                <i aria-hidden="true">•</i>
                <span>{data.email || "your.email@gmail.com"}</span>
                <i aria-hidden="true">•</i>
                <span>{data.address || "26 Springfield Road, London, N39 6CU"}</span>
              </div>
              <div className="cover-letter-body">
                <p className="cover-letter-date">{formatLetterDate(data.letterDate)}</p>
                <div className="cover-letter-recipient">
                  <p>{data.contactName || "(Contact Person’s Name)"}</p>
                  <p>{data.companyName || "(Company Name)"}</p>
                  {(data.companyAddress || "(Company Address)").split("\n").map((line, index) => (
                    <p key={index}>{line}</p>
                  ))}
                </div>
                <p>Dear {data.contactSurname ? `${data.contactSurname},` : "(Contact Person’s Surname),"}</p>
                <p>
                  {data.openingParagraph ||
                    "I’m writing to express my interest in the advertised position. With relevant experience and a strong record of delivering results, I am eager to bring my expertise to your organisation."}
                </p>
                <p>
                  {data.bodyParagraphOne ||
                    "In my current role, I have successfully led important projects, improved processes, and collaborated with cross-functional teams. My commitment to quality and continuous improvement has enabled me to create measurable impact."}
                </p>
                <p>
                  {data.bodyParagraphTwo ||
                    "Throughout my career, I have demonstrated sound judgement, clear communication, and the ability to solve complex challenges. My experience and technical proficiency would allow me to contribute from the outset."}
                </p>
                <p>
                  {data.closingParagraph ||
                    "I’m excited by the opportunity to make a meaningful contribution. I welcome the chance to discuss how my skills and experience align with the needs of your team."}
                </p>
                <div className="cover-letter-signature">
                  <p>{data.signOff || "Yours sincerely,"}</p>
                  <strong>{data.fullName || "(YOUR NAME)"}</strong>
                </div>
              </div>
            </div>
          </div>
          {downloadError && <p className="field-error mt-3">{downloadError}</p>}
          <button
            type="button"
            className="btn btn-primary mt-4 w-full py-3 text-base"
            onClick={downloadPdf}
            disabled={downloading}
          >
            {downloading ? "Creating PDF…" : "Download Cover Letter as PDF"}
          </button>
        </aside>
      </div>
    </div>
  );
}

function FormSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="card-panel p-5">
      <h2 className="text-lg font-semibold text-[var(--navy-100)]">{title}</h2>
      <div className="mt-4">{children}</div>
    </section>
  );
}

function Field({
  label,
  value,
  onChange,
  placeholder,
  type = "text",
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  placeholder?: string;
  type?: string;
}) {
  return (
    <label className="block">
      <span className="field-label">{label}</span>
      <input
        className="input"
        type={type}
        value={value}
        placeholder={placeholder}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}

function TextArea({
  label,
  value,
  onChange,
  rows = 5,
}: {
  label: string;
  value: string;
  onChange: (value: string) => void;
  rows?: number;
}) {
  return (
    <label className="block">
      <span className="field-label">{label}</span>
      <textarea
        className="input resize-y"
        rows={rows}
        value={value}
        onChange={(event) => onChange(event.target.value)}
      />
    </label>
  );
}
