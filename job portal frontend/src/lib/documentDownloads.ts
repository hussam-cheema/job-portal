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

  const sectionHeading = (title: string, first = false) =>
    new Paragraph({
      children: [
        run(title, {
          bold: true,
          font: headingFont,
          size: 31,
        }),
      ],
      spacing: {
        before: first ? 0 : 198,
        after: 125,
        line: 276,
        lineRule: LineRuleType.AUTO,
      },
      border: {
        bottom: {
          style: BorderStyle.SINGLE,
          color: "222222",
          size: 8,
          space: 6,
        },
      },
      keepNext: true,
    });

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

  body.push(
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [
        run(data.personal.fullName || "YOUR NAME", {
          font: headingFont,
          size: 52,
          bold: true,
          allCaps: true,
          color: ink,
        }),
      ],
      spacing: { after: 85, line: 259, lineRule: LineRuleType.AUTO },
    }),
    new Paragraph({
      alignment: AlignmentType.CENTER,
      children: [
        run(
          [
            data.personal.address || "Address",
            data.personal.phone || "Phone",
            data.personal.email || "Email",
          ].join(" • "),
          { size: 21, color: ink }
        ),
      ],
      spacing: { after: 215, line: 314, lineRule: LineRuleType.AUTO },
    })
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
  const noBorder = { style: BorderStyle.NONE, color: "FFFFFF", size: 0 };
  const bodyRun = (text: string, options: { bold?: boolean; font?: string; size?: number } = {}) =>
    new TextRun({
      text,
      font: options.font || bodyFont,
      size: options.size || 18,
      color: "000000",
      bold: options.bold,
    });
  const bodyParagraph = (
    text: string,
    options: {
      before?: number;
      after?: number;
      alignment?: (typeof AlignmentType)[keyof typeof AlignmentType];
      indent?: boolean;
      keepNext?: boolean;
    } = {}
  ) =>
    new Paragraph({
      alignment: options.alignment,
      keepNext: options.keepNext,
      indent:
        options.indent === false
          ? undefined
          : {
              left: bodyIndent,
              right: bodyIndent,
            },
      children: [bodyRun(text)],
      spacing: {
        before: options.before ?? 0,
        after: options.after ?? 283,
        line: 355,
        lineRule: LineRuleType.AUTO,
      },
    });

  const recipientLines = [
    data.contactName || "(Contact Person’s Name)",
    data.companyName || "(Company Name)",
    ...populatedLines(data.companyAddress, ["(Company Address)"]),
  ];

  const contactLine = new Table({
    width: { size: contentWidth, type: WidthType.DXA },
    columnWidths: [contentWidth],
    layout: TableLayoutType.FIXED,
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
              new Paragraph({
                alignment: AlignmentType.CENTER,
                children: [
                  new TextRun({
                    text: data.phone || "07123 456 789",
                    font: headingFont,
                    size: 14,
                    color: ink,
                  }),
                  new TextRun({
                    text: "   •   ",
                    font: headingFont,
                    size: 16,
                    color: "D20B20",
                  }),
                  new TextRun({
                    text: data.email || "your.email@gmail.com",
                    font: headingFont,
                    size: 14,
                    color: ink,
                  }),
                  new TextRun({
                    text: "   •   ",
                    font: headingFont,
                    size: 16,
                    color: "D20B20",
                  }),
                  new TextRun({
                    text: data.address || "26 Springfield Road, London, N39 6CU",
                    font: headingFont,
                    size: 14,
                    color: ink,
                  }),
                ],
                spacing: { after: 0, line: 240, lineRule: LineRuleType.AUTO },
              }),
            ],
          }),
        ],
      }),
    ],
  });

  const recipientParagraphs = recipientLines.map((line, index) =>
    bodyParagraph(line, {
      after: index === recipientLines.length - 1 ? 397 : 0,
      keepNext: index < recipientLines.length - 1,
    })
  );

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
          new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [
              new TextRun({
                text: (data.documentTitle || "GOOGLE COVER LETTER").toUpperCase(),
                font: headingFont,
                size: 34,
                color: ink,
              }),
            ],
            spacing: { after: 45, line: 264, lineRule: LineRuleType.AUTO },
          }),
          new Paragraph({
            alignment: AlignmentType.CENTER,
            children: [
              new TextRun({
                text: data.subtitle || "by CV Genius",
                font: headingFont,
                size: 16,
                color: ink,
              }),
            ],
            spacing: { after: 198, line: 264, lineRule: LineRuleType.AUTO },
          }),
          contactLine,
          bodyParagraph(formattedDate, {
            before: 340,
            after: 283,
            alignment: AlignmentType.RIGHT,
          }),
          ...recipientParagraphs,
          bodyParagraph(
            `Dear ${
              data.contactSurname ? `${data.contactSurname},` : "(Contact Person’s Surname),"
            }`,
            { after: 283 }
          ),
          bodyParagraph(
            data.openingParagraph ||
              "I’m writing to express my interest in the advertised position. With relevant experience and a strong record of delivering results, I am eager to bring my expertise to your organisation."
          ),
          bodyParagraph(
            data.bodyParagraphOne ||
              "In my current role, I have successfully led important projects, improved processes, and collaborated with cross-functional teams. My commitment to quality and continuous improvement has enabled me to create measurable impact."
          ),
          bodyParagraph(
            data.bodyParagraphTwo ||
              "Throughout my career, I have demonstrated sound judgement, clear communication, and the ability to solve complex challenges. My experience and technical proficiency would allow me to contribute from the outset."
          ),
          bodyParagraph(
            data.closingParagraph ||
              "I’m excited by the opportunity to make a meaningful contribution. I welcome the chance to discuss how my skills and experience align with the needs of your team.",
            { after: 340 }
          ),
          bodyParagraph(data.signOff || "Yours sincerely,", { after: 57 }),
          new Paragraph({
            indent: { left: bodyIndent, right: bodyIndent },
            children: [
              new TextRun({
                text: data.fullName || "(YOUR NAME)",
                bold: true,
                font: headingFont,
                size: 25,
                color: "000000",
              }),
            ],
            spacing: { after: 0, line: 355, lineRule: LineRuleType.AUTO },
          }),
        ],
      },
    ],
  });

  return Packer.toBlob(letter);
}
