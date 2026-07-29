import type {
  ResumeAdditionalSelection,
  ResumeDocumentData,
  ResumeSectionSelection,
} from "@/lib/documentDownloads";

export type AtsScoreCategory = {
  label: string;
  score: number;
  maximum: number;
  feedback: string;
};

export type AtsScoreResult = {
  score: number;
  band: "Excellent" | "Strong" | "Developing" | "Incomplete";
  summary: string;
  categories: AtsScoreCategory[];
  recommendations: string[];
};

const DEFAULT_SECTIONS: ResumeSectionSelection = {
  education: true,
  experience: true,
  projects: true,
  activities: true,
  additional: true,
};

const DEFAULT_ADDITIONAL: ResumeAdditionalSelection = {
  languages: true,
  technicalSkills: true,
  volunteerExperience: true,
  interests: true,
};

const ACTION_VERBS = new Set([
  "achieved",
  "analysed",
  "analyzed",
  "automated",
  "built",
  "collaborated",
  "created",
  "delivered",
  "designed",
  "developed",
  "directed",
  "established",
  "generated",
  "grew",
  "implemented",
  "improved",
  "increased",
  "launched",
  "led",
  "managed",
  "mentored",
  "optimized",
  "organised",
  "organized",
  "reduced",
  "resolved",
  "spearheaded",
  "streamlined",
  "supported",
  "trained",
]);

function filled(value: string) {
  return value.trim().length > 0;
}

function words(value: string) {
  return value.trim().split(/\s+/).filter(Boolean);
}

function bulletLines(value: string) {
  return value
    .split("\n")
    .map((item) => item.trim().replace(/^[•*-]\s*/, ""))
    .filter(Boolean);
}

function commaSeparatedItems(value: string) {
  return value
    .split(/[,;\n|]/)
    .map((item) => item.trim())
    .filter(Boolean);
}

function category(
  label: string,
  score: number,
  maximum: number,
  feedback: string
): AtsScoreCategory {
  return { label, score: Math.min(score, maximum), maximum, feedback };
}

/**
 * Provides a transparent, deterministic ATS-readiness estimate for the resume
 * form. It does not call an external service and does not claim to reproduce a
 * particular employer's proprietary applicant-tracking system.
 */
export function scoreResumeForAts(data: ResumeDocumentData): AtsScoreResult {
  const includedSections = { ...DEFAULT_SECTIONS, ...data.includedSections };
  const includedAdditional = { ...DEFAULT_ADDITIONAL, ...data.includedAdditional };
  const recommendations: string[] = [];
  const categories: AtsScoreCategory[] = [];

  let contactScore = 0;
  if (words(data.personal.fullName).length >= 2) contactScore += 4;
  else recommendations.push("Add your full professional name.");
  if (/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(data.personal.email.trim())) contactScore += 5;
  else recommendations.push("Add a valid professional email address.");
  if (data.personal.phone.replace(/\D/g, "").length >= 10) contactScore += 4;
  else recommendations.push("Add a complete phone number with area or country code.");
  if (words(data.personal.address).length >= 2) contactScore += 2;
  categories.push(
    category(
      "Contact details",
      contactScore,
      15,
      contactScore === 15
        ? "Name, email, phone and location are ready for recruiters."
        : "Complete the contact details an ATS and recruiter expect."
    )
  );

  const completedEducation = data.education.filter(
    (item) => filled(item.school) && filled(item.degree)
  );
  const completedExperience = data.experience.filter(
    (item) => filled(item.jobTitle) && filled(item.company)
  );
  const completedProjects = data.projects.filter(
    (item) => filled(item.title) && (filled(item.description) || filled(item.outcome))
  );
  let structureScore = 2; // The builder always uses conventional, ordered headings.
  if (!includedSections.education || completedEducation.length > 0) structureScore += 6;
  else recommendations.push("Complete at least one education entry or hide that section.");
  if (!includedSections.experience || completedExperience.length > 0) structureScore += 7;
  else if (includedSections.projects && completedProjects.length > 0) structureScore += 5;
  else recommendations.push("Add relevant experience or a substantial project.");
  if (
    includedSections.additional &&
    includedAdditional.technicalSkills &&
    filled(data.additional.technicalSkills)
  ) {
    structureScore += 5;
  } else {
    recommendations.push("Include a focused technical or professional skills list.");
  }
  categories.push(
    category(
      "ATS structure",
      structureScore,
      20,
      structureScore >= 17
        ? "The selected sections use clear, conventional ATS headings."
        : "Strengthen the standard sections used to classify your experience."
    )
  );

  const achievementBullets = includedSections.experience
    ? data.experience.flatMap((item) => bulletLines(item.achievements))
    : [];
  const projectOutcomes = includedSections.projects
    ? data.projects.flatMap((item) => [item.outcome.trim()].filter(Boolean))
    : [];
  const evidenceStatements = [...achievementBullets, ...projectOutcomes];
  const actionLed = achievementBullets.filter((item) =>
    ACTION_VERBS.has(words(item)[0]?.toLowerCase().replace(/[^a-z]/g, "") || "")
  );
  const quantified = evidenceStatements.filter((item) =>
    /(?:\b\d+(?:\.\d+)?\s*%|\b\d+(?:,\d{3})*(?:\.\d+)?\b|PKR|Rs\.?|USD|\$)/i.test(item)
  );
  let impactScore = 0;
  if (achievementBullets.length >= 3) impactScore += 8;
  else if (achievementBullets.length > 0) impactScore += 4;
  if (achievementBullets.length >= 6) impactScore += 2;
  if (achievementBullets.length > 0) {
    impactScore += Math.round(7 * (actionLed.length / achievementBullets.length));
  }
  if (quantified.length >= 2) impactScore += 8;
  else if (quantified.length === 1) impactScore += 5;
  if (projectOutcomes.length > 0) impactScore += 2;
  if (achievementBullets.length < 3) {
    recommendations.push("Add at least three concise achievement bullets.");
  }
  if (actionLed.length < Math.ceil(Math.max(achievementBullets.length, 1) / 2)) {
    recommendations.push("Start more experience bullets with strong action verbs.");
  }
  if (quantified.length === 0) {
    recommendations.push("Quantify at least one result with a number, percentage or amount.");
  }
  categories.push(
    category(
      "Achievement impact",
      impactScore,
      25,
      impactScore >= 20
        ? "Your evidence uses action-led, measurable accomplishments."
        : "Add stronger action verbs and measurable outcomes."
    )
  );

  const skills = includedAdditional.technicalSkills
    ? commaSeparatedItems(data.additional.technicalSkills)
    : [];
  const technologies = includedSections.projects
    ? data.projects.flatMap((item) => commaSeparatedItems(item.technologies))
    : [];
  const coursework = includedSections.education
    ? data.education.flatMap((item) => commaSeparatedItems(item.coursework))
    : [];
  const keywordPool = new Set(
    [...skills, ...technologies, ...coursework].map((item) => item.toLowerCase())
  );
  let keywordScore = 0;
  if (skills.length >= 5) keywordScore += 10;
  else if (skills.length >= 2) keywordScore += 6;
  if (technologies.length > 0 || coursework.length > 0) keywordScore += 5;
  if (keywordPool.size >= 8) keywordScore += 5;
  else if (keywordPool.size >= 4) keywordScore += 3;
  if (skills.length < 5) {
    recommendations.push("List at least five role-relevant skills using terms from the job advert.");
  }
  categories.push(
    category(
      "Skills and keywords",
      keywordScore,
      20,
      keywordScore >= 16
        ? "The resume contains a useful range of searchable skills."
        : "Add more role-specific skills and technologies."
    )
  );

  const includedValues = [
    ...Object.values(data.personal),
    ...(includedSections.education ? data.education.flatMap(Object.values) : []),
    ...(includedSections.experience ? data.experience.flatMap(Object.values) : []),
    ...(includedSections.projects ? data.projects.flatMap(Object.values) : []),
    ...(includedSections.activities ? data.activities.flatMap(Object.values) : []),
    ...(includedSections.additional
      ? Object.entries(data.additional)
          .filter(([key]) => includedAdditional[key as keyof ResumeAdditionalSelection])
          .map(([, value]) => value)
      : []),
  ].filter(filled);
  const resumeWordCount = words(includedValues.join(" ")).length;
  const averageBulletLength =
    achievementBullets.length > 0
      ? achievementBullets.reduce((total, item) => total + words(item).length, 0) /
        achievementBullets.length
      : 0;
  const containsTypedPlaceholder = includedValues.some((value) => /\[[^\]]+\]/.test(value));
  let readabilityScore = 0;
  if (resumeWordCount >= 120 && resumeWordCount <= 800) readabilityScore += 4;
  else if (resumeWordCount >= 60 && resumeWordCount <= 1_000) readabilityScore += 2;
  if (averageBulletLength >= 6 && averageBulletLength <= 35) readabilityScore += 3;
  if (!containsTypedPlaceholder && includedValues.length > 0) readabilityScore += 3;
  if (resumeWordCount < 120) recommendations.push("Add more relevant detail; the resume is still very brief.");
  if (resumeWordCount > 800) recommendations.push("Trim the resume so its most relevant evidence is easier to scan.");
  if (containsTypedPlaceholder) recommendations.push("Replace any bracketed placeholder text before applying.");
  categories.push(
    category(
      "Readability",
      readabilityScore,
      10,
      readabilityScore >= 8
        ? "Content length and bullet style are easy to scan."
        : "Improve content length, bullet clarity or unfinished placeholders."
    )
  );

  const completionChecks = [
    !includedSections.education ||
      data.education.every((item) => !Object.values(item).some(filled) || completedEducation.includes(item)),
    !includedSections.experience ||
      data.experience.every(
        (item) => !Object.values(item).some(filled) || completedExperience.includes(item)
      ),
    !includedSections.projects ||
      data.projects.every((item) => !Object.values(item).some(filled) || completedProjects.includes(item)),
  ];
  const datedEvidence = [
    ...(includedSections.education ? data.education.map((item) => item.graduationYear) : []),
    ...(includedSections.experience ? data.experience.map((item) => item.dates) : []),
    ...(includedSections.projects ? data.projects.map((item) => item.dates) : []),
  ].filter(filled);
  let completionScore = completionChecks.filter(Boolean).length * 2;
  if (datedEvidence.length >= 2) completionScore += 4;
  else if (datedEvidence.length === 1) completionScore += 2;
  if (completionChecks.some((item) => !item)) {
    recommendations.push("Complete or remove partially filled entries.");
  }
  if (datedEvidence.length === 0) {
    recommendations.push("Add dates to education, experience or projects.");
  }
  categories.push(
    category(
      "Completeness",
      completionScore,
      10,
      completionScore >= 8
        ? "Included entries contain the core details needed for parsing."
        : "Finish partial entries and add relevant dates."
    )
  );

  const score = categories.reduce((total, item) => total + item.score, 0);
  const band: AtsScoreResult["band"] =
    score >= 85
      ? "Excellent"
      : score >= 70
        ? "Strong"
        : score >= 50
          ? "Developing"
          : "Incomplete";
  const summary =
    score >= 85
      ? "Your resume is well structured and rich in ATS-readable evidence."
      : score >= 70
        ? "Your resume has a solid ATS foundation with a few useful improvements remaining."
        : score >= 50
          ? "The structure is usable, but stronger evidence and keywords will improve it."
          : "Complete the core fields before relying on this resume for applications.";

  return {
    score,
    band,
    summary,
    categories,
    recommendations: [...new Set(recommendations)].slice(0, 6),
  };
}
