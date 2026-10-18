"use client";

import { useEffect, useRef, useState, type ChangeEvent, type DragEvent } from "react";
import { MAX_IMAGE_BYTES, validateImage } from "@/lib/imageWatermark";
import {
  MAX_WATERMARK_REMOVAL_IMAGES,
  removeSiteWatermark,
  type WatermarkBounds,
} from "@/lib/imageWatermarkRemoval";
import styles from "./ImageWatermarkRemoval.module.css";

type ProcessedImage = {
  id: string;
  name: string;
  width: number;
  height: number;
  url: string;
  blob: Blob;
  detected: boolean;
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
  const [images, setImages] = useState<ProcessedImage[]>([]);
  const [busy, setBusy] = useState(false);
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

  async function processFiles(files: FileList | File[] | null) {
    const request = ++requestRef.current;
    revokeImages();
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
          const url = URL.createObjectURL(blob);
          urlsRef.current.push(url);
          processed.push({
            id: crypto.randomUUID(),
            name: file.name,
            width: decoded.width,
            height: decoded.height,
            url,
            blob,
            detected: result.detected,
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
          "No Pakistan Jobs Market watermark was detected. The images are unchanged, "
          + "and other watermark styles may need manual editing.",
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
    setImages([]);
    setBusy(false);
    setProgress("");
    setError("");
  }

  return (
    <section className={styles.shell} data-testid="image-watermark-removal">
      <div className={styles.intro}>
        <p className="tool-kicker">Private, in-browser image repair</p>
        <h2>Remove the site watermark</h2>
        <p>
          Upload up to three PNG, JPEG, or WebP images. The editor detects the
          Pakistan Jobs Market watermark, repairs the covered pixels, and lets you
          download each cleaned image as a full-resolution PNG.
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
            className="btn btn-ghost"
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
                <div className={styles.preview}>
                  {/* Blob previews are generated locally from the canvas export. */}
                  {/* eslint-disable-next-line @next/next/no-img-element */}
                  <img
                    src={image.url}
                    alt={`${image.name} with the detected watermark removed`}
                  />
                </div>
                <div className={styles.cardBody}>
                  <p className={styles.filename} title={image.name}>{image.name}</p>
                  <p className={styles.dimensions}>{image.width} × {image.height} px</p>
                  <span className={image.detected ? styles.detected : styles.notDetected}>
                    {image.detected
                      ? `Watermark removed · ${image.repairedPixels.toLocaleString()} pixels repaired`
                      : "No site watermark detected"}
                  </span>
                  <button
                    type="button"
                    className="btn btn-primary"
                    onClick={() => downloadImage(image)}
                  >
                    Download cleaned PNG
                  </button>
                </div>
              </article>
            ))}
          </div>
        </div>
      )}

      <p className={styles.privacy}>
        Images stay on your device and are never uploaded to our server. Automatic
        detection is designed for the centered red Pakistan Jobs Market watermark.
        Complex backgrounds, heavy compression, or different watermark styles may
        leave faint traces. The PNG export removes source metadata, including
        camera location data. Content directly beneath the watermark may not be
        reconstructable exactly because the watermark replaced those pixels.
      </p>
    </section>
  );
}
