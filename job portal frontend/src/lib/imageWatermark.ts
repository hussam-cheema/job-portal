export type ImageFormat = "png" | "jpeg" | "webp";
export type WatermarkPosition = "top-left" | "center" | "bottom-right";

export type WatermarkOptions = {
  text: string;
  color: string;
  fontSize: number;
  bold: boolean;
  underline: boolean;
  opacity: number;
  position: WatermarkPosition;
};

export const MAX_IMAGE_BYTES = 10 * 1024 * 1024;
export const MAX_IMAGE_PIXELS = 12_000_000;
const MAX_IMAGE_EDGE = 10_000;

const read16BE = (bytes: Uint8Array, at: number) => (bytes[at] << 8) | bytes[at + 1];
const read16LE = (bytes: Uint8Array, at: number) => bytes[at] | (bytes[at + 1] << 8);
const read24LE = (bytes: Uint8Array, at: number) => bytes[at] | (bytes[at + 1] << 8) | (bytes[at + 2] << 16);
const read32BE = (bytes: Uint8Array, at: number) => ((bytes[at] * 0x1000000) + (bytes[at + 1] << 16) + (bytes[at + 2] << 8) + bytes[at + 3]) >>> 0;

function imageHeader(bytes: Uint8Array): { format: ImageFormat; width: number; height: number } | null {
  if (bytes.length >= 24 && [137, 80, 78, 71, 13, 10, 26, 10].every((value, index) => bytes[index] === value)
    && String.fromCharCode(...bytes.subarray(12, 16)) === "IHDR" && read32BE(bytes, 8) === 13) {
    let at = 8;
    while (at + 12 <= bytes.length) {
      const length = read32BE(bytes, at);
      if (length > bytes.length - at - 12) return null;
      const chunk = String.fromCharCode(...bytes.subarray(at + 4, at + 8));
      if (chunk === "acTL") return null; // APNG should not silently lose its animation.
      if (chunk === "IDAT") break;
      at += length + 12;
    }
    return { format: "png", width: read32BE(bytes, 16), height: read32BE(bytes, 20) };
  }
  if (bytes.length >= 30 && bytes[0] === 0xff && bytes[1] === 0xd8) {
    let at = 2;
    while (at + 9 < bytes.length) {
      if (bytes[at] !== 0xff) return null;
      while (bytes[at] === 0xff) at++;
      const marker = bytes[at++];
      if (marker === 0xd9 || marker === 0xda) return null;
      if (marker === 0x01 || (marker >= 0xd0 && marker <= 0xd8)) continue;
      const length = read16BE(bytes, at);
      if (length < 2 || at + length > bytes.length) return null;
      if ([0xc0, 0xc1, 0xc2, 0xc3, 0xc5, 0xc6, 0xc7, 0xc9, 0xca, 0xcb, 0xcd, 0xce, 0xcf].includes(marker)) {
        if (length < 7) return null;
        return { format: "jpeg", width: read16BE(bytes, at + 5), height: read16BE(bytes, at + 3) };
      }
      at += length;
    }
  }
  if (bytes.length >= 30 && String.fromCharCode(...bytes.subarray(0, 4)) === "RIFF"
    && String.fromCharCode(...bytes.subarray(8, 12)) === "WEBP") {
    const chunk = String.fromCharCode(...bytes.subarray(12, 16));
    if (chunk === "VP8X") {
      if (bytes[20] & 0x02) return null; // Animated WebP must not be flattened to one frame.
      return { format: "webp", width: read24LE(bytes, 24) + 1, height: read24LE(bytes, 27) + 1 };
    }
    if (chunk === "VP8L" && bytes[20] === 0x2f) return {
      format: "webp",
      width: 1 + bytes[21] + ((bytes[22] & 0x3f) << 8),
      height: 1 + (bytes[22] >> 6) + (bytes[23] << 2) + ((bytes[24] & 0x0f) << 10),
    };
    if (chunk === "VP8 " && bytes[23] === 0x9d && bytes[24] === 0x01 && bytes[25] === 0x2a) {
      return { format: "webp", width: read16LE(bytes, 26) & 0x3fff, height: read16LE(bytes, 28) & 0x3fff };
    }
  }
  return null;
}

export async function validateImage(file: File): Promise<{ format: ImageFormat; width: number; height: number }> {
  if (file.size === 0) throw new Error("This image is empty. Choose another file.");
  if (file.size >= MAX_IMAGE_BYTES) throw new Error("Choose an image smaller than 10 MB.");
  const extension = file.name.split(".").pop()?.toLowerCase();
  const expected = extension === "jpg" || extension === "jpeg" ? "jpeg" : extension;
  if (!(["png", "jpeg", "webp"] as Array<string | undefined>).includes(expected)) {
    throw new Error("This file type is not allowed. Choose a PNG, JPEG or WebP image.");
  }
  const bytes = new Uint8Array(await file.arrayBuffer());
  const header = imageHeader(bytes);
  const mime = { png: "image/png", jpeg: "image/jpeg", webp: "image/webp" };
  if (!header || header.format !== expected || (file.type && file.type !== mime[header.format])) {
    throw new Error("This file is not a valid PNG, JPEG or WebP image.");
  }
  if (header.width < 64 || header.height < 64 || header.width > MAX_IMAGE_EDGE || header.height > MAX_IMAGE_EDGE
    || header.width * header.height > MAX_IMAGE_PIXELS) {
    throw new Error("Choose an image between 64 pixels and 12 megapixels, with no side over 10,000 pixels.");
  }
  return header;
}

export function paintWatermark(canvas: HTMLCanvasElement, source: CanvasImageSource, width: number, height: number, options: WatermarkOptions) {
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const context = canvas.getContext("2d", { alpha: true });
  if (!context) throw new Error("Your browser could not prepare the image editor.");
  context.clearRect(0, 0, width, height);
  context.drawImage(source, 0, 0, width, height);
  const text = options.text.trim();
  if (!text) return;
  const padding = Math.max(8, Math.round(Math.min(width, height) * 0.035));
  const maxWidth = width - 2 * padding;
  const size = Math.max(6, Math.min(options.fontSize * width / 1000, height * .22));
  context.save();
  context.globalAlpha = Math.max(.01, Math.min(1, options.opacity / 100));
  context.font = `${options.bold ? 700 : 400} ${size}px Arial, sans-serif`;
  context.textBaseline = "alphabetic";
  context.fillStyle = options.color;
  context.strokeStyle = options.color;
  const measuredWidth = context.measureText(text).width;
  const drawnWidth = Math.min(maxWidth, measuredWidth);
  const x = options.position === "top-left" ? padding : options.position === "center" ? (width - drawnWidth) / 2 : width - padding - drawnWidth;
  const baseline = options.position === "top-left" ? padding + size : options.position === "center" ? (height + size * .35) / 2 : height - padding - Math.max(2, size * .1);
  context.fillText(text, x, baseline, maxWidth);
  if (options.underline) {
    const underlineY = Math.min(height - padding * .45, baseline + size * .11);
    context.lineWidth = Math.max(1, size * .055);
    context.beginPath();
    context.moveTo(x, underlineY);
    context.lineTo(x + drawnWidth, underlineY);
    context.stroke();
  }
  context.restore();
}
