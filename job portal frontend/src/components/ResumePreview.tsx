import type {
  ResumeAdditionalSelection,
  ResumeDocumentData,
  ResumeSectionSelection,
  ResumeTemplateId,
} from "@/lib/documentDownloads";

type PreviewProps = {
  data: ResumeDocumentData;
  template: ResumeTemplateId;
};

const sectionDefaults: ResumeSectionSelection = {
  education: true,
  experience: true,
  projects: true,
  activities: true,
  additional: true,
};

const additionalDefaults: ResumeAdditionalSelection = {
  languages: true,
  technicalSkills: true,
  volunteerExperience: true,
  interests: true,
};

function lines(value: string, fallback: string[]) {
  const values = value.split("\n").map((item) => item.trim()).filter(Boolean);
  return values.length ? values : fallback;
}

function initials(name: string) {
  const value = name.trim() || "Your Name";
  return value.split(/\s+/).slice(0, 2).map((part) => part[0]?.toUpperCase()).join("");
}

function contactLine(data: ResumeDocumentData) {
  return [data.personal.address || "Address", data.personal.phone || "Phone", data.personal.email || "Email"]
    .filter(Boolean)
    .join(" • ");
}

function skillItems(data: ResumeDocumentData) {
  return (data.additional.technicalSkills || "Research, Communication, Microsoft Office, Teamwork")
    .split(/[,\n]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function ClassicSection({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section className="resume-section">
      <h2>{title}</h2>
      <div className="resume-section-rule" aria-hidden="true" />
      {children}
    </section>
  );
}

function EducationEntries({ data, compact = false }: { data: ResumeDocumentData; compact?: boolean }) {
  return <>{data.education.map((item, index) => (
    <article className={compact ? "styled-resume-entry is-compact" : "styled-resume-entry"} key={index}>
      <div className="styled-entry-heading">
        <div>
          <h3>{item.school || (index === 0 ? "[UNIVERSITY / COLLEGE]" : "[SCHOOL NAME]")}</h3>
          <p>{item.degree || "[Degree / programme]"}</p>
        </div>
        <span>{item.graduationYear || "[Year]"}</span>
      </div>
      <p className="styled-entry-meta">{item.location || "[Location]"}</p>
      <p>{item.details || "Academic achievements, honours and relevant activities."}</p>
      {item.coursework && <p><strong>Coursework:</strong> {item.coursework}</p>}
    </article>
  ))}</>;
}

function ExperienceEntries({ data, compact = false }: { data: ResumeDocumentData; compact?: boolean }) {
  return <>{data.experience.map((item, index) => (
    <article className={compact ? "styled-resume-entry is-compact" : "styled-resume-entry"} key={index}>
      <div className="styled-entry-heading">
        <div>
          <h3>{item.jobTitle || "[JOB TITLE]"}</h3>
          <p>{item.company || "[Company Name]"}</p>
        </div>
        <span>{item.dates || "[Employment dates]"}</span>
      </div>
      <p className="styled-entry-meta">{item.location || "[Location]"}</p>
      <ul>{lines(item.achievements, [
        "Describe a measurable achievement or responsibility.",
        "Explain the impact of your work on the team or organisation.",
      ]).map((item, itemIndex) => <li key={itemIndex}>{item}</li>)}</ul>
    </article>
  ))}</>;
}

function ProjectEntries({ data }: { data: ResumeDocumentData }) {
  return <>{data.projects.map((item, index) => (
    <article className="styled-resume-entry is-compact" key={index}>
      <div className="styled-entry-heading"><h3>{item.title || "[PROJECT TITLE]"}</h3><span>{item.dates || "[Dates]"}</span></div>
      <p>{item.description || "Brief overview of the project and its objective."}</p>
      <p><strong>Role:</strong> {item.role || "Your contribution"}</p>
      <p><strong>Tools:</strong> {item.technologies || "Relevant technologies"}</p>
      <p><strong>Outcome:</strong> {item.outcome || "Result or lesson learned"}</p>
    </article>
  ))}</>;
}

function ActivityEntries({ data }: { data: ResumeDocumentData }) {
  return <>{data.activities.map((item, index) => (
    <article className="styled-resume-entry is-compact" key={index}>
      <div className="styled-entry-heading"><h3>{item.name || "[ACTIVITY NAME]"}</h3><span>{item.dates || "[Dates]"}</span></div>
      <p>{item.description || "Brief overview of your participation and role."}</p>
      <p><strong>Skills:</strong> {item.skills || "Relevant skills developed"}</p>
      <p><strong>Achievements:</strong> {item.achievements || "Leadership or notable result"}</p>
    </article>
  ))}</>;
}

function AdditionalDetails({ data, include }: { data: ResumeDocumentData; include: ResumeAdditionalSelection }) {
  return <div className="styled-additional-list">
    {include.languages && <p><strong>Languages</strong><span>{data.additional.languages || "English, Urdu"}</span></p>}
    {include.technicalSkills && <p><strong>Technical skills</strong><span>{data.additional.technicalSkills || "Add your software and technical strengths"}</span></p>}
    {include.volunteerExperience && <p><strong>Volunteering</strong><span>{data.additional.volunteerExperience || "Add relevant community experience"}</span></p>}
    {include.interests && <p><strong>Interests</strong><span>{data.additional.interests || "Add interests that support your application"}</span></p>}
  </div>;
}

function ClassicResume({ data, sections, extra }: { data: ResumeDocumentData; sections: ResumeSectionSelection; extra: ResumeAdditionalSelection }) {
  return <>
    <header className="resume-header">
      <h1>{data.personal.fullName || "YOUR NAME"}</h1>
      <p>{contactLine(data)}</p>
    </header>
    {sections.education && <ClassicSection title="Education"><EducationEntries data={data} /></ClassicSection>}
    {sections.experience && <ClassicSection title="Experience"><ExperienceEntries data={data} /></ClassicSection>}
    {sections.projects && <ClassicSection title="University Projects"><ProjectEntries data={data} /></ClassicSection>}
    {sections.activities && <ClassicSection title="Activities"><ActivityEntries data={data} /></ClassicSection>}
    {sections.additional && Object.values(extra).some(Boolean) && <ClassicSection title="Additional"><AdditionalDetails data={data} include={extra} /></ClassicSection>}
  </>;
}

function EditorialResume({ data, sections, extra }: { data: ResumeDocumentData; sections: ResumeSectionSelection; extra: ResumeAdditionalSelection }) {
  const profile = data.additional.volunteerExperience || data.additional.interests || "A focused professional who brings clear communication, practical judgement and a strong commitment to high-quality work.";
  return <div className="editorial-layout">
    <aside className="editorial-sidebar">
      <div className="resume-avatar editorial-avatar" aria-hidden="true">{initials(data.personal.fullName)}</div>
      <section><h2>About me</h2><p>{profile}</p></section>
      {sections.additional && extra.technicalSkills && <section><h2>Skills</h2><div className="editorial-skills">{skillItems(data).map((skill, index) => <p key={skill}><span>{skill}</span><i style={{ width: `${88 - (index % 4) * 12}%` }} /></p>)}</div></section>}
      {sections.additional && extra.languages && <section><h2>Languages</h2><p>{data.additional.languages || "English, Urdu"}</p></section>}
    </aside>
    <main className="editorial-main">
      <header><div className="editorial-name-band" /><h1>{data.personal.fullName || "YOUR NAME"}</h1><p>{contactLine(data)}</p></header>
      {sections.experience && <section className="editorial-section"><h2>Experience</h2><ExperienceEntries data={data} compact /></section>}
      {sections.education && <section className="editorial-section"><h2>Education</h2><EducationEntries data={data} compact /></section>}
      {sections.projects && <section className="editorial-section"><h2>Projects</h2><ProjectEntries data={data} /></section>}
      {sections.activities && <section className="editorial-section"><h2>Activities</h2><ActivityEntries data={data} /></section>}
    </main>
  </div>;
}

function EvergreenResume({ data, sections, extra }: { data: ResumeDocumentData; sections: ResumeSectionSelection; extra: ResumeAdditionalSelection }) {
  const headline = data.experience[0]?.jobTitle || data.education[0]?.degree || "Professional Profile";
  return <div className="evergreen-layout">
    <aside className="evergreen-sidebar">
      <div className="evergreen-avatar-frame"><div className="resume-avatar evergreen-avatar" aria-hidden="true">{initials(data.personal.fullName)}</div></div>
      <h1>{data.personal.fullName || "YOUR NAME"}</h1><p className="evergreen-headline">{headline}</p>
      <section><h2>Profile</h2><p>{data.additional.volunteerExperience || data.additional.interests || "Summarise your strengths, goals and the value you offer an employer."}</p></section>
      <section><h2>Contact</h2><p>{data.personal.phone || "Phone"}</p><p>{data.personal.email || "Email"}</p><p>{data.personal.address || "Address"}</p></section>
      {sections.additional && extra.languages && <section><h2>Languages</h2><p>{data.additional.languages || "English, Urdu"}</p></section>}
    </aside>
    <main className="evergreen-main">
      {sections.education && <section className="evergreen-section"><h2>Education</h2><EducationEntries data={data} compact /></section>}
      {sections.experience && <section className="evergreen-section"><h2>Work experience</h2><ExperienceEntries data={data} compact /></section>}
      {sections.additional && extra.technicalSkills && <section className="evergreen-section"><h2>Skills</h2><div className="evergreen-skills">{skillItems(data).map((skill, index) => <p key={skill}><span>{skill}</span><i><b style={{ width: `${90 - (index % 4) * 14}%` }} /></i></p>)}</div></section>}
      {sections.projects && <section className="evergreen-section"><h2>Projects</h2><ProjectEntries data={data} /></section>}
      {sections.activities && <section className="evergreen-section"><h2>Activities</h2><ActivityEntries data={data} /></section>}
    </main>
  </div>;
}

function ModernResume({ data, sections, extra }: { data: ResumeDocumentData; sections: ResumeSectionSelection; extra: ResumeAdditionalSelection }) {
  const headline = data.experience[0]?.jobTitle || data.education[0]?.degree || "Emerging Professional";
  return <div className="modern-layout">
    <header className="modern-header">
      <div><h1>{data.personal.fullName || "YOUR NAME"}</h1><h2>{headline}</h2><p>{data.additional.volunteerExperience || data.additional.interests || "Write a concise professional profile through the existing additional-information fields."}</p></div>
      <address><p>{data.personal.email || "Email"}<span>✉</span></p><p>{data.personal.phone || "Phone"}<span>☎</span></p><p>{data.personal.address || "Address"}<span>⌖</span></p></address>
    </header>
    <div className="modern-divider" />
    <div className="modern-columns">
      <main>
        {sections.experience && <section className="modern-section"><h2>Work experience</h2><ExperienceEntries data={data} /></section>}
        {sections.education && <section className="modern-section"><h2>Education</h2><EducationEntries data={data} compact /></section>}
      </main>
      <aside>
        {sections.additional && extra.technicalSkills && <section className="modern-section"><h2>Skills</h2><div className="modern-skills">{skillItems(data).map((skill) => <span key={skill}>{skill}</span>)}</div></section>}
        {sections.projects && <section className="modern-section"><h2>Projects</h2><ProjectEntries data={data} /></section>}
        {sections.activities && <section className="modern-section"><h2>Activities</h2><ActivityEntries data={data} /></section>}
        {sections.additional && <section className="modern-section"><h2>Additional</h2><AdditionalDetails data={data} include={{ ...extra, technicalSkills: false }} /></section>}
      </aside>
    </div>
  </div>;
}

export function ResumePreview({ data, template }: PreviewProps) {
  const sections = { ...sectionDefaults, ...data.includedSections };
  const extra = { ...additionalDefaults, ...data.includedAdditional };
  if (template === "editorial") return <EditorialResume data={data} sections={sections} extra={extra} />;
  if (template === "evergreen") return <EvergreenResume data={data} sections={sections} extra={extra} />;
  if (template === "modern") return <ModernResume data={data} sections={sections} extra={extra} />;
  return <ClassicResume data={data} sections={sections} extra={extra} />;
}
