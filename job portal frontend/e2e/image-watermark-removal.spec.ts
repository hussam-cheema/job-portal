import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

type GeneratedImage = {
  base64: string;
  redPixels: number;
};

async function watermarkedImage(
  page: import("@playwright/test").Page,
  format: "png" | "jpeg" | "webp",
  background: string,
  watermark: "site" | "generic" | "none" = "site",
): Promise<GeneratedImage> {
  return page.evaluate(({ format, background, watermark }) => {
    const canvas = document.createElement("canvas");
    canvas.width = 640;
    canvas.height = 420;
    const context = canvas.getContext("2d")!;
    context.fillStyle = background;
    context.fillRect(0, 0, canvas.width, canvas.height);
    context.fillStyle = "#172033";
    context.font = "bold 22px Arial";
    context.fillText("ADVERTISEMENT FOR VACANCIES", 40, 60);
    context.font = "16px Arial";
    for (let index = 0; index < 9; index += 1) {
      context.fillText(
        "Qualification and experience requirements must be verified before applying.",
        40,
        100 + index * 28,
      );
    }
    if (watermark === "site") {
      const font = "bold 48px Arial";
      context.font = font;
      const text = "Pakistan Jobs Market";
      const measured = context.measureText(text).width;
      const x = (canvas.width - measured) / 2;
      const y = canvas.height / 2;
      context.fillStyle = "rgba(0, 0, 0, 0.196)";
      context.beginPath();
      context.roundRect(x - 10, y - 38, measured + 20, 58, 8);
      context.fill();
      context.strokeStyle = "rgba(255, 255, 255, 0.475)";
      context.lineWidth = 2;
      context.strokeText(text, x, y);
      context.fillStyle = "rgba(255, 0, 0, 0.318)";
      context.fillText(text, x, y);
    } else if (watermark === "generic") {
      context.save();
      context.translate(canvas.width / 2, canvas.height / 2);
      context.rotate(-0.12);
      context.textAlign = "center";
      context.font = "bold 54px Arial";
      context.fillStyle = "rgba(255, 255, 255, 0.82)";
      context.fillText("SAMPLE", 0, -10);
      context.font = "bold 28px Arial";
      context.fillText("WATERMARK", 0, 30);
      context.restore();
    }
    const output = canvas.toDataURL(`image/${format}`, 0.92);
    const source = context.getImageData(0, 0, canvas.width, canvas.height);
    let redPixels = 0;
    for (let y = Math.floor(canvas.height * 0.3); y < canvas.height * 0.7; y += 1) {
      for (let x = 0; x < canvas.width; x += 1) {
        const offset = (y * canvas.width + x) * 4;
        if (
          source.data[offset] > 105
          && source.data[offset] - Math.max(source.data[offset + 1], source.data[offset + 2]) > 18
        ) {
          redPixels += 1;
        }
      }
    }
    return { base64: output.split(",")[1], redPixels };
  }, { format, background, watermark });
}

async function countPreviewRedPixels(
  image: import("@playwright/test").Locator,
): Promise<number> {
  return image.evaluate(async (element) => {
    const source = element as HTMLImageElement;
    await source.decode();
    const canvas = document.createElement("canvas");
    canvas.width = source.naturalWidth;
    canvas.height = source.naturalHeight;
    const context = canvas.getContext("2d")!;
    context.drawImage(source, 0, 0);
    const pixels = context.getImageData(0, 0, canvas.width, canvas.height).data;
    let count = 0;
    for (let y = Math.floor(canvas.height * 0.3); y < canvas.height * 0.7; y += 1) {
      for (let x = 0; x < canvas.width; x += 1) {
        const offset = (y * canvas.width + x) * 4;
        if (
          pixels[offset] > 105
          && pixels[offset] - Math.max(pixels[offset + 1], pixels[offset + 2]) > 18
        ) {
          count += 1;
        }
      }
    }
    return count;
  });
}

test("removes the site watermark from three images and downloads a cleaned PNG", async ({ page }) => {
  const analyticsOpen = page.waitForRequest((request) =>
    request.url().endsWith("/api/analytics/visit")
      && request.postData()?.includes("/tools/remove-watermark") === true,
  );
  const analyticsInteraction = page.waitForRequest((request) =>
    request.url().endsWith("/api/tools/remove-watermark/usage")
      && request.method() === "POST",
  );
  await page.goto("/tools/remove-watermark");
  await expect(page.getByRole("heading", { name: "Remove Watermark from Image" })).toBeVisible();
  await analyticsOpen;

  const png = await watermarkedImage(page, "png", "#ffffff");
  const jpeg = await watermarkedImage(page, "jpeg", "#eef4fb");
  const webp = await watermarkedImage(page, "webp", "#fff7df");
  expect(png.redPixels).toBeGreaterThan(500);
  expect(jpeg.redPixels).toBeGreaterThan(500);
  expect(webp.redPixels).toBeGreaterThan(500);

  const input = page.locator("#watermark-removal-files");
  await input.setInputFiles([
    { name: "notice-one.png", mimeType: "image/png", buffer: Buffer.from(png.base64, "base64") },
    { name: "notice-two.jpg", mimeType: "image/jpeg", buffer: Buffer.from(jpeg.base64, "base64") },
    { name: "notice-three.webp", mimeType: "image/webp", buffer: Buffer.from(webp.base64, "base64") },
  ]);
  await analyticsInteraction;

  const results = page.getByTestId("image-watermark-removal").locator("article");
  await expect(results).toHaveCount(3);
  await expect(page.getByText("Watermark removed", { exact: false })).toHaveCount(3);
  const previews = results.locator("img");
  for (let index = 0; index < 3; index += 1) {
    expect(await countPreviewRedPixels(previews.nth(index))).toBeLessThan(40);
  }

  const downloadPromise = page.waitForEvent("download");
  await results.first().getByRole("button", { name: "Download cleaned PNG" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("notice-one-watermark-removed.png");
  const output = await readFile(await download.path());
  expect(output.subarray(0, 8).toString("hex")).toBe("89504e470d0a1a0a");
  expect(output.readUInt32BE(16)).toBe(640);
  expect(output.readUInt32BE(20)).toBe(420);
});

test("rejects more than three files and leaves an unwatermarked image unchanged", async ({ page }) => {
  await page.goto("/tools/remove-watermark");
  const input = page.locator("#watermark-removal-files");
  const source = await watermarkedImage(page, "png", "#ffffff", "none");
  const file = {
    name: "plain.png",
    mimeType: "image/png",
    buffer: Buffer.from(source.base64, "base64"),
  };
  const alert = page.getByTestId("image-watermark-removal").locator("[role=alert]");

  await input.setInputFiles([file, file, file, file]);
  await expect(alert).toContainText("no more than 3");
  await input.setInputFiles(file);
  await expect(alert).toContainText("No site watermark was detected automatically");
  await expect(page.getByText("No site watermark detected")).toBeVisible();
  expect(await countPreviewRedPixels(
    page.getByTestId("image-watermark-removal").locator("article img"),
  )).toBe(source.redPixels);
});

test("manual brush removes a non-site watermark", async ({ page }) => {
  await page.goto("/tools/remove-watermark");
  const generic = await watermarkedImage(page, "png", "#164b6f", "generic");
  await page.locator("#watermark-removal-files").setInputFiles({
    name: "generic-watermark.png",
    mimeType: "image/png",
    buffer: Buffer.from(generic.base64, "base64"),
  });
  await expect(page.getByText("No site watermark detected")).toBeVisible();
  await page.getByRole("button", { name: "Mark watermark manually" }).click();

  const canvas = page.getByLabel("Paint over the watermark to remove");
  const bounds = await canvas.boundingBox();
  expect(bounds).not.toBeNull();
  for (const yRatio of [0.44, 0.48, 0.52, 0.56, 0.6]) {
    await page.mouse.move(bounds!.x + bounds!.width * 0.2, bounds!.y + bounds!.height * yRatio);
    await page.mouse.down();
    await page.mouse.move(bounds!.x + bounds!.width * 0.8, bounds!.y + bounds!.height * yRatio, {
      steps: 12,
    });
    await page.mouse.up();
  }
  await page.getByRole("button", { name: "Remove marked watermark" }).click();
  await expect(page.getByText("Manually removed", { exact: false })).toBeVisible();
});

test("watermark removal stays within mobile and tablet viewports", async ({ page }) => {
  for (const width of [360, 768, 1024]) {
    await page.setViewportSize({ width, height: 850 });
    await page.goto("/tools/remove-watermark");
    await expect(page.getByRole("button", { name: "Browse images" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  }
});

test("browse button and drop-zone heading keep visible contrast in both themes", async ({ page }) => {
  await page.goto("/tools/remove-watermark");
  const button = page.getByRole("button", { name: "Browse images" });
  const heading = page.getByText("Choose 1 to 3 images", { exact: true });
  for (const theme of ["dark", "light"]) {
    await page.evaluate((value) => document.documentElement.setAttribute("data-theme", value), theme);
    const styles = await button.evaluate((element) => {
      const buttonStyle = getComputedStyle(element);
      const dropzone = element.closest("[data-testid=watermark-removal-dropzone]")!;
      const headingElement = dropzone.querySelector("strong")!;
      return {
        buttonBackground: buttonStyle.backgroundColor,
        buttonColor: buttonStyle.color,
        headingColor: getComputedStyle(headingElement).color,
        dropzoneBackground: getComputedStyle(dropzone).backgroundColor,
      };
    });
    expect(styles.buttonBackground).not.toBe("rgba(0, 0, 0, 0)");
    expect(styles.buttonColor).toBe("rgb(255, 255, 255)");
    expect(styles.headingColor).not.toBe(styles.dropzoneBackground);
    await expect(button).toBeVisible();
    await expect(heading).toBeVisible();
  }
});
