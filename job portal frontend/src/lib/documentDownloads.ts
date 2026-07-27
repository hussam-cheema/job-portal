type ResumeEducation = {
  school: string;
  degree: string;
  details: string;
  coursework: string;
  location: string;
  graduationYear: string;
};

type ResumeExperience = {
  jobTitle: string;
  company: string;
  location: string;
  dates: string;
  achievements: string;
};

type ResumeProject = {
  title: string;
  dates: string;
  description: string;
  role: string;
  technologies: string;
  outcome: string;
};

type ResumeActivity = {
  name: string;
  dates: string;
  description: string;
  skills: string;
  achievements: string;
};

export type ResumeDocumentData = {
  personal: {
    fullName: string;
    address: string;
    phone: string;
    email: string;
  };
  education: ResumeEducation[];
  experience: ResumeExperience[];
  projects: ResumeProject[];
  activities: ResumeActivity[];
  additional: {
    languages: string;
    technicalSkills: string;
    volunteerExperience: string;
    interests: string;
  };
};

export type CoverLetterDocumentData = {
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

function populatedLines(value: string, fallback: string[]) {
  const items = value
    .split("\n")
    .map((item) => item.trim())
    .filter(Boolean);
  return items.length ? items : fallback;
}

export function safeDocumentName(value: string, fallback = "professional") {
  return (
    value
      .trim()
      .toLowerCase()
      .replace(/[^a-z0-9]+/g, "-")
      .replace(/^-|-$/g, "") || fallback
  );
}

export function saveDocumentBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  link.style.display = "none";
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 1_000);
}

export async function createResumeDocx(data: ResumeDocumentData) {
  const {
    AlignmentType,
    BorderStyle,
    Document,
    Packer,
    PageOrientation,
    Paragraph,
    TextRun,
  } = await import("docx");

  const body: InstanceType<typeof Paragraph>[] = [];
  const sectionHeading = (title: string) =>
    new Paragraph({
      children: [new TextRun({ text: title.toUpperCase(), bold: true, size: 22 })],
      spacing: { before: 220, after: 90 },
      border: {
        bottom: {
          style: BorderStyle.SINGLE,
          color: "111827",
          size: 8,
          space: 3,
        },
      },
      keepNext: true,
    });
  const detailLine = (
    primary: string,
    secondary = "",
    options: { bold?: boolean; italicSecondary?: boolean } = {}
  ) =>
    new Paragraph({
      children: [
        new TextRun({ text: primary, bold: options.bold }),
        ...(secondary
          ? [
              new TextRun({
                text: ` — ${secondary}`,
                italics: options.italicSecondary,
                color: "374151",
              }),
            ]
          : []),
      ],
      spacing: { after: 45 },
    });
  const bullet = (text: string) =>
    new Paragraph({
      children: [new TextRun(text)],
      bullet: { level: 0 },
      spacing: { after: 35 },
    });

  body.push(
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [
        new TextRun({
          text: data.personal.fullName || "YOUR NAME",
          bold: true,
          allCaps: true,
          size: 34,
          color: "111827",
        }),
      ],
      spacing: { after: 75 },
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [
        new TextRun({
          text: [
            data.personal.address || "Address",
            data.personal.phone || "Phone",
            data.personal.email || "Email",
          ].join(" • "),
          size: 18,
          color: "374151",
        }),
      ],
      spacing: { after: 130 },
    }),
    sectionHeading("Education")
  );

  data.education.forEach((item, index) => {
    const school =
      item.school ||
      (index === 0 ? "[UNIVERSITY/COLLEGE NAME]" : "[YOUR HIGH SCHOOL NAME]");
    const degree =
      item.degree ||
      (index === 0
        ? "[Bachelor of Science in Major]"
        : "Include any honours, awards, or relevant extracurricular activities if applicable.");
    body.push(
      detailLine(school, item.location || (index === 0 ? "[Location]" : "[City, State]"), {
        bold: true,
      }),
      detailLine(degree, item.graduationYear || "[Year of Graduation]", {
        italicSecondary: true,
      })
    );
    if (index === 0) {
      body.push(
        detailLine(item.details || "GPA: [Your GPA, if it is above 3.0]"),
        detailLine(
          `Relevant coursework: ${
            item.coursework || "[List any specific courses relevant to the job]"
          }`
        )
      );
    } else {
      body.push(
        detailLine(
          item.details ||
            "If you have pursued any specialized coursework or achieved notable academic accomplishments during high school."
        )
      );
    }
  });

  body.push(sectionHeading("Experience"));
  data.experience.forEach((item) => {
    body.push(
      detailLine(item.jobTitle || "[JOB TITLE]", item.location || "[Location]", { bold: true }),
      detailLine(item.company || "[Company Name]", item.dates || "[Dates of Employment]", {
        italicSecondary: true,
      }),
      ...populatedLines(item.achievements, [
        "Spearheaded [specific project or initiative], resulting in [quantifiable achievement].",
        "Collaborated with cross-functional teams to [accomplishment or task].",
        "Implemented [strategy or process improvement], leading to [positive outcome].",
        "Managed [specific responsibility or duty], ensuring [desired outcome].",
      ]).map(bullet)
    );
  });

  body.push(sectionHeading("University Projects"));
  data.projects.forEach((item) => {
    body.push(
      detailLine(item.title || "[PROJECT TITLE]", item.dates || "[Dates]", { bold: true }),
      bullet(
        `Description: ${item.description || "Brief overview of the project and its objectives."}`
      ),
      bullet(`Role: ${item.role || "Your specific role or contribution to the project."}`),
      bullet(
        `Technologies Used: ${
          item.technologies || "Any tools, software, or programming languages utilized."
        }`
      ),
      bullet(
        `Outcome: ${item.outcome || "Results achieved or lessons learned from the project."}`
      )
    );
  });

  body.push(sectionHeading("Activities"));
  data.activities.forEach((item) => {
    body.push(
      detailLine(item.name || "[ACTIVITY NAME]", item.dates || "[Dates]", { bold: true }),
      bullet(`Description: ${item.description || "Brief overview of the activity and your role."}`),
      bullet(
        `Skills Developed: ${
          item.skills || "Any relevant skills or qualities honed through participation."
        }`
      ),
      bullet(
        `Achievements: ${
          item.achievements || "Any notable achievements or leadership roles within the activity."
        }`
      )
    );
  });

  body.push(
    sectionHeading("Additional"),
    detailLine(
      `Language Skills: ${
        data.additional.languages || "[List any languages you speak fluently or proficiently.]"
      }`
    ),
    detailLine(
      `Technical Skills: ${
        data.additional.technicalSkills ||
        "[List any relevant technical skills or software proficiencies.]"
      }`
    ),
    detailLine(
      `Volunteer Experience: ${
        data.additional.volunteerExperience ||
        "[Briefly mention any volunteer work you have done, highlighting skills or experiences gained.]"
      }`
    ),
    detailLine(
      `Interests/Hobbies: ${
        data.additional.interests ||
        "[Include any interests or hobbies that demonstrate relevant skills or qualities, or provide insight into your personality.]"
      }`
    )
  );

  const resume = new Document({
    creator: "Pakistan Jobs Market",
    title: `${data.personal.fullName || "Professional"} Resume`,
    description: "Editable resume created with Pakistan Jobs Market Resume Builder",
    styles: {
      default: {
        document: {
          run: { font: "Arial", size: 20, color: "111827" },
          paragraph: { spacing: { line: 260, after: 40 } },
        },
      },
    },
    sections: [
      {
        properties: {
          page: {
            size: {
              width: 11_906,
              height: 16_838,
              orientation: PageOrientation.PORTRAIT,
            },
            margin: { top: 850, right: 950, bottom: 850, left: 950 },
          },
        },
        children: body,
      },
    ],
  });

  return Packer.toBlob(resume);
}

export async function createCoverLetterDocx(
  data: CoverLetterDocumentData,
  formattedDate: string
) {
  const {
    AlignmentType,
    BorderStyle,
    Document,
    Packer,
    PageOrientation,
    Paragraph,
    TextRun,
  } = await import("docx");

  const paragraph = (text: string, after = 220) =>
    new Paragraph({
      children: [new TextRun(text)],
      spacing: { after, line: 300 },
    });
  const recipientLines = [
    data.contactName || "(Contact Person’s Name)",
    data.companyName || "(Company Name)",
    ...populatedLines(data.companyAddress, ["(Company Address)"]),
  ];

  const letter = new Document({
    creator: "Pakistan Jobs Market",
    title: `${data.fullName || "Professional"} Cover Letter`,
    description: "Editable cover letter created with Pakistan Jobs Market Cover Letter Builder",
    styles: {
      default: {
        document: {
          run: { font: "Arial", size: 22, color: "000000" },
          paragraph: { spacing: { line: 300 } },
        },
      },
    },
    sections: [
      {
        properties: {
          page: {
            size: {
              width: 11_906,
              height: 16_838,
              orientation: PageOrientation.PORTRAIT,
            },
            margin: { top: 850, right: 950, bottom: 850, left: 950 },
          },
        },
        children: [
          new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [
              new TextRun({
                text: (data.documentTitle || "GOOGLE COVER LETTER").toUpperCase(),
                font: "Times New Roman",
                size: 36,
                bold: true,
                color: "000000",
              }),
            ],
            spacing: { after: 45 },
          }),
          new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [
              new TextRun({
                text: data.subtitle || "by CV Genius",
                font: "Times New Roman",
                size: 20,
                color: "000000",
              }),
            ],
            spacing: { after: 130 },
            border: {
              bottom: {
                style: BorderStyle.SINGLE,
                color: "B7B7B7",
                size: 6,
                space: 10,
              },
            },
          }),
          new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [
              new TextRun({
                text: [
                  data.phone || "07123 456 789",
                  data.email || "your.email@gmail.com",
                  data.address || "26 Springfield Road, London, N39 6CU",
                ].join("  •  "),
                size: 18,
                color: "000000",
              }),
            ],
            spacing: { after: 360 },
          }),
          new Paragraph({
            alignment: AlignmentType.RIGHT,
            children: [new TextRun(formattedDate)],
            spacing: { after: 360 },
          }),
          ...recipientLines.map((line) => paragraph(line, 10)),
          new Paragraph({ spacing: { after: 260 } }),
          paragraph(
            `Dear ${
              data.contactSurname ? `${data.contactSurname},` : "(Contact Person’s Surname),"
            }`,
            260
          ),
          paragraph(
            data.openingParagraph ||
              "I’m writing to express my interest in the advertised position. With relevant experience and a strong record of delivering results, I am eager to bring my expertise to your organisation."
          ),
          paragraph(
            data.bodyParagraphOne ||
              "In my current role, I have successfully led important projects, improved processes, and collaborated with cross-functional teams. My commitment to quality and continuous improvement has enabled me to create measurable impact."
          ),
          paragraph(
            data.bodyParagraphTwo ||
              "Throughout my career, I have demonstrated sound judgement, clear communication, and the ability to solve complex challenges. My experience and technical proficiency would allow me to contribute from the outset."
          ),
          paragraph(
            data.closingParagraph ||
              "I’m excited by the opportunity to make a meaningful contribution. I welcome the chance to discuss how my skills and experience align with the needs of your team.",
            260
          ),
          paragraph(data.signOff || "Yours sincerely,", 80),
          new Paragraph({
            children: [
              new TextRun({
                text: data.fullName || "(YOUR NAME)",
                bold: true,
                color: "000000",
              }),
            ],
          }),
        ],
      },
    ],
  });

  return Packer.toBlob(letter);
}
