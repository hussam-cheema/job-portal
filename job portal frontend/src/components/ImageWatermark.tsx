"use client";

import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { MAX_IMAGE_BYTES, paintWatermark, validateImage, type WatermarkOptions } from "@/lib/imageWatermark";
import styles from "./ImageWatermark.module.css";

type DecodedImage = { source: ImageBitmap | HTMLImageElement; width: number; height: number; dispose: () => void };

const initialOptions: WatermarkOptions = {
  text: "Your watermark",
  color: "#ffffff",
  fontSize: 64,
  bold: true,
  underline: false,
  opacity: 70,
  position: "bottom-right",
};

async function decodeImage(file: File): Promise<DecodedImage> {
  if (typeof createImageBitmap === "function") {
    const bitmap = await createImageBitmap(file);
    return { source: bitmap, width: bitmap.width, height: bitmap.height, dispose: () => bitmap.close() };
  }
  const url = URL.createObjectURL(file);
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    return { source: image, width: image.naturalWidth, height: image.naturalHeight, dispose: () => URL.revokeObjectURL(url) };
  } catch (error) {
    URL.revokeObjectURL(url);
    throw error;
  }
}

export function ImageWatermark() {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const fileRef = useRef<HTMLInputElement>(null);
  const imageRef = useRef<DecodedImage | null>(null);
  const requestRef = useRef(0);
  const [imageInfo, setImageInfo] = useState<{ name: string; width: number; height: number } | null>(null);
  const [options, setOptions] = useState<WatermarkOptions>(initialOptions);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const [isDragging, setIsDragging] = useState(false);

  useEffect(() => () => {
    requestRef.current++;
    imageRef.current?.dispose();
    imageRef.current = null;
  }, []);

  useEffect(() => {
    if (!imageInfo || !imageRef.current || !canvasRef.current) return;
    try {
      const image = imageRef.current;
      paintWatermark(canvasRef.current, image.source, image.width, image.height, options);
      setError("");
    } catch {
      setError("Your browser could not draw this image. Please try a different file.");
    }
  }, [imageInfo, options]);

  async function selectFiles(files: FileList | File[] | null) {
    const request = ++requestRef.current;
    imageRef.current?.dispose();
    imageRef.current = null;
    setImageInfo(null);
    setError("");
    if (!files?.length) return;
    if (files.length !== 1) {
      setError("Choose only one image at a time.");
      return;
    }
    const file = files[0];
    if (file.size >= MAX_IMAGE_BYTES) {
      setError("Choose an image smaller than 10 MB.");
      return;
    }
    setBusy(true);
    try {
      const header = await validateImage(file);
      if (request !== requestRef.current) return;
      const decoded = await decodeImage(file);
      if (request !== requestRef.current) {
        decoded.dispose();
        return;
      }
      const dimensionsMatch = (decoded.width === header.width && decoded.height === header.height)
        || (header.format === "jpeg" && decoded.width === header.height && decoded.height === header.width);
      if (!dimensionsMatch) {
        decoded.dispose();
        throw new Error("This image has inconsistent dimensions and cannot be used.");
      }
      imageRef.current = decoded;
      setImageInfo({ name: file.name, width: decoded.width, height: decoded.height });
    } catch (cause) {
      if (request === requestRef.current) setError(cause instanceof Error ? cause.message : "This image could not be opened.");
    } finally {
      if (request === requestRef.current) setBusy(false);
    }
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    void selectFiles(event.target.files);
    event.target.value = "";
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    void selectFiles(event.dataTransfer.files);
  }

  function update<K extends keyof WatermarkOptions>(key: K, value: WatermarkOptions[K]) {
    setOptions((current) => ({ ...current, [key]: value }));
  }

  async function download() {
    const canvas = canvasRef.current;
    if (!canvas || !imageInfo) return;
    if (!options.text.trim()) {
      setError("Enter watermark text before downloading.");
      return;
    }
    try {
      const blob = await new Promise<Blob>((resolve, reject) => canvas.toBlob((output) => output ? resolve(output) : reject(new Error("The image could not be exported.")), "image/png"));
      const url = URL.createObjectURL(blob);
      const link = document.createElement("a");
      link.href = url;
      link.download = `${imageInfo.name.replace(/\.[^.]+$/, "").replace(/[^a-zA-Z0-9._-]/g, "-").slice(0, 80) || "image"}-watermarked.png`;
      document.body.appendChild(link);
      link.click();
      link.remove();
      window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
    } catch {
      setError("The download failed. Try again or choose a smaller image.");
    }
  }

  return <section className={styles.shell} data-testid="image-watermark">
    <div className={styles.intro}>
      <p className="tool-kicker">Private, in-browser image editor</p>
      <h2>Add your text watermark</h2>
      <p>Upload one image, customize the text and download a full-size PNG. Your image stays on your device and is never uploaded to our server.</p>
    </div>
    <div className={styles.layout}>
      <div className={styles.controls}>
        <div data-testid="watermark-dropzone" className={`${styles.dropzone} ${isDragging ? styles.dragging : ""}`} onDragEnter={(event) => { event.preventDefault(); setIsDragging(true); }} onDragOver={(event) => event.preventDefault()} onDragLeave={(event) => { event.preventDefault(); setIsDragging(false); }} onDrop={onDrop}>
          <strong>Choose an image</strong>
          <p>PNG, JPEG or WebP. One image under 10 MB, up to 12 megapixels. Animated files are not supported.</p>
          <input ref={fileRef} id="watermark-file" className={styles.visuallyHidden} type="file" accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp" onChange={onFileChange} />
          <button type="button" className="btn btn-ghost" onClick={() => fileRef.current?.click()}>Browse image</button>
          <small>Or drag and drop one image here.</small>
          {imageInfo && <p className={styles.fileInfo}>{imageInfo.name} · {imageInfo.width} × {imageInfo.height} px</p>}
        </div>
        <label className={styles.field} htmlFor="watermark-text">Watermark text
          <input id="watermark-text" type="text" maxLength={100} value={options.text} onChange={(event) => update("text", event.target.value)} placeholder="Type your watermark" />
        </label>
        <div className={styles.twoColumns}>
          <label className={styles.field} htmlFor="watermark-color">Text color
            <span className={styles.colorRow}><input id="watermark-color" aria-label="Text color" type="color" value={options.color} onChange={(event) => update("color", event.target.value)} /><span>{options.color.toUpperCase()}</span></span>
          </label>
          <label className={styles.field} htmlFor="watermark-position">Position
            <select id="watermark-position" value={options.position} onChange={(event) => update("position", event.target.value as WatermarkOptions["position"])}><option value="bottom-right">Bottom right</option><option value="center">Center</option><option value="top-left">Top left</option></select>
          </label>
        </div>
        <label className={styles.field} htmlFor="watermark-size">Font size <span className={styles.value}>{options.fontSize}</span>
          <input id="watermark-size" type="range" min="12" max="144" step="1" value={options.fontSize} onChange={(event) => update("fontSize", Number(event.target.value))} />
          <small>Scales to the original image width.</small>
        </label>
        <label className={styles.field} htmlFor="watermark-opacity">Text opacity <span className={styles.value}>{options.opacity}%</span>
          <input id="watermark-opacity" type="range" min="1" max="100" step="1" value={options.opacity} onChange={(event) => update("opacity", Number(event.target.value))} />
        </label>
        <div className={styles.formatButtons} aria-label="Text formatting">
          <button type="button" aria-label="Bold text" aria-pressed={options.bold} className={options.bold ? styles.active : ""} onClick={() => update("bold", !options.bold)}><strong>B</strong> Bold</button>
          <button type="button" aria-label="Underline text" aria-pressed={options.underline} className={options.underline ? styles.active : ""} onClick={() => update("underline", !options.underline)}><u>U</u> Underline</button>
        </div>
        {error && <p className={styles.error} role="alert">{error}</p>}
      </div>
      <div className={styles.previewPanel}>
        <div className={styles.previewHeading}><div><h3>Live preview</h3><p>Download keeps the original image dimensions.</p></div>{imageInfo && <span>{imageInfo.width} × {imageInfo.height}</span>}</div>
        <div className={styles.previewArea}>{imageInfo ? <canvas ref={canvasRef} role="img" aria-label="Watermarked image preview" /> : <div className={styles.placeholder}>{busy ? "Opening image…" : "Your image preview will appear here"}</div>}</div>
        <button type="button" className="btn btn-primary" disabled={!imageInfo || busy || !options.text.trim()} onClick={() => void download()}>Download watermarked PNG</button>
        <p className={styles.privacy}>We decode your image locally. The PNG export removes embedded metadata, including location data. Review the result before sharing it.</p>
      </div>
    </div>
  </section>;
}
