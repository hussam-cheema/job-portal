import type { JobSummary } from "@/lib/types";
import { decodeHtmlEntities } from "@/lib/format";
import { normalizeRichTextEntities } from "@/lib/richText";

type JsonObject = Record<string, unknown>;

const EMPLOYMENT_TYPE_ALIASES: Record<string, string> = {
  "full time": "FULL_TIME",
  full_time: "FULL_TIME",
  "part time": "PART_TIME",
  part_time: "PART_TIME",
  contract: "CONTRACTOR",
  contractor: "CONTRACTOR",
  temporary: "TEMPORARY",
  internship: "INTERN",
  intern: "INTERN",
  volunteer: "VOLUNTEER",
  "per diem": "PER_DIEM",
  per_diem: "PER_DIEM",
  other: "OTHER",
};

function cleanValues(values: Array<string | null | undefined>): string[] {
  return Array.from(
    new Set(values.map((value) => value?.trim()).filter((value): value is string => Boolean(value))),
  );
}

function employmentType(value: string | null | undefined): string | undefined {
  if (!value) return undefined;
  return EMPLOYMENT_TYPE_ALIASES[value.trim().toLowerCase()];
}

function jobLocations(job: JobSummary): JsonObject[] {
  const cities = cleanValues(job.cities || []);
  const provinces = cleanValues(job.provinces || []);

  if (
    job.nationwide ||
    cities.some((city) => city.toLowerCase() === "pakistan") ||
    (!cities.length && !provinces.length)
  ) {
    return [
      {
        "@type": "Place",
        address: { "@type": "PostalAddress", addressCountry: "PK" },
      },
    ];
  }

  if (cities.length) {
    const region = provinces.length === 1 ? provinces[0] : undefined;
    return cities.map((city) => ({
      "@type": "Place",
      address: {
        "@type": "PostalAddress",
        addressLocality: city,
        ...(region ? { addressRegion: region } : {}),
        addressCountry: "PK",
      },
    }));
  }

  return provinces.map((province) => ({
    "@type": "Place",
    address: {
      "@type": "PostalAddress",
      addressRegion: province,
      addressCountry: "PK",
    },
  }));
}

/**
 * Build truthful Google JobPosting JSON-LD.
 *
 * Unknown optional facts are omitted instead of being emitted as null, empty,
 * or guessed values. In particular, the free-text salary field is not suitable
 * for baseSalary because Google requires an employer-provided amount and pay
 * period, and government/private is not an employmentType.
 */
export function buildJobPostingStructuredData(
  job: JobSummary,
  canonicalUrl: string,
): JsonObject {
  const published = job.published_date || job.created_at;
  const deadline = job.deadline_date || job.application_deadline;
  const normalizedEmploymentType = employmentType(job.employment_type);
  const skills = cleanValues(job.skills || []);
  const industry = job.category?.trim() || cleanValues(job.tags || [])[0];

  return {
    "@context": "https://schema.org",
    "@type": "JobPosting",
    title: decodeHtmlEntities(job.title),
    description: job.description?.trim()
      ? normalizeRichTextEntities(job.description.trim())
      : decodeHtmlEntities(job.title),
    ...(published ? { datePosted: published } : {}),
    ...(deadline ? { validThrough: deadline } : {}),
    ...(normalizedEmploymentType ? { employmentType: normalizedEmploymentType } : {}),
    ...(industry ? { industry } : {}),
    ...(skills.length ? { skills: skills.join(", ") } : {}),
    ...(job.education_required?.trim()
      ? { educationRequirements: job.education_required.trim() }
      : {}),
    ...(job.experience_required?.trim()
      ? { experienceRequirements: job.experience_required.trim() }
      : {}),
    hiringOrganization: {
      "@type": "Organization",
      name: job.company?.trim() || job.source?.trim() || "Pakistan Jobs Market",
    },
    jobLocation: jobLocations(job),
    ...(job.id
      ? {
          identifier: {
            "@type": "PropertyValue",
            name: job.company?.trim() || job.source?.trim() || "Pakistan Jobs Market",
            value: job.id,
          },
        }
      : {}),
    url: canonicalUrl,
  };
}
