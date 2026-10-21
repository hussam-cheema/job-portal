import { NextResponse, type NextRequest } from "next/server";

const legacyRedirects: Record<string, string> = {
  "/&": "/",
  "/%26": "/",
  "/$": "/",
  "/%24": "/",
  "/categories-office": "/categories/office",
  "/categories/accounting": "/categories/accounting-finance",
  "/categories/fia-jobs": "/jobs-by-categories",
  "/categories/office-jobs": "/categories/office",
  "/categories/pakistan-navy-jobs": "/categories/pakistan-navy",
  "/categories/ppsc-jobs": "/categories/ppsc",
  "/companies/punjab-university": "/companies/cemb",
  "/cover-letter": "/tools/cover-letter",
  "/jobs/assistant-manager-jobs-2026-public-sector-organization":
    "/jobs/assistant-manager-jobs-2026-public-sector-organization-nescompaec",
  "/jobs/public-sector-organization-jobs-2026-nescom-job-2026":
    "/jobs/assistant-manager-jobs-2026-public-sector-organization-nescompaec",
  "/jobs/sindh-information-department-jobs-2026-situations-vacant-44-posts":
    "/jobs/sindh-information-department-government-jobs-2026-situations-vacant-44-posts",
  "/resume-builder": "/tools/resume-builder",
};

export function middleware(request: NextRequest) {
  const pathname = request.nextUrl.pathname;
  const normalizedPath =
    pathname === "/" ? pathname : pathname.replace(/\/+$/, "");
  const destination =
    legacyRedirects[pathname] ||
    legacyRedirects[normalizedPath];
  if (!destination) return NextResponse.next();

  const response = NextResponse.redirect(
    new URL(destination, request.nextUrl.origin),
    301,
  );
  response.headers.set("Cache-Control", "public, max-age=86400");
  return response;
}

export const config = {
  matcher: ["/((?!api|_next/static|_next/image|favicon.ico).*)"],
};
