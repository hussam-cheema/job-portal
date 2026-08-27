import { expect, test } from "@playwright/test";

const viewports = [
  { name: "phone", width: 390, height: 844 },
  { name: "tablet", width: 820, height: 1180 },
] as const;

const builders = [
  {
    path: "/resume-builder",
    previewTestId: "resume-preview",
    shellTestId: "resume-preview-shell",
    downloadName: "Download Resume as PDF",
  },
  {
    path: "/cover-letter",
    previewTestId: "cover-letter-preview",
    shellTestId: "cover-letter-preview-shell",
    downloadName: "Download Cover Letter as PDF",
  },
] as const;

for (const builder of builders) {
  test(`${builder.path} stacks its building blocks above the preview on desktop`, async ({ page }) => {
    await page.setViewportSize({ width: 1440, height: 1000 });
    await page.goto(builder.path);

    const layout = await page.evaluate(() => {
      const form = document.querySelector<HTMLElement>(".builder-form-stack");
      const preview = document.querySelector<HTMLElement>(".builder-preview-panel");
      if (!form || !preview) return null;

      const formRect = form.getBoundingClientRect();
      const previewRect = preview.getBoundingClientRect();
      return {
        form: {
          bottom: formRect.bottom,
          left: formRect.left,
          right: formRect.right,
        },
        preview: {
          left: previewRect.left,
          right: previewRect.right,
          top: previewRect.top,
        },
      };
    });

    expect(layout).not.toBeNull();
    expect(layout!.preview.top).toBeGreaterThanOrEqual(layout!.form.bottom);
    expect(layout!.preview.left).toBeCloseTo(layout!.form.left, 0);
    expect(layout!.preview.right).toBeCloseTo(layout!.form.right, 0);
  });
}

for (const viewport of viewports) {
  for (const builder of builders) {
    test(`${builder.path} fits the ${viewport.name} viewport without clipping`, async ({ page }) => {
      await page.setViewportSize(viewport);
      await page.goto(builder.path);

      const shell = page.getByTestId(builder.shellTestId);
      const preview = page.getByTestId(builder.previewTestId);
      const downloadButton = page.getByRole("button", { name: builder.downloadName });

      await expect(shell).toBeVisible();
      await expect(preview).toBeVisible();
      await expect(downloadButton).toBeVisible();

      const layout = await page.evaluate(
        ({ shellId, previewId }) => {
          const workspace = document.querySelector<HTMLElement>(".builder-workspace");
          const panel = document.querySelector<HTMLElement>(".builder-preview-panel");
          const shellElement = document.querySelector<HTMLElement>(
            `[data-testid="${shellId}"]`
          );
          const previewElement = document.querySelector<HTMLElement>(
            `[data-testid="${previewId}"]`
          );
          if (!workspace || !panel || !shellElement || !previewElement) return null;

          const box = (element: HTMLElement) => {
            const rect = element.getBoundingClientRect();
            return {
              left: rect.left,
              right: rect.right,
              width: rect.width,
              height: rect.height,
            };
          };

          return {
            viewportWidth: window.innerWidth,
            documentWidth: document.documentElement.scrollWidth,
            documentHeight: document.documentElement.scrollHeight,
            viewportHeight: window.innerHeight,
            workspace: box(workspace),
            panel: box(panel),
            shell: box(shellElement),
            preview: box(previewElement),
          };
        },
        { shellId: builder.shellTestId, previewId: builder.previewTestId }
      );

      expect(layout).not.toBeNull();
      expect(layout!.documentWidth).toBeLessThanOrEqual(layout!.viewportWidth);
      expect(layout!.documentHeight).toBeGreaterThan(layout!.viewportHeight);
      for (const box of [layout!.workspace, layout!.panel, layout!.shell, layout!.preview]) {
        expect(box.left).toBeGreaterThanOrEqual(0);
        expect(box.right).toBeLessThanOrEqual(layout!.viewportWidth + 1);
      }
      expect(layout!.preview.width).toBeLessThanOrEqual(layout!.shell.width);
      expect(layout!.preview.height).toBeLessThanOrEqual(layout!.shell.height);
    });
  }
}
