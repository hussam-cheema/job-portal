import { expect, test } from "@playwright/test";
import { readFile } from "node:fs/promises";

test("image watermark validates files, applies controls, and downloads full-resolution PNG", async ({ page }) => {
  await page.goto("/tools/add-watermark");
  await expect(page.getByRole("heading", { name: "Add Watermark to Image" })).toBeVisible();
  await expect(page.getByText("One image under 10 MB", { exact: false })).toBeVisible();
  const input = page.locator("#watermark-file");
  const error = page.getByTestId("image-watermark").locator("[role=alert]");

  await input.setInputFiles({ name: "unsafe.svg", mimeType: "image/svg+xml", buffer: Buffer.from("<svg><script>alert(1)</script></svg>") });
  await expect(error).toContainText("not allowed");
  await input.setInputFiles({ name: "fake.png", mimeType: "image/png", buffer: Buffer.from("not an image") });
  await expect(error).toContainText("not a valid");
  await input.setInputFiles({ name: "large.png", mimeType: "image/png", buffer: Buffer.alloc(10 * 1024 * 1024) });
  await expect(error).toContainText("smaller than 10 MB");

  const base64 = await page.evaluate(() => {
    const canvas = document.createElement("canvas");
    canvas.width = 600;
    canvas.height = 400;
    const ctx = canvas.getContext("2d")!;
    ctx.fillStyle = "#164ba0";
    ctx.fillRect(0, 0, 600, 400);
    return canvas.toDataURL("image/png").split(",")[1];
  });
  const oversizedDimensions = Buffer.from(base64, "base64");
  oversizedDimensions.writeUInt32BE(10_000, 16);
  oversizedDimensions.writeUInt32BE(10_000, 20);
  await input.setInputFiles({ name: "pixel-bomb.png", mimeType: "image/png", buffer: oversizedDimensions });
  await expect(error).toContainText("12 megapixels");
  await page.getByTestId("watermark-dropzone").dispatchEvent("drop", {
    dataTransfer: await page.evaluateHandle(() => {
      const transfer = new DataTransfer();
      transfer.items.add(new File(["one"], "one.png", { type: "image/png" }));
      transfer.items.add(new File(["two"], "two.png", { type: "image/png" }));
      return transfer;
    }),
  });
  await expect(error).toContainText("only one image");
  await input.setInputFiles({ name: "my photo.png", mimeType: "image/png", buffer: Buffer.from(base64, "base64") });
  const preview = page.getByRole("img", { name: "Watermarked image preview" });
  await expect(preview).toBeVisible();
  await expect(page.getByText("600 × 400 px")).toBeVisible();
  const first = await preview.evaluate((element) => (element as HTMLCanvasElement).toDataURL());
  await page.getByLabel("Watermark text").fill("Copyright 2026");
  await page.getByLabel("Text color").fill("#ffdb00");
  await page.getByLabel("Font size").fill("90");
  await page.getByLabel("Text opacity").fill("35");
  await page.getByRole("button", { name: "Bold text" }).click();
  await page.getByRole("button", { name: "Underline text" }).click();
  await page.getByLabel("Position").selectOption("center");
  await expect(page.getByRole("button", { name: "Bold text" })).toHaveAttribute("aria-pressed", "false");
  await expect(page.getByRole("button", { name: "Underline text" })).toHaveAttribute("aria-pressed", "true");
  await expect.poll(async () => preview.evaluate((element) => (element as HTMLCanvasElement).toDataURL())).not.toBe(first);

  const downloadPromise = page.waitForEvent("download");
  await page.getByRole("button", { name: "Download watermarked PNG" }).click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toBe("my-photo-watermarked.png");
  const output = await readFile(await download.path());
  expect(output.subarray(0, 8).toString("hex")).toBe("89504e470d0a1a0a");
  expect(output.readUInt32BE(16)).toBe(600);
  expect(output.readUInt32BE(20)).toBe(400);
  expect(output.length).toBeGreaterThan(1000);
});

test("watermark editor stays within mobile and tablet viewports", async ({ page }) => {
  for (const width of [360, 390, 768, 1024]) {
    await page.setViewportSize({ width, height: 850 });
    await page.goto("/tools/add-watermark");
    await expect(page.getByRole("button", { name: "Browse image" })).toBeVisible();
    expect(await page.evaluate(() => document.documentElement.scrollWidth <= window.innerWidth + 1)).toBe(true);
  }
});

test("watermark input and control text stays dark on white in both site themes", async ({ page }) => {
  await page.goto("/tools/add-watermark");
  for (const theme of ["dark", "light"]) {
    await page.evaluate((value) => document.documentElement.setAttribute("data-theme", value), theme);
    const colors = await page.evaluate(() => {
      const text = document.querySelector<HTMLInputElement>("#watermark-text")!;
      const select = document.querySelector<HTMLSelectElement>("#watermark-position")!;
      const colorLabel = document.querySelector<HTMLInputElement>("#watermark-color")!.parentElement!.querySelector("span")!;
      const underline = document.querySelector<HTMLButtonElement>('[aria-label="Underline text"]')!;
      return {
        text: getComputedStyle(text).color,
        textBackground: getComputedStyle(text).backgroundColor,
        placeholder: getComputedStyle(text, "::placeholder").color,
        select: getComputedStyle(select).color,
        selectBackground: getComputedStyle(select).backgroundColor,
        colorLabel: getComputedStyle(colorLabel).color,
        underline: getComputedStyle(underline).color,
        underlineBackground: getComputedStyle(underline).backgroundColor,
      };
    });
    expect(colors).toEqual({
      text: "rgb(17, 24, 39)",
      textBackground: "rgb(255, 255, 255)",
      placeholder: "rgb(100, 116, 139)",
      select: "rgb(17, 24, 39)",
      selectBackground: "rgb(255, 255, 255)",
      colorLabel: "rgb(17, 24, 39)",
      underline: "rgb(17, 24, 39)",
      underlineBackground: "rgb(255, 255, 255)",
    });
  }
});
