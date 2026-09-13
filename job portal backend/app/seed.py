from __future__ import annotations

import os
from datetime import datetime, timedelta
from urllib.parse import urlparse
from uuid import uuid4

from sqlalchemy import func, select

from app.auth import ensure_admin_user
from app.database import SessionLocal
from app.logging_config import get_logger
from app.constants import (
    PAKISTAN_ALL_CITIES,
    PAKISTAN_CITIES,
    PAKISTAN_NEWSPAPERS,
    PAKISTAN_PROVINCES,
)
from app.models import Job, JobQnA, Page, SiteSetting, TaxonomyTerm, ToolCategory, ToolPage
from app.page_types import page_slug_namespace
from app.services.directory_pages import ensure_directory_pages
from app.services.seo import upsert_job_seo, upsert_page_seo, upsert_tool_seo
from app.services.taxonomy import ensure_default_taxonomy
from app.utils import as_list, slugify

logger = get_logger("jobportal.seed")

HOMEPAGE_BRANDING = {
    "site_name": "Pakistan Jobs Market",
    "site_title": "Pakistan Jobs Market",
    "site_title_header": "Pakistan Jobs Market",
    "site_header": "Latest government & private job openings in Pakistan",
    "site_description": (
        "Discover current government and private jobs across Pakistan, search opportunities "
        "by city and category, get instant job alerts, and use practical career tools."
    ),
    "footer_copyright": (
        "Copyrights © {year} - Pakistan Jobs Market. All rights reserved."
    ),
    "homepage_focus_keyword": "jobs in Pakistan",
    "homepage_meta_title": "Jobs in Pakistan 2026 | Pakistan Jobs Market",
    "homepage_meta_description": (
        "Find latest government and private jobs in Pakistan by city and category. Explore "
        "curated listings, deadlines, job alerts, resume tools and career guides."
    ),
    "homepage_meta_keywords": (
        "jobs in Pakistan, latest jobs in Pakistan, government jobs Pakistan, private jobs "
        "Pakistan, newspaper jobs, FPSC jobs, PPSC jobs, jobs by city, Pakistan Jobs Market"
    ),
    "logo_url": "/pakistan-jobs-market-logo.png",
}

DEFAULT_TOOL_CATEGORIES = (
    {
        "slug": "tax-salary-tools",
        "title": "Tax & Salary Tools",
        "icon_key": "coins",
        "content": "<p>Practical calculators for Pakistan salary and tax planning.</p>",
        "color_index": 1,
    },
    {
        "slug": "tools-for-students",
        "title": "Tools for Students",
        "icon_key": "graduation",
        "content": "<p>Flexible study and academic planning calculators for students.</p>",
        "color_index": 2,
    },
    {
        "slug": "image-editing-tools",
        "title": "Image Editing Tools",
        "icon_key": "image",
        "content": "<p>Helpful image utilities will be published here.</p>",
        "color_index": 3,
    },
    {
        "slug": "document-tools",
        "title": "Document Tools",
        "icon_key": "document",
        "content": "<p>Helpful document utilities will be published here.</p>",
        "color_index": 4,
    },
)

DEFAULT_TOOLS = (
    {
        "category_slug": "tax-salary-tools",
        "slug": "pakistan-tax-calculator",
        "title": "Pakistan Tax Calculator",
        "tool_kind": "tax_calculator",
        "content": (
            "<p>Estimate monthly and annual income tax for a salaried person in Pakistan "
            "using the selected tax year's federal salary slabs.</p>"
        ),
    },
    {
        "category_slug": "tax-salary-tools",
        "slug": "government-salary-calculator",
        "title": "Government Salary Calculator",
        "tool_kind": "government_salary_calculator",
        "content": (
            "<p>Estimate a Pakistan government salary from the selected pay family, grade "
            "and pay stage. The result separates basic or consolidated pay from standard "
            "allowances and clearly identifies benefits that depend on an employee's "
            "department, posting or appointment terms.</p><p>Federal BPS, PPS, MP, SPPS "
            "and Management Grade figures use published Government of Pakistan schedules. "
            "Organization-specific SPS, O, E, OG, EG and J packages must be entered from "
            "the relevant official advertisement, appointment letter or salary slip because "
            "those labels do not have one government-wide monetary table.</p>"
        ),
    },
    {
        "category_slug": "tools-for-students",
        "slug": "cgpa-calculator",
        "title": "CGPA Calculator",
        "tool_kind": "cgpa_calculator",
        "content": (
            "<p>Add any number of semesters and subjects to calculate semester GPA and "
            "CGPA on Pakistan's common 4.00 scale.</p>"
        ),
    },
    {
        "category_slug": "image-editing-tools",
        "slug": "add-watermark",
        "title": "Add Watermark to Image",
        "tool_kind": "image_watermark",
        "content": (
            "<h2>Add a text watermark to an image</h2>"
            "<p>Choose one PNG, JPEG or WebP image, type your watermark and adjust its "
            "colour, size, weight, underline, placement and opacity. Preview each change "
            "before downloading a full-resolution PNG.</p>"
            "<p>The editor runs in your browser: your image is not uploaded to Pakistan Jobs "
            "Market. Files must be under 10 MB and no larger than 12 megapixels. Animated "
            "images and SVG are not accepted. Exporting a new PNG removes the source "
            "file's metadata, including camera location details. Check the result before "
            "sharing or publishing it.</p>"
        ),
    },
    {
        "category_slug": "tools-for-students",
        "slug": "resume-builder",
        "title": "Resume Builder",
        "tool_kind": "resume_builder",
        "content": (
            "<p>Create a polished resume from guided sections, choose from four templates, "
            "preview the result and download it as PDF or DOCX.</p>"
        ),
    },
    {
        "category_slug": "tools-for-students",
        "slug": "cover-letter",
        "title": "Cover Letter Builder",
        "tool_kind": "cover_letter",
        "content": (
            "<p>Build a structured cover letter, review it in the live preview and download "
            "the finished application letter.</p>"
        ),
    },
    {
        "category_slug": "tools-for-students",
        "slug": "api",
        "title": "API",
        "tool_kind": "student_api",
        "content": (
            "<h2>Build student projects with real Pakistan jobs data</h2>"
            "<p>The Pakistan Jobs Market student API gives active newsletter subscribers "
            "read-only access to published job and blog data for learning, coursework and "
            "portfolio projects. Verify your subscribed email to create a private API key.</p>"
            "<p>Each subscriber receives a lifetime allowance of 50 data requests. Job "
            "responses include the complete description, advertisement image URLs and public "
            "attachment details; blog responses include the complete published article.</p>"
            "<p>Keep your key private and use the service responsibly. Access remains linked "
            "to an active newsletter subscription.</p>"
        ),
    },
    {
        "category_slug": "document-tools",
        "slug": "docx-pdf-converter",
        "title": "DOCX and PDF Converter",
        "tool_kind": "document_converter",
        "content": (
            "<p>Convert one DOCX document to PDF or one PDF document to DOCX. "
            "Files are validated before processing and automatically removed after a short "
            "download window.</p><p>DOCX-to-PDF conversion preserves the document's print "
            "layout using LibreOffice. PDF-to-DOCX conversion reconstructs editable content "
            "as accurately as possible; highly complex or scanned PDFs can require manual "
            "adjustment because PDF stores fixed page positions rather than document structure.</p>"
        ),
    },
)

ABOUT_HTML = """
<p><strong>Pakistan Jobs Market</strong> is an independent online job discovery platform created
for people looking for current employment opportunities across Pakistan. Our purpose is simple:
to make it easier to find useful government, private-sector, newspaper and company career
announcements in one searchable place.</p>

<h2>Helping people find jobs in Pakistan</h2>
<p>Searching for work often means checking many newspaper pages, recruitment portals, public
service commission notices and employer career websites. Pakistan Jobs Market organizes selected
opportunities so visitors can browse latest jobs in Pakistan by city, job type and category. Our
coverage may include roles in Karachi, Lahore, Islamabad, Rawalpindi, Peshawar, Quetta, Faisalabad,
Multan and other cities, as well as nationwide vacancies.</p>
<p>Listings may include government jobs, private jobs, public-sector vacancies, banking jobs,
education jobs, technology roles, healthcare opportunities and other career categories. Where the
source provides them, we present important details such as the employer, publication date,
application deadline, education, experience, location and original application or reference URL.</p>

<h2>What Pakistan Jobs Market offers</h2>
<ul>
  <li><strong>Organized job listings:</strong> filters for cities, categories and government or
  private employment help visitors narrow their search.</li>
  <li><strong>Application deadlines:</strong> prominent deadline information and an Applications
  Closed notice help visitors identify active opportunities.</li>
  <li><strong>Job alerts:</strong> visitors can subscribe to receive an email when a new job is
  published and can unsubscribe whenever they choose.</li>
  <li><strong>Career resources:</strong> the blog, ATS-standard resume builder with an on-page
  readiness score, and cover-letter builder offer practical tools for applicants.</li>
  <li><strong>Interview Q&amp;A:</strong> some job pages may contain questions and answers extracted
  from relevant public video transcripts or comments to support further research.</li>
</ul>

<h2>Free tools for applications, study and salary planning</h2>
<p>The Tools hub brings together interactive resources designed for Pakistan. It includes the
Pakistan Tax Calculator, Government Salary Calculator, CGPA Calculator, Resume Builder, Cover
Letter Builder, DOCX/PDF Converter and a read-only student API. Active newsletter subscribers can
use the API to build coursework and portfolio projects with published job and blog data. Tool
categories and pages are managed through the website's content system so the directory can
continue to grow.</p>
<p>The Government Salary Calculator separates basic pay and applicable allowances where a central
official schedule exists. Because SPS, O, E, OG, EG and J packages can be set by individual
organizations, those scales require the user to enter the amount shown in the relevant official
advertisement, appointment letter or salary slip. Official references and important limitations
are shown with the calculator.</p>

<h2>ATS-standard resume tools</h2>
<p>Our Resume Builder uses conventional headings, searchable text, a clean single-column reading
order and recruiter-friendly formatting. Visitors can check a transparent ATS-readiness score for
the resume currently in the form, review category-level feedback, and download the same
professional layout as a searchable PDF or editable Word document.</p>

<h2>Our editorial approach</h2>
<p>We aim to publish clear, useful and source-attributed information. Job advertisements may be
collected from publicly accessible employer career pages, government institutions, public service
commissions and established Pakistani newspapers. We may summarize or format an advertisement for
readability, while linking to a reference or application source where one is available.</p>
<p>Pakistan Jobs Market is not a recruitment agency and does not accept applications on behalf of
employers. Candidates should always read the official advertisement, confirm eligibility,
deadlines and application instructions, and verify any fee directly with the recruiting
organization before applying.</p>

<h2>Accuracy, corrections and responsible use</h2>
<p>Recruitment notices can change, be extended, withdrawn or corrected after publication. Although
we work to keep information helpful and current, we cannot guarantee that every third-party detail
is complete or error-free. If you identify an outdated deadline, broken source link or inaccurate
detail, please use our Contact Us page and include the relevant page URL so it can be reviewed.</p>
<p>We also encourage safe job searching. Never share banking passwords, one-time codes or
unnecessary sensitive information with an unverified person. Be cautious of anyone promising a job
in exchange for an unofficial payment.</p>

<h2>Our commitment</h2>
<p>Pakistan Jobs Market is designed to be accessible to students, fresh graduates, experienced
professionals and public-sector candidates throughout the country. We will continue improving the
quality of listings, search tools and career guidance so that visitors can spend less time finding
opportunities and more time preparing strong applications.</p>
""".strip()

PRIVACY_HTML = """
<p><strong>Pakistan Jobs Market</strong> respects the privacy of visitors, subscribers and people
who contact us. This Privacy Policy explains what information may be collected when you use this
website, why it is used, how it may be protected and the choices available to you.</p>
<p><strong>Effective date:</strong> 5 September 2026</p>

<h2>Information we may collect</h2>
<p>You can browse public job listings and career content without creating an account. Depending on
the feature you use, we may collect the following limited information:</p>
<ul>
  <li><strong>Subscription information:</strong> the email address you voluntarily submit for job
  alerts, together with subscription status and operational timestamps.</li>
  <li><strong>Contact information:</strong> your name, email address, subject and message when you
  send an enquiry, correction or feedback through the Contact Us form.</li>
  <li><strong>Technical information:</strong> IP address, browser and device information, requested
  pages, timestamps, referral data and error records that may be processed in server logs,
  security monitoring or aggregate analytics.</li>
  <li><strong>Preference information:</strong> browser-stored choices such as light or dark theme.</li>
  <li><strong>Temporary document-conversion information:</strong> when you choose the DOCX/PDF
  Converter, the selected file, original filename, validation details, conversion status and
  generated download are processed for the limited purpose of completing that request.</li>
  <li><strong>Student API information:</strong> when a subscriber requests API access, we process
  the subscribed email, subscription status, one-time verification state, a one-way hash and short
  prefix of the API key, quota and request counts, operational timestamps, and privacy-protected
  network identifiers used to prevent abuse.</li>
</ul>

<h2>How information is used</h2>
<p>We use information only for legitimate website operations, including delivering requested job
alerts, responding to messages, preventing abuse, diagnosing errors, protecting the service,
understanding aggregate usage and improving content and performance. We do not ask visitors to
submit a CV or sensitive financial credentials in order to browse the website.</p>

<h2>Resume Builder, Cover Letter Builder and calculators</h2>
<p>Information entered in the Resume Builder or Cover Letter Builder is processed in your browser
to create the preview and requested PDF or DOCX download. Resume content and the resulting
ATS-readiness score are not submitted to Pakistan Jobs Market. Salary, tax and CGPA calculator
inputs are likewise calculated in the browser and are not stored by Pakistan Jobs Market. Closing
or refreshing a page may remove this information unless your browser preserves it independently.</p>

<h2>DOCX and PDF conversion</h2>
<p>The document converter must send the selected DOCX or PDF file to our server because the format
conversion cannot be completed entirely in the browser. Files are checked for type and size,
processed in an isolated temporary job, made available through a short-lived access token and
automatically removed after the configured download window. We do not use uploaded document
content for advertising, profiling or model training. Do not upload documents containing
information you are not authorized to process, and remove unnecessary sensitive information
before conversion.</p>

<h2>Email alerts and unsubscribe choices</h2>
<p>If you subscribe to job alerts, Pakistan Jobs Market uses the submitted address to send messages
about newly published jobs. Each alert includes an unsubscribe option. Using that option removes
the active subscription record so future alerts are not sent. Transactional messages already in
delivery may not be recalled.</p>

<h2>Student API verification and credentials</h2>
<p>The student API sends a short-lived, single-use verification code to an active newsletter
subscriber before creating a key. Pakistan Jobs Market does not store the readable verification
code or the complete API key: keyed one-way hashes are stored for comparison, and only a short key
prefix is retained for support. The service also stores whether access is active, the lifetime
quota, requests used and last-use timestamps. Creating a replacement key invalidates the earlier
key but does not reset the quota.</p>
<p>Hashed rate-limit and security events may be retained for a limited period to detect automated
abuse. Unsubscribing disables API access. A minimal inactive access ledger may be retained where
reasonably necessary to enforce the lifetime quota, prevent repeated free-key creation, investigate
abuse or meet legal and security obligations.</p>

<h2>Cookies, analytics and advertising</h2>
<p>The website or its service providers may use cookies, local storage or similar technologies for
essential preferences, security, audience measurement and performance. Pakistan Jobs Market may
use Google services such as Search Console or analytics tools to understand aggregate search and
website performance.</p>

<h3>Google advertising cookies and personalized advertising</h3>
<p>Third-party vendors, including Google, use cookies to serve ads based on a visitor's previous
visits to Pakistan Jobs Market or other websites. Google's use of advertising cookies enables
Google and its partners to serve ads based on visits to this website and/or other websites on the
Internet.</p>
<p>Visitors can control personalized advertising in the following ways:</p>
<ul>
  <li>Visit <a href="https://adssettings.google.com/" rel="noopener noreferrer">Google Ads
  Settings</a> to manage or opt out of personalized advertising from Google.</li>
  <li>Visit the <a href="https://www.aboutads.info/choices/" rel="noopener noreferrer">YourAdChoices
  opt-out page</a> to opt out of some third-party vendors' use of cookies for personalized
  advertising.</li>
  <li>Use browser controls to block or delete cookies. Disabling cookies may affect some website
  features.</li>
</ul>
<p>Google and Google-certified advertising vendors may collect, receive or use information as a
result of ad serving on this website. Learn more about <a
href="https://policies.google.com/technologies/partner-sites" rel="noopener noreferrer">how Google
uses information from sites that use its services</a>, <a
href="https://policies.google.com/technologies/ads" rel="noopener noreferrer">Google advertising
technologies</a>, and the <a href="https://policies.google.com/privacy"
rel="noopener noreferrer">Google Privacy Policy</a>. Where other advertising vendors or networks
are enabled, their identities and privacy choices will be disclosed through the applicable consent
message or this policy.</p>

<h3>Consent choices for regulated regions</h3>
<p>For visitors in the European Economic Area, the United Kingdom and Switzerland, Pakistan Jobs
Market uses Google-certified consent-management controls to request applicable choices for
advertising cookies, local storage, personalized advertising and related data processing. Visitors
can change or withdraw a choice through the privacy options made available by that consent
message.</p>

<h2>Service providers and third-party links</h2>
<p>We may rely on hosting, database, object-storage, email-delivery, security and analytics
providers to operate the service. These providers process limited information for the services
they supply. Document conversion may also rely on server-side open-source office and document
processing software. Job listings and articles can link to employer, government, newspaper,
social media
or other external websites. Pakistan Jobs Market does not control their content or privacy
practices, so visitors should review the policy of each external service before submitting data.</p>

<h2>Data retention and security</h2>
<p>Information is retained only for as long as reasonably needed for its purpose, legal obligations,
security, dispute resolution or service continuity. Operational error logs are retained for a
short, configured period. We use reasonable administrative and technical safeguards, but no
internet transmission or storage system can be guaranteed completely secure.</p>

<h2>Your choices and requests</h2>
<p>You may unsubscribe from job alerts at any time. You may also contact us to request correction or
deletion of personal information you previously submitted, subject to identity verification and
any legitimate retention requirements. Browser settings can be used to control cookies and local
storage.</p>

<h2>Children's privacy</h2>
<p>This service is intended for general job seekers and is not designed to knowingly collect
personal information from children below the age at which they may consent to online data
processing. A parent or guardian who believes a child submitted personal information may contact
us for review.</p>

<h2>Policy updates and contact</h2>
<p>We may update this Privacy Policy when features, providers or legal requirements change. The
latest published version applies from the effective date shown at the beginning of this policy.
Questions or privacy requests can be sent through the Pakistan Jobs Market Contact Us page.</p>
""".strip()

DISCLAIMER_HTML = """
<p><strong>Pakistan Jobs Market</strong> aggregates and organizes job advertisements from public
sources in good faith as an informational resource for job seekers. Sources may include Pakistani
newspapers such as <em>Daily Jang</em>, <em>Express</em>, <em>Nawa-i-Waqt</em>, <em>The News</em>,
<em>Dawn</em> and <em>The Nation</em>, as well as government institutions, public service
commissions and private-company career pages.</p>

<h2>Not an employer or recruitment agency</h2>
<p>Pakistan Jobs Market is not the employer, recruiting organization, testing authority or
newspaper behind third-party vacancies. Unless a page expressly states otherwise, we do not
participate in selection, shortlisting, testing, interviews, appointments or payment collection.
Submitting a message or subscribing to alerts is not a job application and does not create an
employment or agency relationship.</p>

<h2>Verify every job advertisement</h2>
<p>Information may be summarized, reformatted or transcribed from a public advertisement. A source
can later change a deadline, eligibility rule, number of posts, fee, test schedule or application
procedure. Before applying, users must confirm all details through the official advertisement,
employer website or authorized recruitment body. If this website and the official source differ,
the official source controls.</p>
<p>We do not warrant that every listing is complete, current, continuously available or free from
typing, transcription or source errors. Pakistan Jobs Market is not responsible for an inaccurate,
misrepresented, expired, withdrawn or misleading third-party advertisement.</p>

<h2>Applications, payments and recruitment fraud</h2>
<p>Use only the official application channel and payment method stated by the recruiting body.
Pakistan Jobs Market does not guarantee employment and does not authorize individuals to request
money, passwords, one-time codes or banking credentials in its name. Treat unsolicited job offers,
unofficial fees and promises of guaranteed appointment with caution. Users are responsible for
assessing the authenticity and suitability of an opportunity before sharing information or making
any payment.</p>

<h2>External links and third-party content</h2>
<p>Reference, application, newspaper, video and employer links are provided for convenience. We do
not control external websites and cannot guarantee their availability, safety, accuracy, products,
services or privacy practices. Opening a third-party link is at the visitor's discretion.</p>

<h2>Interview Q&amp;A and automated assistance</h2>
<p>Some job pages may display interview questions and answers extracted or organized with automated
tools from publicly available video transcripts or comments. Such material may contain opinions,
outdated statements, language errors or incomplete context. It is supplementary study material,
not official recruitment guidance, and should be checked against authoritative sources.</p>

<h2>Career tools and ATS score</h2>
<p>The Resume Builder follows common ATS-readable practices and provides an on-device readiness
estimate based on completeness, standard sections, achievements, measurable impact, skills,
keywords and readability. Applicant-tracking systems and job requirements vary, so the score is
guidance rather than a test performed by an employer and does not guarantee parsing, shortlisting,
an interview or employment. Users should tailor every resume to the official job description and
review all generated documents before applying.</p>

<h2>Tax, salary and CGPA calculators</h2>
<p>Calculator results are informational estimates, not tax, payroll, accounting, legal or academic
advice. Tax laws, pay notifications, allowances, departmental rules and university grading
policies can change or depend on facts the calculator does not know. Government salary figures for
organization-specific scales require an amount from the relevant employer's current official
document. Users must verify every result with FBR, the Finance Division, the employing department,
their accounts office or their educational institution as applicable. No calculator result creates
an entitlement or guarantees a payslip, tax liability, grade or benefit.</p>

<h2>Document conversion</h2>
<p>The DOCX/PDF Converter is provided for convenience. Although the service validates files and
checks converted output, the two formats store content differently. Complex layouts, fonts,
forms, tracked changes, embedded objects, scanned pages or damaged and password-protected files
may not convert exactly. Users must inspect the downloaded file before relying on, signing,
printing or submitting it. Keep an independent copy of every original; Pakistan Jobs Market is not
responsible for formatting changes, omitted elements, file corruption or loss arising from use of
the converter.</p>

<h2>Student API</h2>
<p>The student API is a limited, read-only learning resource. API responses may reproduce the same
third-party job information and public-source limitations described above, and they may change or
be removed without notice. A key does not transfer ownership of website or source content, permit
misrepresentation, or guarantee uninterrupted access. Users must protect their key, respect the
lifetime quota, attribute sources where appropriate, and independently verify information before
using it in a project or application.</p>

<h2>Copyright, corrections and availability</h2>
<p>Advertisements, logos and source materials may belong to their respective owners and are used
for identification and informational reference. Rights holders or users may contact us with a
specific page URL to request review of an attribution, correction or removal. We may change,
suspend or remove content or features without notice.</p>

<h2>Limitation of responsibility</h2>
<p>To the maximum extent permitted by applicable law, use of Pakistan Jobs Market is at the user's
own risk. We are not liable for losses arising from reliance on a listing, missed deadlines,
external websites, communications with third parties, application decisions, fees, fraud or use of
career resources. If you do not agree with this disclaimer, please discontinue use of the service.</p>
""".strip()

DEFAULT_PAGE_SEO = {
    "about": {
        "focus_keyword": "Pakistan Jobs Market",
        "meta_title": "About Pakistan Jobs Market | Jobs in Pakistan",
        "meta_description": (
            "Learn how Pakistan Jobs Market helps job seekers discover government, private, "
            "newspaper and company career opportunities across Pakistan."
        ),
        "meta_keywords": (
            "about Pakistan Jobs Market, jobs in Pakistan, Pakistan job portal, government jobs, "
            "private jobs, newspaper jobs, career resources"
        ),
    },
    "privacy": {
        "focus_keyword": "Pakistan Jobs Market privacy policy",
        "meta_title": "Privacy Policy | Pakistan Jobs Market",
        "meta_description": (
            "Read how Pakistan Jobs Market collects, uses, protects and retains contact, "
            "subscription, analytics and technical information."
        ),
        "meta_keywords": (
            "Pakistan Jobs Market privacy policy, data protection, cookies, analytics, "
            "newsletter privacy, job alerts privacy"
        ),
    },
    "disclaimer": {
        "focus_keyword": "Pakistan Jobs Market disclaimer",
        "meta_title": "Job Listing Disclaimer | Pakistan Jobs Market",
        "meta_description": (
            "Understand sourcing, verification limits, application risks and user responsibilities "
            "for job listings published on Pakistan Jobs Market."
        ),
        "meta_keywords": (
            "Pakistan Jobs Market disclaimer, job listing disclaimer, newspaper jobs disclaimer, "
            "government jobs disclaimer, recruitment fraud warning"
        ),
    },
    "jobs-by-cities": {
        "focus_keyword": "jobs by city in Pakistan",
        "meta_title": "Jobs by City in Pakistan | Pakistan Jobs Market",
        "meta_description": "Browse current Pakistan job opportunities by city, including province-wide and nationwide vacancies.",
        "meta_keywords": "jobs by city Pakistan, Lahore jobs, Karachi jobs, Islamabad jobs",
    },
    "jobs-by-provinces": {
        "focus_keyword": "jobs by province in Pakistan",
        "meta_title": "Jobs by Province in Pakistan | Pakistan Jobs Market",
        "meta_description": "Browse current jobs across every province and territory of Pakistan.",
        "meta_keywords": "jobs by province Pakistan, Punjab jobs, Sindh jobs, KPK jobs",
    },
    "jobs-by-categories": {
        "focus_keyword": "jobs by category in Pakistan",
        "meta_title": "Jobs by Category in Pakistan | Pakistan Jobs Market",
        "meta_description": "Explore current Pakistan vacancies by profession and job category.",
        "meta_keywords": "jobs by category Pakistan, engineering jobs, teaching jobs, IT jobs",
    },
    "jobs-by-organizations": {
        "focus_keyword": "jobs by organization in Pakistan",
        "meta_title": "Jobs by Organization in Pakistan | Pakistan Jobs Market",
        "meta_description": "Find current vacancies grouped by the recruiting organization or department.",
        "meta_keywords": "organization jobs Pakistan, department jobs, company jobs Pakistan",
    },
    "jobs-by-newspapers": {
        "focus_keyword": "newspaper jobs in Pakistan",
        "meta_title": "Jobs by Newspaper in Pakistan | Pakistan Jobs Market",
        "meta_description": "Browse current Pakistan job advertisements by their newspaper source.",
        "meta_keywords": "newspaper jobs Pakistan, Jang jobs, Dawn jobs, Express jobs",
    },
}

DEFAULT_PAGES = [
    (
        "about",
        "About Us",
        ABOUT_HTML,
    ),
    (
        "privacy",
        "Privacy Policy",
        PRIVACY_HTML,
    ),
    (
        "contact",
        "Contact Us",
        "<p>Questions, partnership ideas, or corrections to a listing? Send a message below. "
        "Pakistan Jobs Market does not process job applications.</p>",
    ),
    ("disclaimer", "Disclaimer", DISCLAIMER_HTML),
    (
        "jobs-by-cities",
        "Jobs by Cities",
        "<p>Choose a city to see local vacancies together with province-wide and nationwide opportunities that also cover that city.</p>",
    ),
    (
        "jobs-by-provinces",
        "Jobs by Provinces",
        "<p>Explore vacancies for each province and territory. Results also include jobs assigned to cities inside that region and roles open across Pakistan.</p>",
    ),
    (
        "jobs-by-categories",
        "Jobs by Category",
        "<p>Browse current job posts using the categories assigned in the job editor.</p>",
    ),
    (
        "jobs-by-organizations",
        "Jobs by Organization",
        "<p>Find opportunities by the source organization or recruiting department named on each job post.</p>",
    ),
    (
        "jobs-by-newspapers",
        "Jobs by Newspaper",
        "<p>Find advertisements by the newspaper name recorded on each job post.</p>",
    ),
]


def ensure_default_tools(db) -> list[object]:
    """Seed the requested tools once without overwriting later administrator edits."""
    created: list[object] = []
    categories: dict[str, ToolCategory] = {}
    max_color = db.execute(select(func.max(ToolCategory.color_index))).scalar() or 0
    for order, item in enumerate(DEFAULT_TOOL_CATEGORIES):
        category = db.execute(
            select(ToolCategory).where(ToolCategory.slug == item["slug"])
        ).scalar_one_or_none()
        if not category:
            color_index = int(item["color_index"])
            if db.execute(
                select(ToolCategory.id).where(ToolCategory.color_index == color_index)
            ).scalar_one_or_none():
                max_color += 1
                color_index = max_color
            category = ToolCategory(
                id=str(uuid4()),
                slug=item["slug"],
                title=item["title"],
                content=item["content"],
                icon_key=item["icon_key"],
                color_index=color_index,
                sort_order=order,
                is_published=True,
                created_at=datetime.utcnow(),
                updated_at=datetime.utcnow(),
            )
            db.add(category)
            upsert_tool_seo(
                db,
                category,
                entity_type="tool_category",
                path=f"/tools/categories/{category.slug}",
            )
            created.append(category)
        categories[item["slug"]] = category

    db.flush()
    for order, item in enumerate(DEFAULT_TOOLS):
        tool = db.execute(
            select(ToolPage).where(ToolPage.slug == item["slug"])
        ).scalar_one_or_none()
        if tool:
            continue
        category = categories[item["category_slug"]]
        tool = ToolPage(
            id=str(uuid4()),
            category_id=category.id,
            slug=item["slug"],
            title=item["title"],
            content=item["content"],
            tool_kind=item["tool_kind"],
            sort_order=order,
            is_published=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(tool)
        upsert_tool_seo(
            db,
            tool,
            entity_type="tool",
            path=f"/tools/{tool.slug}",
        )
        created.append(tool)

    cursor = db.get(SiteSetting, "tool_category_color_cursor")
    current_max = db.execute(select(func.max(ToolCategory.color_index))).scalar() or max_color
    if cursor:
        cursor.value = str(max(int(cursor.value or 0), int(current_max)))
        cursor.updated_at = datetime.utcnow()
    else:
        db.add(
            SiteSetting(
                key="tool_category_color_cursor",
                value=str(current_max),
                updated_at=datetime.utcnow(),
            )
        )
    db.flush()
    return created


def ensure_default_pages(db) -> list[Page]:
    """Create missing core CMS pages without overwriting administrator edits."""
    created: list[Page] = []
    for slug, title, content in DEFAULT_PAGES:
        exists = db.execute(select(Page).where(Page.slug == slug)).scalar_one_or_none()
        if exists:
            continue
        page = Page(
            id=str(uuid4()),
            slug=slug,
            title=title,
            content=content,
            is_published=True,
            created_at=datetime.utcnow(),
            updated_at=datetime.utcnow(),
        )
        db.add(page)
        upsert_page_seo(db, page, seo_override=DEFAULT_PAGE_SEO.get(slug))
        created.append(page)
    return created


def sync_taxonomy_pages_v1(db) -> list[Page]:
    """Create one CMS page per current job-directory entry exactly once.

    The completion marker deliberately prevents deleted or renamed pages from being
    recreated on later starts. New directory pages can be added from Admin > Pages.
    """
    marker_key = "taxonomy_pages_v1_complete"
    if db.get(SiteSetting, marker_key):
        return []

    jobs = db.execute(
        select(Job.source, Job.newspaper, Job.tags)
    ).all()
    category_terms = db.execute(
        select(TaxonomyTerm.name).where(
            TaxonomyTerm.kind == "category",
            TaxonomyTerm.is_active.is_(True),
        )
    ).scalars().all()

    values_by_type = {
        "city": [*PAKISTAN_CITIES, PAKISTAN_ALL_CITIES],
        "province": PAKISTAN_PROVINCES,
        "category": [
            *category_terms,
            *(value for job in jobs for value in as_list(job.tags)),
        ],
        "organization": (job.source for job in jobs),
        "newspaper": [*PAKISTAN_NEWSPAPERS, *(job.newspaper for job in jobs)],
    }
    created = ensure_directory_pages(db, values_by_type)

    db.add(SiteSetting(key=marker_key, value="1", updated_at=datetime.utcnow()))
    return created


def sync_job_directory_pages_v3(db) -> list[Page]:
    """Reconcile Pages for job values edited before automatic sync was enabled."""
    marker_key = "job_directory_pages_v3_complete"
    if db.get(SiteSetting, marker_key):
        return []

    jobs = db.execute(
        select(Job.source, Job.newspaper, Job.tags, Job.cities, Job.provinces)
    ).all()
    created = ensure_directory_pages(
        db,
        {
            "city": (value for job in jobs for value in as_list(job.cities)),
            "province": (value for job in jobs for value in as_list(job.provinces)),
            "category": (value for job in jobs for value in as_list(job.tags)),
            "organization": (job.source for job in jobs),
            "newspaper": (job.newspaper for job in jobs),
        },
    )
    db.add(SiteSetting(key=marker_key, value="1", updated_at=datetime.utcnow()))
    return created


def sync_directory_page_slugs_v2(db) -> list[Page]:
    """Remove legacy type suffixes now that slugs are scoped by public route."""
    marker_key = "directory_page_slugs_v2_complete"
    if db.get(SiteSetting, marker_key):
        return []

    pages = db.execute(select(Page)).scalars().all()
    occupied = {
        (page_slug_namespace(page.page_type), page.slug.casefold()): page.id
        for page in pages
    }
    updated: list[Page] = []
    for page in pages:
        if page.page_type == "standard" or not page.taxonomy_value:
            continue
        desired = slugify(page.taxonomy_value)
        namespace = page_slug_namespace(page.page_type)
        legacy_base = f"{desired}-{page.page_type}"
        legacy_suffix = page.slug.removeprefix(f"{legacy_base}-")
        is_generated_legacy_slug = page.slug == legacy_base or (
            page.slug.startswith(f"{legacy_base}-") and legacy_suffix.isdigit()
        )
        if not desired or not is_generated_legacy_slug:
            continue
        owner = occupied.get((namespace, desired.casefold()))
        if owner and owner != page.id:
            continue
        occupied.pop((namespace, page.slug.casefold()), None)
        occupied[(namespace, desired.casefold())] = page.id
        page.slug = desired
        page.updated_at = datetime.utcnow()
        upsert_page_seo(db, page)
        updated.append(page)

    db.add(SiteSetting(key=marker_key, value="1", updated_at=datetime.utcnow()))
    return updated


def sync_local_core_pages_once(db) -> list[Page]:
    """Apply the current production-page snapshot to the local DB exactly once."""
    site_host = (urlparse(os.getenv("SITE_URL", "http://localhost:3000")).hostname or "").lower()
    if site_host not in {"localhost", "127.0.0.1", "frontend"}:
        return []
    marker_key = "local_core_pages_synced_from_production_v1"
    if db.get(SiteSetting, marker_key):
        return []

    changed: list[Page] = []
    for slug, title, content in DEFAULT_PAGES:
        if slug not in {"about", "privacy", "contact", "disclaimer"}:
            continue
        page = db.execute(select(Page).where(Page.slug == slug)).scalar_one_or_none()
        if not page:
            continue
        page.title = title
        page.content = content
        page.is_published = True
        page.updated_at = datetime.utcnow()
        upsert_page_seo(db, page, seo_override=DEFAULT_PAGE_SEO.get(slug))
        changed.append(page)
    db.add(
        SiteSetting(
            key=marker_key,
            value="true",
            updated_at=datetime.utcnow(),
        )
    )
    db.flush()
    return changed


def sync_core_page_content_v2(db) -> list[Page]:
    """Install the requested long-form core content and SEO once on every environment."""
    marker_key = "core_pages_seo_content_v2"
    if db.get(SiteSetting, marker_key):
        return []

    defaults = {slug: (title, content) for slug, title, content in DEFAULT_PAGES}
    changed: list[Page] = []
    for slug in ("about", "privacy", "disclaimer"):
        title, content = defaults[slug]
        page = db.execute(select(Page).where(Page.slug == slug)).scalar_one_or_none()
        if not page:
            continue
        page.title = title
        page.content = content
        page.is_published = True
        page.updated_at = datetime.utcnow()
        upsert_page_seo(db, page, seo_override=DEFAULT_PAGE_SEO[slug])
        changed.append(page)

    db.add(SiteSetting(key=marker_key, value="true", updated_at=datetime.utcnow()))
    db.flush()
    return changed


def sync_core_page_content_v3(db) -> list[Page]:
    """Publish the ATS Resume Builder disclosures to the managed core pages once."""
    marker_key = "core_pages_ats_resume_content_v3"
    if db.get(SiteSetting, marker_key):
        return []

    defaults = {slug: (title, content) for slug, title, content in DEFAULT_PAGES}
    changed: list[Page] = []
    for slug in ("about", "privacy", "disclaimer"):
        title, content = defaults[slug]
        page = db.execute(select(Page).where(Page.slug == slug)).scalar_one_or_none()
        if not page:
            continue
        page.title = title
        page.content = content
        page.is_published = True
        page.updated_at = datetime.utcnow()
        upsert_page_seo(db, page, seo_override=DEFAULT_PAGE_SEO[slug])
        changed.append(page)

    db.add(SiteSetting(key=marker_key, value="true", updated_at=datetime.utcnow()))
    db.flush()
    return changed


def sync_privacy_adsense_disclosures_v4(db) -> list[Page]:
    """Publish Google's required advertising-cookie disclosures exactly once."""
    marker_key = "privacy_adsense_disclosures_v4"
    if db.get(SiteSetting, marker_key):
        return []

    page = db.execute(select(Page).where(Page.slug == "privacy")).scalar_one_or_none()
    changed: list[Page] = []
    if page:
        page.title = "Privacy Policy"
        page.content = PRIVACY_HTML
        page.is_published = True
        page.updated_at = datetime.utcnow()
        upsert_page_seo(db, page, seo_override=DEFAULT_PAGE_SEO["privacy"])
        changed.append(page)

    db.add(SiteSetting(key=marker_key, value="true", updated_at=datetime.utcnow()))
    db.flush()
    return changed


def sync_expanded_tools_core_pages_v5(db) -> list[Page]:
    """Publish the expanded tools, privacy and accuracy disclosures exactly once."""
    marker_key = "expanded_tools_core_pages_v5"
    if db.get(SiteSetting, marker_key):
        return []

    defaults = {slug: (title, content) for slug, title, content in DEFAULT_PAGES}
    changed: list[Page] = []
    for slug in ("about", "privacy", "disclaimer"):
        title, content = defaults[slug]
        page = db.execute(select(Page).where(Page.slug == slug)).scalar_one_or_none()
        if not page:
            continue
        page.title = title
        page.content = content
        page.is_published = True
        page.updated_at = datetime.utcnow()
        upsert_page_seo(db, page, seo_override=DEFAULT_PAGE_SEO[slug])
        changed.append(page)

    db.add(SiteSetting(key=marker_key, value="true", updated_at=datetime.utcnow()))
    db.flush()
    return changed


def sync_student_api_core_pages_v6(db) -> list[Page]:
    """Publish student API, credential and quota disclosures exactly once."""
    marker_key = "student_api_core_pages_v6"
    if db.get(SiteSetting, marker_key):
        return []

    defaults = {slug: (title, content) for slug, title, content in DEFAULT_PAGES}
    changed: list[Page] = []
    for slug in ("about", "privacy", "disclaimer"):
        title, content = defaults[slug]
        page = db.execute(select(Page).where(Page.slug == slug)).scalar_one_or_none()
        if not page:
            continue
        page.title = title
        page.content = content
        page.is_published = True
        page.updated_at = datetime.utcnow()
        upsert_page_seo(db, page, seo_override=DEFAULT_PAGE_SEO[slug])
        changed.append(page)

    db.add(SiteSetting(key=marker_key, value="true", updated_at=datetime.utcnow()))
    db.flush()
    return changed


def sync_homepage_branding_seo_v1(db) -> list[str]:
    """Apply the new public brand and homepage SEO once, without overwriting future edits."""
    marker_key = "homepage_branding_seo_v1"
    if db.get(SiteSetting, marker_key):
        return []

    changed: list[str] = []
    for key, value in HOMEPAGE_BRANDING.items():
        row = db.get(SiteSetting, key)
        if row:
            row.value = value
            row.updated_at = datetime.utcnow()
        else:
            db.add(SiteSetting(key=key, value=value, updated_at=datetime.utcnow()))
        changed.append(key)
    db.add(SiteSetting(key=marker_key, value="true", updated_at=datetime.utcnow()))
    db.flush()
    return changed

SEED_JOBS = [
    {
        "title": "Senior Software Engineer — Backend",
        "description": "<p>Build scalable APIs and services for enterprise clients across Pakistan.</p><ul><li>Python / FastAPI</li><li>PostgreSQL</li><li>AWS</li></ul>",
        "source": "Systems Limited",
        "cities": ["Lahore"],
        "job_type": "private",
        "skills": ["Python", "FastAPI", "PostgreSQL"],
        "tags": ["Software Engineering"],
        "salary_range": "PKR 250,000 – 400,000",
        "experience_required": "4 year(s)",
        "education_required": "BS Computer Science",
        "days_ago": 2,
        "deadline_days": 20,
    },
    {
        "title": "Assistant Director (IT)",
        "description": "<p>Federal government IT role. Competitive exam based recruitment.</p>",
        "source": "FPSC",
        "cities": ["Islamabad"],
        "job_type": "government",
        "skills": ["IT Management", "Networking"],
        "tags": ["Government", "IT"],
        "salary_range": "BPS-17",
        "experience_required": "2 year(s)",
        "education_required": "Master's in CS / IT",
        "days_ago": 5,
        "deadline_days": 14,
    },
    {
        "title": "Frontend Developer (React / Next.js)",
        "description": "<p>Ship polished product UI for global clients.</p>",
        "source": "10Pearls",
        "cities": ["Karachi"],
        "job_type": "private",
        "skills": ["React", "Next.js", "TypeScript"],
        "tags": ["Software Engineering"],
        "salary_range": "PKR 180,000 – 300,000",
        "experience_required": "3 year(s)",
        "education_required": "BS CS",
        "days_ago": 1,
        "deadline_days": 30,
    },
]


def seed_if_empty() -> None:
    db = SessionLocal()
    try:
        ensure_admin_user(db)

        ensure_default_pages(db)
        ensure_default_tools(db)
        sync_local_core_pages_once(db)
        sync_core_page_content_v2(db)
        sync_core_page_content_v3(db)
        sync_privacy_adsense_disclosures_v4(db)
        sync_expanded_tools_core_pages_v5(db)
        sync_student_api_core_pages_v6(db)
        sync_homepage_branding_seo_v1(db)
        ensure_default_taxonomy(db)

        count = db.execute(select(func.count()).select_from(Job)).scalar() or 0
        if count > 0:
            db.commit()
            logger.info("seed skipped — jobs already present count=%s", count)
            return

        now = datetime.utcnow()
        for item in SEED_JOBS:
            job_id = str(uuid4())
            published = now - timedelta(days=item["days_ago"])
            deadline = now + timedelta(days=item["deadline_days"])
            title = item["title"]
            job = Job(
                id=job_id,
                slug=slugify(title),
                title=title,
                description=item["description"],
                published_date=published,
                deadline_date=deadline,
                salary_range=item.get("salary_range"),
                source=item.get("source"),
                reference_url=None,
                application_url=None,
                experience_required=item.get("experience_required"),
                education_required=item.get("education_required"),
                skills=item.get("skills") or [],
                job_type=item.get("job_type"),
                cities=item.get("cities") or [],
                tags=item.get("tags") or [],
                keywords=", ".join(item.get("tags") or []),
                created_at=published,
                updated_at=published,
            )
            db.add(job)
            upsert_job_seo(db, job)
            db.add(
                JobQnA(
                    id=str(uuid4()),
                    job_id=job_id,
                    question="What experience is required?",
                    answer=item.get("experience_required") or "See job description.",
                    source="seed",
                    youtube_url="https://www.youtube.com/results?search_query="
                    + title.replace(" ", "+")
                    + "+interview",
                    youtube_title=f"Interview tips — {title}",
                    created_at=now,
                )
            )
            db.add(
                JobQnA(
                    id=str(uuid4()),
                    job_id=job_id,
                    question="How should I prepare?",
                    answer="Review the listed skills and practice common interview questions for this role.",
                    source="seed",
                    youtube_url=None,
                    youtube_title=None,
                    created_at=now,
                )
            )

        db.flush()
        ensure_default_taxonomy(db)
        sync_taxonomy_pages_v1(db)
        sync_directory_page_slugs_v2(db)
        sync_job_directory_pages_v3(db)

        db.commit()
        logger.info("seeded sample jobs count=%s", len(SEED_JOBS))
    except Exception:
        db.rollback()
        logger.exception("seed_if_empty failed")
        raise
    finally:
        db.close()
