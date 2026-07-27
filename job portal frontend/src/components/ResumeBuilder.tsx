"use client";

import { useState } from "react";
import { useA4PreviewScale } from "@/hooks/useA4PreviewScale";
import {
  createResumeDocx,
  safeDocumentName,
  saveDocumentBlob,
} from "@/lib/documentDownloads";

type Education = {
  school: string;
  degree: string;
  details: string;
  coursework: string;
  location: string;
  graduationYear: string;
};

type Experience = {
  jobTitle: string;
  company: string;
  location: string;
  dates: string;
  achievements: string;
};

type Project = {
  title: string;
  dates: string;
  description: string;
  role: string;
  technologies: string;
  outcome: string;
};

type Activity = {
  name: string;
  dates: string;
  description: string;
  skills: string;
  achievements: string;
};

const inputClass = "builder-input";

const emptyEducation = (): Education => ({
  school: "",
  degree: "",
  details: "",
  coursework: "",
  location: "",
  graduationYear: "",
});

const emptyExperience = (): Experience => ({
  jobTitle: "",
  company: "",
  location: "",
  dates: "",
  achievements: "",
});

const emptyProject = (): Project => ({
  title: "",
  dates: "",
  description: "",
  role: "",
  technologies: "",
  outcome: "",
});

const emptyActivity = (): Activity => ({
  name: "",
  dates: "",
  description: "",
  skills: "",
  achievements: "",
});

function lines(value: string, fallback: string[]) {
  const items = value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
  return items.length ? items : fallback;
}

function ResumeSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="resume-section">
      <h2>{title}</h2>
      <div className="resume-section-rule" aria-hidden="true" />
      {children}
    </section>
  );
}

function RemoveButton({ onClick, label }: { onClick: () => void; label: string }) {
  return (
    <button type="button" className="builder-remove-button" onClick={onClick}>
      Remove {label}
    </button>
  );
}

export function ResumeBuilder() {
  const {
    documentRef: previewRef,
    documentStyle,
    shellRef,
    stageStyle,
  } = useA4PreviewScale();
  const [personal, setPersonal] = useState({
    fullName: "",
    address: "",
    phone: "",
    email: "",
  });
  const [education, setEducation] = useState<Education[]>([
    emptyEducation(),
    emptyEducation(),
  ]);
  const [experience, setExperience] = useState<Experience[]>([
    emptyExperience(),
    emptyExperience(),
  ]);
  const [projects, setProjects] = useState<Project[]>([emptyProject()]);
  const [activities, setActivities] = useState<Activity[]>([emptyActivity()]);
  const [additional, setAdditional] = useState({
    languages: "",
    technicalSkills: "",
    volunteerExperience: "",
    interests: "",
  });
  const [downloading, setDownloading] = useState<"pdf" | "docx" | null>(null);
  const [downloadError, setDownloadError] = useState<string | null>(null);

  function updateItem<T>(
    setter: React.Dispatch<React.SetStateAction<T[]>>,
    index: number,
    key: keyof T,
    value: string
  ) {
    setter((items) =>
      items.map((item, itemIndex) =>
        itemIndex === index ? ({ ...item, [key]: value } as T) : item
      )
    );
  }

  async function downloadPdf() {
    if (!previewRef.current) return;
    const preview = previewRef.current;
    const previewTransform = preview.style.transform;
    setDownloading("pdf");
    setDownloadError(null);
    try {
      // The live preview is scaled only to fit the browser panel. Capture the
      // original A4 document so the downloaded PDF keeps its full resolution.
      preview.style.transform = "none";
      await document.fonts.ready;
      const [{ default: html2canvas }, { jsPDF }] = await Promise.all([
        import("html2canvas"),
        import("jspdf"),
      ]);
      const canvas = await html2canvas(preview, {
        backgroundColor: "#ffffff",
        scale: 2.4,
        useCORS: true,
        logging: false,
      });
      const pageWidth = 210;
      const pageHeight = 297;
      const naturalImageHeight = (canvas.height * pageWidth) / canvas.width;
      // Browser pixel-to-millimetre rounding can make an exact A4 preview a
      // fraction taller than 297 mm. Treat that tiny difference as one page
      // instead of producing an otherwise blank second page.
      const imageHeight =
        naturalImageHeight <= pageHeight * 1.01 ? pageHeight : naturalImageHeight;
      const pages = Math.max(1, Math.ceil((imageHeight - 0.1) / pageHeight));
      const pdf = new jsPDF({ orientation: "portrait", unit: "mm", format: "a4", compress: true });
      const image = canvas.toDataURL("image/jpeg", 0.98);

      for (let page = 0; page < pages; page += 1) {
        if (page > 0) pdf.addPage("a4", "portrait");
        pdf.addImage(image, "JPEG", 0, -(page * pageHeight), pageWidth, imageHeight, undefined, "FAST");
      }

      pdf.save(`${safeDocumentName(personal.fullName)}-resume.pdf`);
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : "The PDF could not be created.");
    } finally {
      preview.style.transform = previewTransform;
      setDownloading(null);
    }
  }

  async function downloadDocx() {
    setDownloading("docx");
    setDownloadError(null);
    try {
      const blob = await createResumeDocx({
        personal,
        education,
        experience,
        projects,
        activities,
        additional,
      });
      saveDocumentBlob(blob, `${safeDocumentName(personal.fullName)}-resume.docx`);
    } catch (error) {
      setDownloadError(error instanceof Error ? error.message : "The Word document could not be created.");
    } finally {
      setDownloading(null);
    }
  }

  return (
    <div className="career-builder site-wrap py-10">
      <div className="builder-intro mb-8 max-w-3xl">
        <p className="text-xs font-semibold uppercase tracking-[0.18em] text-[var(--accent)]">
          Free career tool
        </p>
        <h1 className="mt-2 text-3xl font-semibold tracking-tight text-[var(--navy-100)] sm:text-4xl">
          Resume Builder
        </h1>
        <p className="mt-3 text-[var(--muted)]">
          Enter your information, review the live A4 preview, and download a professional PDF or
          editable Word document.
          Your information stays in this browser and is not submitted to Pakistan Jobs Market.
        </p>
      </div>

      <div className="builder-workspace grid gap-8 xl:grid-cols-[minmax(22rem,0.78fr)_minmax(0,1.22fr)] xl:items-start">
        <div className="builder-form-stack space-y-5">
          <section className="builder-form-card">
            <h2 className="text-lg font-semibold text-[var(--navy-100)]">Contact information</h2>
            <div className="mt-4 grid gap-4 sm:grid-cols-2">
              <Field label="Full name" value={personal.fullName} placeholder="Mary Leannon" onChange={(value) => setPersonal((item) => ({ ...item, fullName: value }))} />
              <Field label="Email" type="email" value={personal.email} placeholder="maryleannon@mail.com" onChange={(value) => setPersonal((item) => ({ ...item, email: value }))} />
              <Field label="Address" value={personal.address} placeholder="Street, city, province" onChange={(value) => setPersonal((item) => ({ ...item, address: value }))} />
              <Field label="Phone" type="tel" value={personal.phone} placeholder="+92 300 1234567" onChange={(value) => setPersonal((item) => ({ ...item, phone: value }))} />
            </div>
          </section>

          <section className="builder-form-card">
            <EditorHeading title="Education" onAdd={() => setEducation((items) => [...items, emptyEducation()])} />
            <div className="mt-4 space-y-5">
              {education.map((item, index) => (
                <div key={index} className="resume-editor-entry">
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="font-medium text-[var(--navy-200)]">Education {index + 1}</h3>
                    {education.length > 1 && <RemoveButton label="education" onClick={() => setEducation((items) => items.filter((_, i) => i !== index))} />}
                  </div>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2">
                    <Field label="University / school" value={item.school} onChange={(value) => updateItem(setEducation, index, "school", value)} />
                    <Field label="Location" value={item.location} onChange={(value) => updateItem(setEducation, index, "location", value)} />
                    <Field label="Degree / programme" value={item.degree} onChange={(value) => updateItem(setEducation, index, "degree", value)} />
                    <Field label="Graduation year" value={item.graduationYear} onChange={(value) => updateItem(setEducation, index, "graduationYear", value)} />
                    <Field label="GPA, honours or activities" value={item.details} onChange={(value) => updateItem(setEducation, index, "details", value)} />
                    <Field label="Relevant coursework" value={item.coursework} onChange={(value) => updateItem(setEducation, index, "coursework", value)} />
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="builder-form-card">
            <EditorHeading title="Experience" onAdd={() => setExperience((items) => [...items, emptyExperience()])} />
            <div className="mt-4 space-y-5">
              {experience.map((item, index) => (
                <div key={index} className="resume-editor-entry">
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="font-medium text-[var(--navy-200)]">Position {index + 1}</h3>
                    {experience.length > 1 && <RemoveButton label="position" onClick={() => setExperience((items) => items.filter((_, i) => i !== index))} />}
                  </div>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2">
                    <Field label="Job title" value={item.jobTitle} onChange={(value) => updateItem(setExperience, index, "jobTitle", value)} />
                    <Field label="Location" value={item.location} onChange={(value) => updateItem(setExperience, index, "location", value)} />
                    <Field label="Company" value={item.company} onChange={(value) => updateItem(setExperience, index, "company", value)} />
                    <Field label="Employment dates" value={item.dates} placeholder="Jan 2024 - Present" onChange={(value) => updateItem(setExperience, index, "dates", value)} />
                  </div>
                  <TextArea label="Achievements (one bullet per line)" value={item.achievements} onChange={(value) => updateItem(setExperience, index, "achievements", value)} />
                </div>
              ))}
            </div>
          </section>

          <section className="builder-form-card">
            <EditorHeading title="University projects" onAdd={() => setProjects((items) => [...items, emptyProject()])} />
            <div className="mt-4 space-y-5">
              {projects.map((item, index) => (
                <div key={index} className="resume-editor-entry">
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="font-medium text-[var(--navy-200)]">Project {index + 1}</h3>
                    {projects.length > 1 && <RemoveButton label="project" onClick={() => setProjects((items) => items.filter((_, i) => i !== index))} />}
                  </div>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2">
                    <Field label="Project title" value={item.title} onChange={(value) => updateItem(setProjects, index, "title", value)} />
                    <Field label="Dates" value={item.dates} onChange={(value) => updateItem(setProjects, index, "dates", value)} />
                    <Field label="Description" value={item.description} onChange={(value) => updateItem(setProjects, index, "description", value)} />
                    <Field label="Your role" value={item.role} onChange={(value) => updateItem(setProjects, index, "role", value)} />
                    <Field label="Technologies used" value={item.technologies} onChange={(value) => updateItem(setProjects, index, "technologies", value)} />
                    <Field label="Outcome" value={item.outcome} onChange={(value) => updateItem(setProjects, index, "outcome", value)} />
                  </div>
                </div>
              ))}
            </div>
          </section>

          <section className="builder-form-card">
            <EditorHeading title="Activities" onAdd={() => setActivities((items) => [...items, emptyActivity()])} />
            <div className="mt-4 space-y-5">
              {activities.map((item, index) => (
                <div key={index} className="resume-editor-entry">
                  <div className="flex items-center justify-between gap-3">
                    <h3 className="font-medium text-[var(--navy-200)]">Activity {index + 1}</h3>
                    {activities.length > 1 && <RemoveButton label="activity" onClick={() => setActivities((items) => items.filter((_, i) => i !== index))} />}
                  </div>
                  <div className="mt-3 grid gap-3 sm:grid-cols-2">
                    <Field label="Activity name" value={item.name} onChange={(value) => updateItem(setActivities, index, "name", value)} />
                    <Field label="Dates" value={item.dates} onChange={(value) => updateItem(setActivities, index, "dates", value)} />
                    <Field label="Description" value={item.description} onChange={(value) => updateItem(setActivities, index, "description", value)} />
                    <Field label="Skills developed" value={item.skills} onChange={(value) => updateItem(setActivities, index, "skills", value)} />
                  </div>
                  <Field label="Achievements" value={item.achievements} onChange={(value) => updateItem(setActivities, index, "achievements", value)} />
                </div>
              ))}
            </div>
          </section>

          <section className="builder-form-card">
            <h2 className="text-lg font-semibold text-[var(--navy-100)]">Additional information</h2>
            <div className="mt-4 grid gap-4">
              <Field label="Language skills" value={additional.languages} onChange={(value) => setAdditional((item) => ({ ...item, languages: value }))} />
              <Field label="Technical skills" value={additional.technicalSkills} onChange={(value) => setAdditional((item) => ({ ...item, technicalSkills: value }))} />
              <Field label="Volunteer experience" value={additional.volunteerExperience} onChange={(value) => setAdditional((item) => ({ ...item, volunteerExperience: value }))} />
              <Field label="Interests / hobbies" value={additional.interests} onChange={(value) => setAdditional((item) => ({ ...item, interests: value }))} />
            </div>
          </section>
        </div>

        <aside className="builder-preview-panel xl:sticky xl:top-20">
          <div className="builder-preview-heading mb-3 flex items-center justify-between gap-3">
            <div>
              <h2 className="font-semibold text-[var(--navy-100)]">A4 resume preview</h2>
              <p className="text-xs text-[var(--muted)]">
                Download a print-ready PDF or an editable Word document.
              </p>
            </div>
          </div>
          <div ref={shellRef} className="resume-preview-shell" data-testid="resume-preview-shell">
            <div className="document-preview-stage" style={stageStyle}>
              <div ref={previewRef} className="resume-paper" style={documentStyle} data-testid="resume-preview">
              <header className="resume-header">
                <h1>{personal.fullName || "YOUR NAME"}</h1>
                <p>
                  {[personal.address || "Address", personal.phone || "Phone", personal.email || "Email"]
                    .filter(Boolean)
                    .join(" • ")}
                </p>
              </header>

              <ResumeSection title="Education">
                {education.map((item, index) => (
                  <div className="resume-entry" key={index}>
                    <div className="resume-entry-row">
                      <div>
                        <h3>{item.school || (index === 0 ? "[UNIVERSITY/COLLEGE NAME]" : "[YOUR HIGH SCHOOL NAME]")}</h3>
                        <p>{item.degree || (index === 0 ? "[Bachelor of Science in Major]" : "Include any honours, awards, or relevant extracurricular activities if applicable.")}</p>
                      </div>
                      <div className="resume-entry-aside">
                        <p>{item.location || (index === 0 ? "[Location]" : "[City, State]")}</p>
                        <p>{item.graduationYear || "[Year of Graduation]"}</p>
                      </div>
                    </div>
                    {index === 0 ? (
                      <>
                        <p>{item.details || "GPA: [Your GPA, if it is above 3.0]"}</p>
                        <p>Relevant coursework: {item.coursework || "[List any specific courses relevant to the job]"}</p>
                      </>
                    ) : (
                      <p>{item.details || "If you have pursued any specialized coursework or achieved notable academic accomplishments during high school."}</p>
                    )}
                  </div>
                ))}
              </ResumeSection>

              <ResumeSection title="Experience">
                {experience.map((item, index) => (
                  <div className="resume-entry" key={index}>
                    <div className="resume-entry-row">
                      <div>
                        <h3>{item.jobTitle || "[JOB TITLE]"}</h3>
                        <p>{item.company || "[Company Name]"}</p>
                      </div>
                      <div className="resume-entry-aside">
                        <p>{item.location || "[Location]"}</p>
                        <p>{item.dates || "[Dates of Employment]"}</p>
                      </div>
                    </div>
                    <ul>
                      {lines(item.achievements, [
                        "Spearheaded [specific project or initiative], resulting in [quantifiable achievement].",
                        "Collaborated with cross-functional teams to [accomplishment or task].",
                        "Implemented [strategy or process improvement], leading to [positive outcome].",
                        "Managed [specific responsibility or duty], ensuring [desired outcome].",
                      ]).map((achievement, bulletIndex) => <li key={bulletIndex}>{achievement}</li>)}
                    </ul>
                  </div>
                ))}
              </ResumeSection>

              <ResumeSection title="University Projects">
                {projects.map((item, index) => (
                  <div className="resume-entry" key={index}>
                    <div className="resume-entry-row">
                      <h3>{item.title || "[PROJECT TITLE]"}</h3>
                      <div className="resume-entry-aside"><p>{item.dates || "[Dates]"}</p></div>
                    </div>
                    <ul>
                      <li>Description: {item.description || "Brief overview of the project and its objectives."}</li>
                      <li>Role: {item.role || "Your specific role or contribution to the project."}</li>
                      <li>Technologies Used: {item.technologies || "Any tools, software, or programming languages utilized."}</li>
                      <li>Outcome: {item.outcome || "Results achieved or lessons learned from the project."}</li>
                    </ul>
                  </div>
                ))}
              </ResumeSection>

              <ResumeSection title="Activities">
                {activities.map((item, index) => (
                  <div className="resume-entry" key={index}>
                    <div className="resume-entry-row">
                      <h3>{item.name || "[ACTIVITY NAME]"}</h3>
                      <div className="resume-entry-aside"><p>{item.dates || "[Dates]"}</p></div>
                    </div>
                    <ul>
                      <li>Description: {item.description || "Brief overview of the activity and your role."}</li>
                      <li>Skills Developed: {item.skills || "Any relevant skills or qualities honed through participation."}</li>
                      <li>Achievements: {item.achievements || "Any notable achievements or leadership roles within the activity."}</li>
                    </ul>
                  </div>
                ))}
              </ResumeSection>

              <ResumeSection title="Additional">
                <div className="resume-additional">
                  <p><strong>Language Skills:</strong> {additional.languages || "[List any languages you speak fluently or proficiently.]"}</p>
                  <p><strong>Technical Skills:</strong> {additional.technicalSkills || "[List any relevant technical skills or software proficiencies.]"}</p>
                  <p><strong>Volunteer Experience:</strong> {additional.volunteerExperience || "[Briefly mention any volunteer work you have done, highlighting skills or experiences gained.]"}</p>
                  <p><strong>Interests/Hobbies:</strong> {additional.interests || "[Include any interests or hobbies that demonstrate relevant skills or qualities, or provide insight into your personality.]"}</p>
                </div>
              </ResumeSection>
              </div>
            </div>
          </div>

          {downloadError && <p className="field-error mt-3">{downloadError}</p>}
          <div className="builder-download-actions mt-4">
            <button
              type="button"
              className="download-document-button download-pdf-button w-full"
              onClick={downloadPdf}
              disabled={downloading !== null}
              aria-label="Download Resume as PDF"
            >
              <DownloadIcon />
              <span className="download-document-copy">
                <strong>{downloading === "pdf" ? "Creating your PDF…" : "Download Resume as PDF"}</strong>
                <small>Print-ready A4 document</small>
              </span>
              <span className="download-document-arrow" aria-hidden="true">→</span>
            </button>
            <button
              type="button"
              className="download-document-button download-docx-button w-full"
              onClick={downloadDocx}
              disabled={downloading !== null}
              aria-label="Download Resume as DOCX"
            >
              <DownloadIcon />
              <span className="download-document-copy">
                <strong>{downloading === "docx" ? "Creating your DOCX…" : "Download Resume as DOCX"}</strong>
                <small>Editable Microsoft Word document</small>
              </span>
              <span className="download-document-arrow" aria-hidden="true">→</span>
            </button>
          </div>
        </aside>
      </div>
    </div>
  );
}

function DownloadIcon() {
  return (
    <span className="download-document-icon" aria-hidden="true">
      <svg viewBox="0 0 24 24" fill="none">
        <path d="M12 3v11m0 0 4-4m-4 4-4-4M5 17v2a2 2 0 0 0 2 2h10a2 2 0 0 0 2-2v-2" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round" />
      </svg>
    </span>
  );
}

function EditorHeading({ title, onAdd }: { title: string; onAdd: () => void }) {
  return (
    <div className="flex items-center justify-between gap-3">
      <h2 className="text-lg font-semibold text-[var(--navy-100)]">{title}</h2>
      <button type="button" className="builder-add-button" onClick={onAdd}>
        <span aria-hidden="true">+</span> Add another
      </button>
    </div>
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
      <span className="builder-field-label">{label}</span>
      <input className={inputClass} type={type} value={value} placeholder={placeholder} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}

function TextArea({ label, value, onChange }: { label: string; value: string; onChange: (value: string) => void }) {
  return (
    <label className="mt-3 block">
      <span className="builder-field-label">{label}</span>
      <textarea className={`${inputClass} builder-textarea min-h-28 resize-y`} value={value} onChange={(event) => onChange(event.target.value)} />
    </label>
  );
}
