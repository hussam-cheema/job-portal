"use client";

import {
  useEffect,
  useRef,
  useState,
  type ChangeEvent,
  type DragEvent,
  type PointerEvent as ReactPointerEvent,
} from "react";
import { MAX_IMAGE_BYTES, validateImage } from "@/lib/imageWatermark";
import {
  MAX_WATERMARK_REMOVAL_IMAGES,
  removeMaskedWatermarkPixels,
  removeSiteWatermark,
  type WatermarkBounds,
} from "@/lib/imageWatermarkRemoval";
import styles from "./ImageWatermarkRemoval.module.css";

type ProcessedImage = {
  id: string;
  file: File;
  name: string;
  width: number;
  height: number;
  originalUrl: string;
  url: string;
  blob: Blob;
  detected: boolean;
  manual: boolean;
  repairedPixels: number;
  bounds: WatermarkBounds | null;
};

type DecodedImage = {
  source: ImageBitmap | HTMLImageElement;
  width: number;
  height: number;
  dispose: () => void;
};

async function decodeImage(file: File): Promise<DecodedImage> {
  if (typeof createImageBitmap === "function") {
    const bitmap = await createImageBitmap(file);
    return {
      source: bitmap,
      width: bitmap.width,
      height: bitmap.height,
      dispose: () => bitmap.close(),
    };
  }
  const url = URL.createObjectURL(file);
  try {
    const image = new Image();
    image.src = url;
    await image.decode();
    return {
      source: image,
      width: image.naturalWidth,
      height: image.naturalHeight,
      dispose: () => URL.revokeObjectURL(url),
    };
  } catch (error) {
    URL.revokeObjectURL(url);
    throw error;
  }
}

function safeFilename(value: string) {
  return (
    value
      .replace(/\.[^.]+$/, "")
      .replace(/[^a-zA-Z0-9._-]/g, "-")
      .slice(0, 80) || "image"
  );
}

export function ImageWatermarkRemoval() {
  const fileRef = useRef<HTMLInputElement>(null);
  const urlsRef = useRef<string[]>([]);
  const requestRef = useRef(0);
  const manualSourceRef = useRef<HTMLImageElement | null>(null);
  const manualCanvasRef = useRef<HTMLCanvasElement | null>(null);
  const drawingRef = useRef(false);
  const lastDrawPointRef = useRef<{ x: number; y: number } | null>(null);
  const [images, setImages] = useState<ProcessedImage[]>([]);
  const [busy, setBusy] = useState(false);
  const [manualBusy, setManualBusy] = useState(false);
  const [editingId, setEditingId] = useState<string | null>(null);
  const [manualBrushSize, setManualBrushSize] = useState(28);
  const [progress, setProgress] = useState("");
  const [error, setError] = useState("");
  const [isDragging, setIsDragging] = useState(false);

  function revokeImages() {
    urlsRef.current.forEach((url) => URL.revokeObjectURL(url));
    urlsRef.current = [];
  }

  useEffect(() => () => {
    requestRef.current += 1;
    revokeImages();
  }, []);

  useEffect(() => {
    const source = manualSourceRef.current;
    const canvas = manualCanvasRef.current;
    if (!editingId || !source || !canvas) return;
    canvas.width = source.naturalWidth;
    canvas.height = source.naturalHeight;
    canvas.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
    drawingRef.current = false;
    lastDrawPointRef.current = null;
  }, [editingId]);

  async function processFiles(files: FileList | File[] | null) {
    const request = ++requestRef.current;
    revokeImages();
    manualSourceRef.current = null;
    setEditingId(null);
    setImages([]);
    setError("");
    setProgress("");
    if (!files?.length) return;
    const selected = Array.from(files);
    if (selected.length > MAX_WATERMARK_REMOVAL_IMAGES) {
      setError(`Choose no more than ${MAX_WATERMARK_REMOVAL_IMAGES} images at once.`);
      return;
    }

    setBusy(true);
    const processed: ProcessedImage[] = [];
    try {
      for (const [index, file] of selected.entries()) {
        if (request !== requestRef.current) return;
        setProgress(`Processing image ${index + 1} of ${selected.length}…`);
        if (file.size >= MAX_IMAGE_BYTES) {
          throw new Error(`${file.name} is 10 MB or larger. Choose a smaller image.`);
        }
        const header = await validateImage(file);
        const decoded = await decodeImage(file);
        try {
          const dimensionsMatch =
            (decoded.width === header.width && decoded.height === header.height)
            || (
              header.format === "jpeg"
              && decoded.width === header.height
              && decoded.height === header.width
            );
          if (!dimensionsMatch) {
            throw new Error(`${file.name} has inconsistent dimensions.`);
          }
          const canvas = document.createElement("canvas");
          const result = removeSiteWatermark(
            canvas,
            decoded.source,
            decoded.width,
            decoded.height,
          );
          const blob = await new Promise<Blob>((resolve, reject) => {
            canvas.toBlob(
              (output) => output
                ? resolve(output)
                : reject(new Error(`${file.name} could not be exported.`)),
              "image/png",
            );
          });
          if (request !== requestRef.current) return;
          const originalUrl = URL.createObjectURL(file);
          const url = URL.createObjectURL(blob);
          urlsRef.current.push(originalUrl, url);
          processed.push({
            id: crypto.randomUUID(),
            file,
            name: file.name,
            width: decoded.width,
            height: decoded.height,
            originalUrl,
            url,
            blob,
            detected: result.detected,
            manual: false,
            repairedPixels: result.repairedPixels,
            bounds: result.bounds,
          });
          setImages([...processed]);
        } finally {
          decoded.dispose();
        }
        await new Promise((resolve) => window.setTimeout(resolve, 0));
      }
      if (processed.length && processed.every((image) => !image.detected)) {
        setError(
          "No site watermark was detected automatically. Use “Mark watermark manually” "
          + "for another watermark style.",
        );
      }
    } catch (cause) {
      if (request === requestRef.current) {
        setError(cause instanceof Error ? cause.message : "The images could not be processed.");
      }
    } finally {
      if (request === requestRef.current) {
        setBusy(false);
        setProgress("");
      }
    }
  }

  function onFileChange(event: ChangeEvent<HTMLInputElement>) {
    void processFiles(event.target.files);
    event.target.value = "";
  }

  function onDrop(event: DragEvent<HTMLDivElement>) {
    event.preventDefault();
    setIsDragging(false);
    void processFiles(event.dataTransfer.files);
  }

  async function startManualEdit(image: ProcessedImage) {
    setError("");
    setManualBusy(true);
    try {
      const source = new Image();
      source.src = image.originalUrl;
      await source.decode();
      manualSourceRef.current = source;
      setEditingId(image.id);
    } catch {
      setError("This image could not be opened for manual repair.");
    } finally {
      setManualBusy(false);
    }
  }

  function manualPoint(event: ReactPointerEvent<HTMLCanvasElement>) {
    const canvas = event.currentTarget;
    const bounds = canvas.getBoundingClientRect();
    return {
      canvas,
      x: ((event.clientX - bounds.left) / bounds.width) * canvas.width,
      y: ((event.clientY - bounds.top) / bounds.height) * canvas.height,
      scale: canvas.width / bounds.width,
    };
  }

  function drawManualStroke(
    canvas: HTMLCanvasElement,
    from: { x: number; y: number } | null,
    to: { x: number; y: number },
    scale: number,
  ) {
    const context = canvas.getContext("2d");
    if (!context) return;
    context.save();
    context.strokeStyle = "rgba(255, 82, 48, 0.72)";
    context.fillStyle = "rgba(255, 82, 48, 0.72)";
    context.lineCap = "round";
    context.lineJoin = "round";
    context.lineWidth = Math.max(2, manualBrushSize * scale);
    if (from) {
      context.beginPath();
      context.moveTo(from.x, from.y);
      context.lineTo(to.x, to.y);
      context.stroke();
    } else {
      context.beginPath();
      context.arc(to.x, to.y, Math.max(1, manualBrushSize * scale / 2), 0, Math.PI * 2);
      context.fill();
    }
    context.restore();
  }

  function onManualPointerDown(event: ReactPointerEvent<HTMLCanvasElement>) {
    if (manualBusy) return;
    event.preventDefault();
    event.currentTarget.setPointerCapture(event.pointerId);
    const point = manualPoint(event);
    drawingRef.current = true;
    lastDrawPointRef.current = { x: point.x, y: point.y };
    drawManualStroke(point.canvas, null, point, point.scale);
  }

  function onManualPointerMove(event: ReactPointerEvent<HTMLCanvasElement>) {
    if (!drawingRef.current) return;
    event.preventDefault();
    const point = manualPoint(event);
    drawManualStroke(point.canvas, lastDrawPointRef.current, point, point.scale);
    lastDrawPointRef.current = { x: point.x, y: point.y };
  }

  function onManualPointerUp(event: ReactPointerEvent<HTMLCanvasElement>) {
    drawingRef.current = false;
    lastDrawPointRef.current = null;
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  }

  function clearManualMask() {
    const canvas = manualCanvasRef.current;
    if (!canvas) return;
    canvas.getContext("2d")?.clearRect(0, 0, canvas.width, canvas.height);
  }

  async function applyManualRemoval(image: ProcessedImage) {
    const source = manualSourceRef.current;
    const maskCanvas = manualCanvasRef.current;
    if (!source || !maskCanvas) return;
    const maskData = maskCanvas.getContext("2d", { willReadFrequently: true })
      ?.getImageData(0, 0, maskCanvas.width, maskCanvas.height);
    if (!maskData) {
      setError("The manual watermark selection could not be read.");
      return;
    }
    const mask = new Uint8Array(image.width * image.height);
    let selectedPixels = 0;
    for (let index = 0; index < mask.length; index += 1) {
      if (maskData.data[index * 4 + 3] > 12) {
        mask[index] = 1;
        selectedPixels += 1;
      }
    }
    if (!selectedPixels) {
      setError("Paint over the watermark before applying manual removal.");
      return;
    }

    setManualBusy(true);
    setError("");
    try {
      const canvas = document.createElement("canvas");
      canvas.width = image.width;
      canvas.height = image.height;
      const context = canvas.getContext("2d", { willReadFrequently: true });
      if (!context) throw new Error("Your browser could not prepare the repair.");
      context.drawImage(source, 0, 0, image.width, image.height);
      const imageData = context.getImageData(0, 0, image.width, image.height);
      const result = removeMaskedWatermarkPixels(imageData, mask);
      if (!result.detected) throw new Error("The selected area could not be repaired.");
      context.putImageData(imageData, 0, 0);
      const blob = await new Promise<Blob>((resolve, reject) => {
        canvas.toBlob(
          (output) => output
            ? resolve(output)
            : reject(new Error("The repaired image could not be exported.")),
          "image/png",
        );
      });
      const url = URL.createObjectURL(blob);
      urlsRef.current.push(url);
      setImages((current) => current.map((item) => (
        item.id === image.id
          ? {
            ...item,
            url,
            blob,
            detected: true,
            manual: true,
            repairedPixels: result.repairedPixels,
            bounds: result.bounds,
          }
          : item
      )));
      setEditingId(null);
      manualSourceRef.current = null;
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "Manual removal failed.");
    } finally {
      setManualBusy(false);
    }
  }

  function downloadImage(image: ProcessedImage) {
    const url = URL.createObjectURL(image.blob);
    const link = document.createElement("a");
    link.href = url;
    link.download = `${safeFilename(image.name)}-watermark-removed.png`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 30_000);
  }

  function clearAll() {
    requestRef.current += 1;
    revokeImages();
    manualSourceRef.current = null;
    setEditingId(null);
    setImages([]);
    setBusy(false);
    setProgress("");
    setError("");
  }

  return (
    <section className={styles.shell} data-testid="image-watermark-removal">
      <div className={styles.intro}>
        <p className="tool-kicker">Private, in-browser image repair</p>
        <h2>Remove a watermark from your image</h2>
        <p>
          Upload up to three PNG, JPEG, or WebP images. The editor removes the
          Pakistan Jobs Market watermark automatically. For any other watermark,
          paint over it with the repair brush and apply local content-aware fill.
        </p>
      </div>

      <div
        data-testid="watermark-removal-dropzone"
        className={`${styles.dropzone} ${isDragging ? styles.dragging : ""}`}
        onDragEnter={(event) => {
          event.preventDefault();
          setIsDragging(true);
        }}
        onDragOver={(event) => event.preventDefault()}
        onDragLeave={(event) => {
          event.preventDefault();
          setIsDragging(false);
        }}
        onDrop={onDrop}
      >
        <strong>Choose 1 to 3 images</strong>
        <p>
          Each image must be under 10 MB and no larger than 12 megapixels.
          Animated files and SVG are not accepted.
        </p>
        <input
          ref={fileRef}
          id="watermark-removal-files"
          className={styles.visuallyHidden}
          type="file"
          multiple
          accept=".png,.jpg,.jpeg,.webp,image/png,image/jpeg,image/webp"
          onChange={onFileChange}
        />
        <div className={styles.actions}>
          <button
            type="button"
            className={styles.browseButton}
            onClick={() => fileRef.current?.click()}
            disabled={busy}
          >
            Browse images
          </button>
          {images.length > 0 && (
            <button type="button" className={styles.clearButton} onClick={clearAll}>
              Clear all
            </button>
          )}
        </div>
        <small>Or drag and drop up to three images here.</small>
        {progress && <p className={styles.progress} role="status">{progress}</p>}
      </div>

      {error && <p className={styles.error} role="alert">{error}</p>}

      {images.length > 0 && (
        <div className={styles.results}>
          <div className={styles.resultsHeading}>
            <div>
              <h3>Cleaned images</h3>
              <p>Review each result before downloading or publishing it.</p>
            </div>
            <span>{images.length} of {MAX_WATERMARK_REMOVAL_IMAGES}</span>
          </div>
          <div className={styles.grid}>
            {images.map((image) => (
              <article key={image.id} className={styles.card}>
                {editingId === image.id ? (
                  <div className={styles.manualEditor}>
                    <div
                      className={styles.manualStage}
                      style={{ aspectRatio: `${image.width} / ${image.height}` }}
                    >
                      {/* eslint-disable-next-line @next/next/no-img-element */}
                      <img src={image.originalUrl} alt={`${image.name} original for manual repair`} />
                      <canvas
                        ref={manualCanvasRef}
                        aria-label="Paint over the watermark to remove"
                        onPointerDown={onManualPointerDown}
                        onPointerMove={onManualPointerMove}
                        onPointerUp={onManualPointerUp}
                        onPointerCancel={onManualPointerUp}
                      />
                    </div>
                    <div className={styles.manualTools}>
                      <p>Paint over every part of the watermark on the original image.</p>
                      <label>
                        Brush size
                        <input
                          aria-label="Watermark brush size"
                          type="range"
                          min={8}
                          max={100}
                          step={2}
                          value={manualBrushSize}
                          onChange={(event) => setManualBrushSize(Number(event.target.value))}
                        />
                      </label>
                      <div className={styles.manualActions}>
                        <button type="button" className={styles.secondaryButton} onClick={clearManualMask}>
                          Clear selection
                        </button>
                        <button
                          type="button"
                          className={styles.applyButton}
                          disabled={manualBusy}
                          onClick={() => void applyManualRemoval(image)}
                        >
                          {manualBusy ? "Repairing…" : "Remove marked watermark"}
                        </button>
                        <button
                          type="button"
                          className={styles.cancelButton}
                          onClick={() => {
                            setEditingId(null);
                            manualSourceRef.current = null;
                          }}
                        >
                          Cancel
                        </button>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className={styles.preview}>
                    {/* Blob previews are generated locally from the canvas export. */}
                    {/* eslint-disable-next-line @next/next/no-img-element */}
                    <img
                      src={image.url}
                      alt={`${image.name} with the watermark removed`}
                    />
                  </div>
                )}
                <div className={styles.cardBody}>
                  <p className={styles.filename} title={image.name}>{image.name}</p>
                  <p className={styles.dimensions}>{image.width} × {image.height} px</p>
                  <span className={image.detected ? styles.detected : styles.notDetected}>
                    {image.manual
                      ? `Manually removed · ${image.repairedPixels.toLocaleString()} pixels repaired`
                      : image.detected
                        ? `Site watermark removed · ${image.repairedPixels.toLocaleString()} pixels repaired`
                      : "No site watermark detected"}
                  </span>
                  {editingId !== image.id && (
                    <div className={styles.cardActions}>
                      <button
                        type="button"
                        className="btn btn-primary"
                        onClick={() => downloadImage(image)}
                      >
                        Download cleaned PNG
                      </button>
                      <button
                        type="button"
                        className={styles.secondaryButton}
                        disabled={manualBusy}
                        onClick={() => void startManualEdit(image)}
                      >
                        {image.detected ? "Refine with brush" : "Mark watermark manually"}
                      </button>
                    </div>
                  )}
                </div>
              </article>
            ))}
          </div>
        </div>
      )}

      <p className={styles.privacy}>
        Images stay on your device and are never uploaded to our server. Automatic
        detection is optimized for the centered red Pakistan Jobs Market watermark;
        use the repair brush for any other watermark. Complex backgrounds, heavy
        compression, or broad overlays may leave faint traces. The PNG export removes
        source metadata, including camera location data. Content directly beneath the
        watermark may not be reconstructable exactly because the watermark replaced
        those pixels.
      </p>
    </section>
  );
}
