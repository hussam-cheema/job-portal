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

export type ResumeSectionSelection = {
  education: boolean;
  experience: boolean;
  projects: boolean;
  activities: boolean;
  additional: boolean;
};

export type ResumeAdditionalSelection = {
  languages: boolean;
  technicalSkills: boolean;
  volunteerExperience: boolean;
  interests: boolean;
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
  includedSections?: ResumeSectionSelection;
  includedAdditional?: ResumeAdditionalSelection;
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

export function buildResumeAtsText(data: ResumeDocumentData) {
  const includedSections: ResumeSectionSelection = {
    education: true,
    experience: true,
    projects: true,
    activities: true,
    additional: true,
    ...data.includedSections,
  };
  const includedAdditional: ResumeAdditionalSelection = {
    languages: true,
    technicalSkills: true,
    volunteerExperience: true,
    interests: true,
    ...data.includedAdditional,
  };
  const output: string[] = [];
  const add = (...values: string[]) => {
    for (const value of values) {
      const normalized = value.trim();
      if (normalized) output.push(normalized);
    }
  };

  add(data.personal.fullName);
  add([data.personal.address, data.personal.phone, data.personal.email].filter(Boolean).join(" | "));

  if (includedSections.education) {
    add("EDUCATION");
    for (const item of data.education) {
      add(
        item.school,
        item.degree,
        [item.location, item.graduationYear].filter(Boolean).join(" | "),
        item.details,
        item.coursework ? `Relevant coursework: ${item.coursework}` : ""
      );
    }
  }

  if (includedSections.experience) {
    add("EXPERIENCE");
    for (const item of data.experience) {
      add(
        item.jobTitle,
        item.company,
        [item.location, item.dates].filter(Boolean).join(" | ")
      );
      add(...populatedLines(item.achievements, []));
    }
  }

  if (includedSections.projects) {
    add("UNIVERSITY PROJECTS");
    for (const item of data.projects) {
      add(
        item.title,
        item.dates,
        item.description ? `Description: ${item.description}` : "",
        item.role ? `Role: ${item.role}` : "",
        item.technologies ? `Technologies used: ${item.technologies}` : "",
        item.outcome ? `Outcome: ${item.outcome}` : ""
      );
    }
  }

  if (includedSections.activities) {
    add("ACTIVITIES");
    for (const item of data.activities) {
      add(
        item.name,
        item.dates,
        item.description ? `Description: ${item.description}` : "",
        item.skills ? `Skills developed: ${item.skills}` : "",
        item.achievements ? `Achievements: ${item.achievements}` : ""
      );
    }
  }

  if (includedSections.additional && Object.values(includedAdditional).some(Boolean)) {
    add("ADDITIONAL");
    if (includedAdditional.languages) {
      add(data.additional.languages ? `Language skills: ${data.additional.languages}` : "");
    }
    if (includedAdditional.technicalSkills) {
      add(
        data.additional.technicalSkills
          ? `Technical skills: ${data.additional.technicalSkills}`
          : ""
      );
    }
    if (includedAdditional.volunteerExperience) {
      add(
        data.additional.volunteerExperience
          ? `Volunteer experience: ${data.additional.volunteerExperience}`
          : ""
      );
    }
    if (includedAdditional.interests) {
      add(data.additional.interests ? `Interests and hobbies: ${data.additional.interests}` : "");
    }
  }

  return output;
}

export async function createResumeDocx(data: ResumeDocumentData) {
  const {
    AlignmentType,
    BorderStyle,
    Document,
    LevelFormat,
    LineRuleType,
    Packer,
    PageOrientation,
    Paragraph,
    Table,
    TableBorders,
    TableCell,
    TableLayoutType,
    TableRow,
    TextRun,
    WidthType,
  } = await import("docx");

  // Arial is deliberately used for the editable document: it closely matches
  // the Avenir-style web preview and is available in Word/LibreOffice without
  // falling back to a wider serif font that changes pagination.
  const bodyFont = "Arial";
  const headingFont = "Georgia";
  const ink = "171717";
  const mutedInk = "374151";
  const contentWidth = 10_772;
  const leftColumnWidth = 7_560;
  const rightColumnWidth = contentWidth - leftColumnWidth;
  const entrySpacing = 153;
  const noBorder = { style: BorderStyle.NONE, color: "FFFFFF", size: 0 };
  const body: Array<InstanceType<typeof Paragraph> | InstanceType<typeof Table>> = [];
  const includedSections: ResumeSectionSelection = {
    education: true,
    experience: true,
    projects: true,
    activities: true,
    additional: true,
    ...data.includedSections,
  };
  const includedAdditional: ResumeAdditionalSelection = {
    languages: true,
    technicalSkills: true,
    volunteerExperience: true,
    interests: true,
    ...data.includedAdditional,
  };

  const run = (
    text: string,
    options: {
      bold?: boolean;
      italics?: boolean;
      font?: string;
      size?: number;
      color?: string;
      allCaps?: boolean;
    } = {}
  ) =>
    new TextRun({
      text,
      font: options.font || bodyFont,
      size: options.size || 18,
      color: options.color || ink,
      bold: options.bold,
      italics: options.italics,
      allCaps: options.allCaps,
    });

  const paragraph = (
    children: InstanceType<typeof TextRun>[],
    options: {
      after?: number;
      alignment?: (typeof AlignmentType)[keyof typeof AlignmentType];
      keepNext?: boolean;
      size?: number;
    } = {}
  ) =>
    new Paragraph({
      children,
      alignment: options.alignment,
      keepNext: options.keepNext,
      spacing: {
        after: options.after ?? 0,
        line: 314,
        lineRule: LineRuleType.AUTO,
      },
    });

  const centeredBand = (
    children: InstanceType<typeof Paragraph>[],
    centerWidth: number,
    bottomMargin = 0
  ) => {
    const boundedCenter = Math.min(contentWidth, Math.max(1_800, centerWidth));
    const sideWidth = Math.floor((contentWidth - boundedCenter) / 2);
    const finalCenterWidth = contentWidth - sideWidth * 2;
    const blankCell = (width: number) =>
      new TableCell({
        width: { size: width, type: WidthType.DXA },
        margins: { top: 0, bottom: 0, left: 0, right: 0, marginUnitType: WidthType.DXA },
        borders: { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder },
        children: [new Paragraph({ children: [] })],
      });
    return new Table({
      width: { size: contentWidth, type: WidthType.DXA },
      columnWidths: [sideWidth, finalCenterWidth, sideWidth],
      layout: TableLayoutType.FIXED,
      borders: TableBorders.NONE,
      margins: {
        top: 0,
        bottom: bottomMargin,
        left: 0,
        right: 0,
        marginUnitType: WidthType.DXA,
      },
      rows: [
        new TableRow({
          cantSplit: true,
          children: [
            blankCell(sideWidth),
            new TableCell({
              width: { size: finalCenterWidth, type: WidthType.DXA },
              margins: {
                top: 0,
                bottom: bottomMargin,
                left: 0,
                right: 0,
                marginUnitType: WidthType.DXA,
              },
              borders: { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder },
              children,
            }),
            blankCell(sideWidth),
          ],
        }),
      ],
    });
  };

  const sectionHeading = (title: string, first = false) => {
    const rule = { style: BorderStyle.SINGLE, color: "222222", size: 8 };
    return new Table({
      width: { size: contentWidth, type: WidthType.DXA },
      columnWidths: [contentWidth],
      layout: TableLayoutType.FIXED,
      borders: {
        top: noBorder,
        left: noBorder,
        bottom: rule,
        right: noBorder,
        insideHorizontal: noBorder,
        insideVertical: noBorder,
      },
      margins: {
        top: first ? 0 : 198,
        bottom: 125,
        left: 0,
        right: 0,
        marginUnitType: WidthType.DXA,
      },
      rows: [
        new TableRow({
          cantSplit: true,
          children: [
            new TableCell({
              width: { size: contentWidth, type: WidthType.DXA },
              margins: {
                top: first ? 0 : 198,
                bottom: 125,
                left: 0,
                right: 0,
                marginUnitType: WidthType.DXA,
              },
              borders: { top: noBorder, left: noBorder, bottom: rule, right: noBorder },
              children: [
                new Paragraph({
                  children: [
                    run(title, {
                      bold: true,
                      font: headingFont,
                      size: 31,
                    }),
                  ],
                  spacing: { after: 0, line: 276, lineRule: LineRuleType.AUTO },
                  keepNext: true,
                }),
              ],
            }),
          ],
        }),
      ],
    });
  };

  const entryTable = ({
    title,
    subtitle,
    asideTop,
    asideBottom,
  }: {
    title: string;
    subtitle?: string;
    asideTop: string;
    asideBottom?: string;
  }) => {
    const leftParagraphs = [
      new Paragraph({
        children: [run(title, { bold: true, size: 21 })],
        spacing: { after: 0, line: 312, lineRule: LineRuleType.AUTO },
        keepNext: Boolean(subtitle),
      }),
    ];
    if (subtitle) {
      leftParagraphs.push(
        new Paragraph({
          children: [run(subtitle)],
          spacing: { after: 0, line: 314, lineRule: LineRuleType.AUTO },
        })
      );
    }

    const rightParagraphs = [
      new Paragraph({
        alignment: AlignmentType.RIGHT,
        children: [run(asideTop, { color: mutedInk })],
        spacing: { after: 0, line: 314, lineRule: LineRuleType.AUTO },
        keepNext: Boolean(asideBottom),
      }),
    ];
    if (asideBottom) {
      rightParagraphs.push(
        new Paragraph({
          alignment: AlignmentType.RIGHT,
          children: [run(asideBottom, { color: mutedInk })],
          spacing: { after: 0, line: 314, lineRule: LineRuleType.AUTO },
        })
      );
    }

    return new Table({
      width: { size: contentWidth, type: WidthType.DXA },
      columnWidths: [leftColumnWidth, rightColumnWidth],
      layout: TableLayoutType.FIXED,
      borders: TableBorders.NONE,
      margins: { top: 0, bottom: 0, left: 0, right: 0, marginUnitType: WidthType.DXA },
      rows: [
        new TableRow({
          cantSplit: true,
          children: [
            new TableCell({
              width: { size: leftColumnWidth, type: WidthType.DXA },
              margins: {
                top: 0,
                bottom: 0,
                left: 0,
                right: 227,
                marginUnitType: WidthType.DXA,
              },
              children: leftParagraphs,
            }),
            new TableCell({
              width: { size: rightColumnWidth, type: WidthType.DXA },
              margins: {
                top: 0,
                bottom: 0,
                left: 227,
                right: 0,
                marginUnitType: WidthType.DXA,
              },
              children: rightParagraphs,
            }),
          ],
        }),
      ],
    });
  };

  const bullet = (text: string, after = 0) =>
    new Paragraph({
      children: [run(text)],
      numbering: { reference: "resume-bullets", level: 0 },
      spacing: { after, line: 314, lineRule: LineRuleType.AUTO },
    });

  const headerName = (data.personal.fullName || "YOUR NAME").toUpperCase();
  const headerContact = [
    data.personal.address || "Address",
    data.personal.phone || "Phone",
    data.personal.email || "Email",
  ].join(" • ");
  body.push(
    centeredBand(
      [
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [
            run(headerName, {
              font: headingFont,
              size: 52,
              bold: true,
              allCaps: true,
              color: ink,
            }),
          ],
          spacing: { after: 0, line: 259, lineRule: LineRuleType.AUTO },
        }),
      ],
      Math.max(3_600, headerName.length * 420),
      85
    ),
    centeredBand(
      [
        new Paragraph({
          alignment: AlignmentType.CENTER,
          children: [run(headerContact, { size: 21, color: ink })],
          spacing: { after: 0, line: 314, lineRule: LineRuleType.AUTO },
        }),
      ],
      Math.max(5_400, headerContact.length * 130),
      215
    )
  );

  let firstSection = true;
  const addSectionHeading = (title: string) => {
    body.push(sectionHeading(title, firstSection));
    firstSection = false;
  };

  if (includedSections.education) {
    addSectionHeading("Education");
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
        entryTable({
          title: school,
          subtitle: degree,
          asideTop: item.location || (index === 0 ? "[Location]" : "[City, State]"),
          asideBottom: item.graduationYear || "[Year of Graduation]",
        })
      );
      if (index === 0) {
        body.push(
          paragraph([run(item.details || "GPA: [Your GPA, if it is above 3.0]")]),
          paragraph(
            [
              run("Relevant coursework: ", { bold: true }),
              run(item.coursework || "[List any specific courses relevant to the job]"),
            ],
            { after: entrySpacing }
          )
        );
      } else {
        body.push(
          paragraph(
            [
              run(
                item.details ||
                  "If you have pursued any specialized coursework or achieved notable academic accomplishments during high school."
              ),
            ],
            { after: entrySpacing }
          )
        );
      }
    });
  }

  if (includedSections.experience) {
    addSectionHeading("Experience");
    data.experience.forEach((item) => {
      const achievements = populatedLines(item.achievements, [
        "Spearheaded [specific project or initiative], resulting in [quantifiable achievement].",
        "Collaborated with cross-functional teams to [accomplishment or task].",
        "Implemented [strategy or process improvement], leading to [positive outcome].",
        "Managed [specific responsibility or duty], ensuring [desired outcome].",
      ]);
      body.push(
        entryTable({
          title: item.jobTitle || "[JOB TITLE]",
          subtitle: item.company || "[Company Name]",
          asideTop: item.location || "[Location]",
          asideBottom: item.dates || "[Dates of Employment]",
        }),
        ...achievements.map((achievement, index) =>
          bullet(achievement, index === achievements.length - 1 ? entrySpacing : 0)
        )
      );
    });
  }

  if (includedSections.projects) {
    addSectionHeading("University Projects");
    data.projects.forEach((item) => {
      const projectBullets = [
        `Description: ${item.description || "Brief overview of the project and its objectives."}`,
        `Role: ${item.role || "Your specific role or contribution to the project."}`,
        `Technologies Used: ${
          item.technologies || "Any tools, software, or programming languages utilized."
        }`,
        `Outcome: ${item.outcome || "Results achieved or lessons learned from the project."}`,
      ];
      body.push(
        entryTable({
          title: item.title || "[PROJECT TITLE]",
          asideTop: item.dates || "[Dates]",
        }),
        ...projectBullets.map((text, index) =>
          bullet(text, index === projectBullets.length - 1 ? entrySpacing : 0)
        )
      );
    });
  }

  if (includedSections.activities) {
    addSectionHeading("Activities");
    data.activities.forEach((item) => {
      const activityBullets = [
        `Description: ${item.description || "Brief overview of the activity and your role."}`,
        `Skills Developed: ${
          item.skills || "Any relevant skills or qualities honed through participation."
        }`,
        `Achievements: ${
          item.achievements || "Any notable achievements or leadership roles within the activity."
        }`,
      ];
      body.push(
        entryTable({
          title: item.name || "[ACTIVITY NAME]",
          asideTop: item.dates || "[Dates]",
        }),
        ...activityBullets.map((text, index) =>
          bullet(text, index === activityBullets.length - 1 ? entrySpacing : 0)
        )
      );
    });
  }

  const additionalLine = (label: string, value: string, after = 0) =>
    paragraph([run(`${label}:`, { bold: true }), run(` ${value}`)], { after });

  if (includedSections.additional && Object.values(includedAdditional).some(Boolean)) {
    addSectionHeading("Additional");
    if (includedAdditional.languages) {
      body.push(
        additionalLine(
          "Language Skills",
          data.additional.languages || "[List any languages you speak fluently or proficiently.]"
        )
      );
    }
    if (includedAdditional.technicalSkills) {
      body.push(
        additionalLine(
          "Technical Skills",
          data.additional.technicalSkills ||
            "[List any relevant technical skills or software proficiencies.]"
        )
      );
    }
    if (includedAdditional.volunteerExperience) {
      body.push(
        additionalLine(
          "Volunteer Experience",
          data.additional.volunteerExperience ||
            "[Briefly mention any volunteer work you have done, highlighting skills or experiences gained.]"
        )
      );
    }
    if (includedAdditional.interests) {
      body.push(
        additionalLine(
          "Interests/Hobbies",
          data.additional.interests ||
            "[Include any interests or hobbies that demonstrate relevant skills or qualities, or provide insight into your personality.]"
        )
      );
    }
  }

  const resume = new Document({
    creator: "Pakistan Jobs Market",
    title: `${data.personal.fullName || "Professional"} Resume`,
    description: "Editable resume created with Pakistan Jobs Market Resume Builder",
    styles: {
      default: {
        document: {
          run: { font: bodyFont, size: 18, color: ink },
          paragraph: {
            spacing: { line: 314, lineRule: LineRuleType.AUTO, after: 0 },
          },
        },
      },
    },
    numbering: {
      config: [
        {
          reference: "resume-bullets",
          levels: [
            {
              level: 0,
              format: LevelFormat.BULLET,
              text: "•",
              alignment: AlignmentType.LEFT,
              style: {
                run: { font: bodyFont, size: 18, color: ink },
                paragraph: {
                  indent: { left: 420, hanging: 160 },
                  spacing: { line: 314, lineRule: LineRuleType.AUTO, after: 0 },
                },
              },
            },
          ],
        },
      ],
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
            margin: { top: 737, right: 567, bottom: 624, left: 567 },
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
    LineRuleType,
    Packer,
    PageOrientation,
    Paragraph,
    Table,
    TableBorders,
    TableCell,
    TableLayoutType,
    TableRow,
    TextRun,
    WidthType,
  } = await import("docx");

  const bodyFont = "Arial";
  const headingFont = "Georgia";
  const ink = "090909";
  const bodyIndent = 567;
  const contentWidth = 10_998;
  const bodyWidth = contentWidth - bodyIndent * 2;
  const noBorder = { style: BorderStyle.NONE, color: "FFFFFF", size: 0 };
  const bodyRun = (
    text: string,
    options: { bold?: boolean; font?: string; size?: number; color?: string } = {}
  ) =>
    new TextRun({
      text,
      font: options.font || bodyFont,
      size: options.size || 18,
      color: options.color || "000000",
      bold: options.bold,
    });
  const bodyParagraph = (
    text: string,
    options: {
      alignment?: (typeof AlignmentType)[keyof typeof AlignmentType];
      keepNext?: boolean;
      bold?: boolean;
      font?: string;
      size?: number;
    } = {}
  ) =>
    new Paragraph({
      alignment: options.alignment,
      keepNext: options.keepNext,
      children: [
        bodyRun(text, {
          bold: options.bold,
          font: options.font,
          size: options.size,
        }),
      ],
      spacing: {
        before: 0,
        after: 0,
        line: 355,
        lineRule: LineRuleType.AUTO,
      },
    });

  const spacer = (height: number) =>
    new Paragraph({
      children: [bodyRun("\u00a0", { size: 2, color: "FFFFFF" })],
      spacing: {
        before: 0,
        after: 0,
        line: height,
        lineRule: LineRuleType.EXACT,
      },
    });

  const blankCell = (width: number) =>
    new TableCell({
      width: { size: width, type: WidthType.DXA },
      margins: { top: 0, bottom: 0, left: 0, right: 0, marginUnitType: WidthType.DXA },
      borders: { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder },
      children: [new Paragraph({ children: [] })],
    });

  const centeredBand = (
    paragraphs: InstanceType<typeof Paragraph>[],
    centerWidth: number,
    bottomMargin = 0
  ) => {
    const boundedCenter = Math.min(contentWidth, Math.max(1_800, centerWidth));
    const sideWidth = Math.floor((contentWidth - boundedCenter) / 2);
    const finalCenterWidth = contentWidth - sideWidth * 2;
    return new Table({
      width: { size: contentWidth, type: WidthType.DXA },
      columnWidths: [sideWidth, finalCenterWidth, sideWidth],
      layout: TableLayoutType.FIXED,
      borders: TableBorders.NONE,
      margins: { top: 0, bottom: 0, left: 0, right: 0, marginUnitType: WidthType.DXA },
      rows: [
        new TableRow({
          cantSplit: true,
          children: [
            blankCell(sideWidth),
            new TableCell({
              width: { size: finalCenterWidth, type: WidthType.DXA },
              margins: {
                top: 0,
                bottom: bottomMargin,
                left: 0,
                right: 0,
                marginUnitType: WidthType.DXA,
              },
              borders: { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder },
              children: paragraphs,
            }),
            blankCell(sideWidth),
          ],
        }),
      ],
    });
  };

  const recipientLines = [
    data.contactName || "(Contact Person’s Name)",
    data.companyName || "(Company Name)",
    ...populatedLines(data.companyAddress, ["(Company Address)"]),
  ];
  const title = (data.documentTitle || "GOOGLE COVER LETTER").toUpperCase();
  const subtitle = data.subtitle || "by CV Genius";
  const phone = data.phone || "07123 456 789";
  const email = data.email || "your.email@gmail.com";
  const address = data.address || "26 Springfield Road, London, N39 6CU";
  const contactText = `${phone}   •   ${email}   •   ${address}`;

  const contactLine = new Table({
    width: { size: contentWidth, type: WidthType.DXA },
    columnWidths: [contentWidth],
    layout: TableLayoutType.FIXED,
    margins: { top: 0, bottom: 0, left: 0, right: 0, marginUnitType: WidthType.DXA },
    borders: {
      top: { style: BorderStyle.SINGLE, color: "9B9B9B", size: 6 },
      bottom: { style: BorderStyle.SINGLE, color: "9B9B9B", size: 6 },
      left: noBorder,
      right: noBorder,
      insideHorizontal: noBorder,
      insideVertical: noBorder,
    },
    rows: [
      new TableRow({
        cantSplit: true,
        children: [
          new TableCell({
            width: { size: contentWidth, type: WidthType.DXA },
            margins: {
              top: 160,
              bottom: 160,
              left: 0,
              right: 0,
              marginUnitType: WidthType.DXA,
            },
            borders: {
              top: { style: BorderStyle.SINGLE, color: "9B9B9B", size: 6 },
              bottom: { style: BorderStyle.SINGLE, color: "9B9B9B", size: 6 },
              left: noBorder,
              right: noBorder,
            },
            children: [
              centeredBand(
                [
                  new Paragraph({
                    alignment: AlignmentType.CENTER,
                    children: [
                      bodyRun(phone, { font: headingFont, size: 14, color: ink }),
                      bodyRun("   •   ", {
                        font: headingFont,
                        size: 16,
                        color: "D20B20",
                      }),
                      bodyRun(email, { font: headingFont, size: 14, color: ink }),
                      bodyRun("   •   ", {
                        font: headingFont,
                        size: 16,
                        color: "D20B20",
                      }),
                      bodyRun(address, { font: headingFont, size: 14, color: ink }),
                    ],
                    spacing: { after: 0, line: 240, lineRule: LineRuleType.AUTO },
                  }),
                ],
                Math.max(4_200, contactText.length * 75)
              ),
            ],
          }),
        ],
      }),
    ],
  });

  const dateWidth = 2_100;
  const dateRow = new Table({
    width: { size: bodyWidth, type: WidthType.DXA },
    columnWidths: [bodyWidth - dateWidth, dateWidth],
    layout: TableLayoutType.FIXED,
    borders: TableBorders.NONE,
    margins: { top: 0, bottom: 0, left: 0, right: 0, marginUnitType: WidthType.DXA },
    rows: [
      new TableRow({
        cantSplit: true,
        children: [
          blankCell(bodyWidth - dateWidth),
          new TableCell({
            width: { size: dateWidth, type: WidthType.DXA },
            margins: { top: 0, bottom: 0, left: 0, right: 0, marginUnitType: WidthType.DXA },
            borders: { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder },
            children: [
              bodyParagraph(formattedDate, {
                alignment: AlignmentType.RIGHT,
              }),
            ],
          }),
        ],
      }),
    ],
  });

  const bodyChildren: Array<InstanceType<typeof Paragraph> | InstanceType<typeof Table>> = [
    spacer(340),
    dateRow,
    spacer(283),
    ...recipientLines.map((line, index) =>
      bodyParagraph(line, { keepNext: index < recipientLines.length - 1 })
    ),
    spacer(397),
    bodyParagraph(
      `Dear ${data.contactSurname ? `${data.contactSurname},` : "(Contact Person’s Surname),"}`
    ),
    spacer(283),
    bodyParagraph(
      data.openingParagraph ||
        "I’m writing to express my interest in the advertised position. With relevant experience and a strong record of delivering results, I am eager to bring my expertise to your organisation."
    ),
    spacer(283),
    bodyParagraph(
      data.bodyParagraphOne ||
        "In my current role, I have successfully led important projects, improved processes, and collaborated with cross-functional teams. My commitment to quality and continuous improvement has enabled me to create measurable impact."
    ),
    spacer(283),
    bodyParagraph(
      data.bodyParagraphTwo ||
        "Throughout my career, I have demonstrated sound judgement, clear communication, and the ability to solve complex challenges. My experience and technical proficiency would allow me to contribute from the outset."
    ),
    spacer(283),
    bodyParagraph(
      data.closingParagraph ||
        "I’m excited by the opportunity to make a meaningful contribution. I welcome the chance to discuss how my skills and experience align with the needs of your team."
    ),
    spacer(340),
    bodyParagraph(data.signOff || "Yours sincerely,"),
    spacer(57),
    bodyParagraph(data.fullName || "(YOUR NAME)", {
      bold: true,
      font: headingFont,
      size: 25,
    }),
  ];

  const bodyTable = new Table({
    width: { size: contentWidth, type: WidthType.DXA },
    columnWidths: [bodyIndent, bodyWidth, bodyIndent],
    layout: TableLayoutType.FIXED,
    borders: TableBorders.NONE,
    margins: { top: 0, bottom: 0, left: 0, right: 0, marginUnitType: WidthType.DXA },
    rows: [
      new TableRow({
        children: [
          blankCell(bodyIndent),
          new TableCell({
            width: { size: bodyWidth, type: WidthType.DXA },
            margins: { top: 0, bottom: 0, left: 0, right: 0, marginUnitType: WidthType.DXA },
            borders: { top: noBorder, bottom: noBorder, left: noBorder, right: noBorder },
            children: bodyChildren,
          }),
          blankCell(bodyIndent),
        ],
      }),
    ],
  });

  const letter = new Document({
    creator: "Pakistan Jobs Market",
    title: `${data.fullName || "Professional"} Cover Letter`,
    description: "Editable cover letter created with Pakistan Jobs Market Cover Letter Builder",
    styles: {
      default: {
        document: {
          run: { font: bodyFont, size: 18, color: ink },
          paragraph: {
            spacing: { line: 355, lineRule: LineRuleType.AUTO, after: 0 },
          },
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
            margin: { top: 680, right: 454, bottom: 907, left: 454 },
          },
        },
        children: [
          centeredBand(
            [
              new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [bodyRun(title, { font: headingFont, size: 34, color: ink })],
                spacing: { after: 0, line: 264, lineRule: LineRuleType.AUTO },
              }),
            ],
            Math.max(3_600, title.length * 200),
            45
          ),
          centeredBand(
            [
              new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [bodyRun(subtitle, { font: headingFont, size: 16, color: ink })],
                spacing: { after: 0, line: 264, lineRule: LineRuleType.AUTO },
              }),
            ],
            Math.max(1_800, subtitle.length * 130),
            198
          ),
          contactLine,
          bodyTable,
        ],
      },
    ],
  });

  return Packer.toBlob(letter);
}
