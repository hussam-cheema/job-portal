"use client";

import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import ReactQuill, { Quill } from "react-quill-new";
import "react-quill-new/dist/quill.snow.css";
import {
  restoreStoredJobDescriptionImages,
  rewriteJobDescriptionImageUrl,
  rewriteJobDescriptionImages,
} from "@/lib/media";

export type QuillEditorProps = {
  value: string;
  onChange: (html: string) => void;
  placeholder?: string;
  onUploadImage?: (file: File) => Promise<string>;
  onUploadAttachment?: (file: File) => Promise<{ url: string; name: string }>;
  maxAttachments?: number;
  attachmentCount?: number;
};

function registerQuillExtras() {
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const SizeStyle: any = Quill.import("attributors/style/size");
    if (SizeStyle) {
      SizeStyle.whitelist = [
        "10px",
        "12px",
        "14px",
        "16px",
        "18px",
        "20px",
        "24px",
        "32px",
      ];
      Quill.register(SizeStyle, true);
    }
  } catch {
    /* size style optional */
  }
  try {
    // eslint-disable-next-line @typescript-eslint/no-explicit-any
    const FontStyle: any = Quill.import("attributors/style/font");
    if (FontStyle) {
      FontStyle.whitelist = [
        "sans-serif",
        "serif",
        "monospace",
        "arial",
        "georgia",
        "helvetica",
        "times-new-roman",
      ];
      Quill.register(FontStyle, true);
    }
  } catch {
    /* font style optional */
  }
}

let registered = false;
function ensureRegistered() {
  if (registered || typeof window === "undefined") return;
  registerQuillExtras();
  registered = true;
}

const TOOLBAR = [
  [{ header: [1, 2, 3, 4, 5, 6, false] }],
  [{ size: ["small", false, "large", "huge"] }],
  ["bold", "italic", "underline", "strike"],
  [{ color: [] }, { background: [] }],
  [{ script: "sub" }, { script: "super" }],
  ["blockquote", "code-block"],
  [{ list: "ordered" }, { list: "bullet" }],
  [{ indent: "-1" }, { indent: "+1" }],
  [{ direction: "rtl" }, { align: [] }],
  ["link", "image", "video"],
  ["clean"],
];

function fileToDataUrl(file: File): Promise<string> {
  return new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => resolve(String(reader.result || ""));
    reader.onerror = () => reject(new Error("Failed to read image file"));
    reader.readAsDataURL(file);
  });
}

export function QuillEditor({
  value,
  onChange,
  placeholder = "Write content…",
  onUploadImage,
  onUploadAttachment,
  maxAttachments = 3,
  attachmentCount = 0,
}: QuillEditorProps) {
  const quillRef = useRef<ReactQuill | null>(null);
  const imageInput = useRef<HTMLInputElement>(null);
  const fileInput = useRef<HTMLInputElement>(null);
  const onUploadImageRef = useRef(onUploadImage);
  const onUploadAttachmentRef = useRef(onUploadAttachment);
  const attachmentCountRef = useRef(attachmentCount);
  const uploadedImageSourcesRef = useRef(new Map<string, string>());
  const imageUploadQueueRef = useRef<Promise<void>>(Promise.resolve());
  const [mounted, setMounted] = useState(false);

  useEffect(() => {
    ensureRegistered();
    setMounted(true);
  }, []);

  useEffect(() => {
    onUploadImageRef.current = onUploadImage;
  }, [onUploadImage]);
  useEffect(() => {
    onUploadAttachmentRef.current = onUploadAttachment;
  }, [onUploadAttachment]);
  useEffect(() => {
    attachmentCountRef.current = attachmentCount;
  }, [attachmentCount]);

  const insertImage = useCallback((url: string) => {
    const editor = quillRef.current?.getEditor?.();
    if (!editor || !url) return;
    const range = editor.getSelection(true);
    const index = range?.index ?? Math.max(0, editor.getLength() - 1);
    editor.insertEmbed(index, "image", url, "user");
    editor.setSelection(index + 1, 0, "silent");
  }, []);

  const uploadAndInsertImage = useCallback(
    async (file: File) => {
      if (!file.type.startsWith("image/")) {
        throw new Error("Please choose an image file");
      }
      let url = onUploadImageRef.current
        ? await onUploadImageRef.current(file)
        : await fileToDataUrl(file);
      if (!url) throw new Error("Empty image result");
      if (url.startsWith("/")) {
        const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        url = `${base.replace(/\/$/, "")}${url}`;
      }
      // R2 custom-domain access can be unavailable even though the upload
      // succeeded. Insert through the public backend media route immediately
      // so pasted images never render as broken while editing.
      const displayUrl = rewriteJobDescriptionImageUrl(url);
      if (displayUrl !== url) {
        uploadedImageSourcesRef.current.set(displayUrl, url);
      }
      insertImage(displayUrl);
    },
    [insertImage]
  );

  const uploadFiles = useCallback(
    (files: File[]) => {
      const operation = imageUploadQueueRef.current.then(async () => {
        for (const file of files) {
          try {
            await uploadAndInsertImage(file);
          } catch (err) {
            console.error(err);
            alert(err instanceof Error ? err.message : "Image upload failed");
          }
        }
      });
      // Paste, drag/drop, and the toolbar picker share one upload queue. This
      // prevents two async uploads from overwriting the controlled Quill value
      // or restoring the wrong durable R2 source.
      imageUploadQueueRef.current = operation.catch(() => undefined);
      return operation;
    },
    [uploadAndInsertImage],
  );

  const handlePasteCapture = useCallback(
    (event: React.ClipboardEvent<HTMLDivElement>) => {
      const clipboard = event.clipboardData;
      const itemFiles = Array.from(clipboard.items || [])
        .filter((item) => item.kind === "file" && item.type.startsWith("image/"))
        .map((item) => item.getAsFile())
        .filter((file): file is File => Boolean(file));
      const directFiles = Array.from(clipboard.files || []).filter((file) =>
        file.type.startsWith("image/")
      );
      const files = [...itemFiles, ...directFiles].filter(
        (file, index, all) =>
          all.findIndex(
            (candidate) =>
              candidate.name === file.name &&
              candidate.size === file.size &&
              candidate.type === file.type
          ) === index
      );
      if (!files.length) return;
      event.preventDefault();
      event.stopPropagation();
      uploadFiles(files);
    },
    [uploadFiles],
  );

  const insertAttachmentLink = useCallback((url: string, name: string) => {
    const editor = quillRef.current?.getEditor?.();
    if (!editor) return;
    const range = editor.getSelection(true);
    const index = range?.index ?? Math.max(0, editor.getLength() - 1);
    const label = `📎 ${name}`;
    editor.insertText(index, label, "link", url, "user");
    editor.insertText(index + label.length, "\n", "user");
    editor.setSelection(index + label.length + 1, 0, "silent");
  }, []);

  const openImagePicker = useCallback(() => {
    // Always open file picker — never URL prompt
    imageInput.current?.click();
  }, []);

  useEffect(() => {
    if (!mounted) return;
    const id = window.setTimeout(() => {
      try {
        const editor = quillRef.current?.getEditor?.();
        if (!editor) return;
        const toolbar = editor.getModule("toolbar") as {
          addHandler?: (name: string, fn: () => void) => void;
        } | null;
        toolbar?.addHandler?.("image", openImagePicker);
      } catch (err) {
        console.error("quill toolbar bind failed", err);
      }
    }, 50);
    return () => window.clearTimeout(id);
  }, [mounted, openImagePicker]);

  useEffect(() => {
    if (!mounted) return;
    const editor = quillRef.current?.getEditor?.();
    const root = (editor as unknown as { root?: HTMLElement } | undefined)?.root;
    if (!root) return;

    const onDrop = (event: DragEvent) => {
      const files = Array.from(event.dataTransfer?.files || []).filter((file) =>
        file.type.startsWith("image/")
      );
      if (!files.length) return;
      event.preventDefault();
      event.stopPropagation();
      uploadFiles(files);
    };

    root.addEventListener("drop", onDrop, true);
    return () => {
      root.removeEventListener("drop", onDrop, true);
    };
  }, [mounted, uploadFiles]);

  const modules = useMemo(
    () => ({
      toolbar: {
        container: TOOLBAR,
        handlers: {
          image: openImagePicker,
        },
      },
      clipboard: {
        matchVisual: false,
      },
    }),
    [openImagePicker]
  );

  // Existing R2 URLs are intentionally preserved in form state/database, but
  // displayed through the same reliable backend media proxy as public posts.
  const editorValue = useMemo(
    () => rewriteJobDescriptionImages(value || ""),
    [value],
  );

  const formats = [
    "header",
    "size",
    "bold",
    "italic",
    "underline",
    "strike",
    "color",
    "background",
    "script",
    "blockquote",
    "code-block",
    "list",
    "indent",
    "direction",
    "align",
    "table",
    "link",
    "image",
    "video",
  ];

  async function handleImageFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file) return;
    await uploadFiles([file]);
  }

  async function handleAttachmentFile(e: React.ChangeEvent<HTMLInputElement>) {
    const file = e.target.files?.[0];
    e.target.value = "";
    if (!file || !onUploadAttachmentRef.current) return;
    if (attachmentCountRef.current >= maxAttachments) {
      alert(`Maximum ${maxAttachments} attachments allowed`);
      return;
    }
    try {
      const { url, name } = await onUploadAttachmentRef.current(file);
      let finalUrl = url;
      if (finalUrl.startsWith("/")) {
        const base = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";
        finalUrl = `${base.replace(/\/$/, "")}${finalUrl}`;
      }
      insertAttachmentLink(finalUrl, name);
    } catch (err) {
      console.error(err);
      alert(err instanceof Error ? err.message : "Attachment upload failed");
    }
  }

  if (!mounted) {
    return (
      <div className="quill-wrap">
        <div className="ql-toolbar ql-snow" style={{ minHeight: 42 }} />
        <div className="ql-container ql-snow" style={{ minHeight: 220, padding: 12 }}>
          Loading Quill editor…
        </div>
      </div>
    );
  }

  return (
    <div
      className={`quill-wrap${onUploadAttachment ? " quill-wrap--with-attach" : ""}`}
      onPasteCapture={handlePasteCapture}
    >
      {onUploadAttachment && (
        <div className="quill-extra-bar">
          <button
            type="button"
            className="quill-attach-btn"
            onClick={() => fileInput.current?.click()}
          >
            📎 Attachment
          </button>
          <span className="quill-attach-hint">
            Max {maxAttachments} files ({attachmentCount}/{maxAttachments})
          </span>
        </div>
      )}

      <ReactQuill
        ref={quillRef}
        theme="snow"
        value={editorValue}
        onChange={(html) => {
          const empty = !html || html === "<p><br></p>" || html === "<p></p>";
          if (empty) {
            onChange("");
            return;
          }
          let storedHtml = restoreStoredJobDescriptionImages(html, value || "");
          for (const [displayUrl, sourceUrl] of uploadedImageSourcesRef.current) {
            storedHtml = storedHtml.replaceAll(displayUrl, sourceUrl);
          }
          onChange(storedHtml);
        }}
        modules={modules}
        formats={formats}
        placeholder={placeholder}
      />

      <input
        ref={imageInput}
        type="file"
        accept="image/*"
        className="hidden"
        onChange={handleImageFile}
      />
      <input ref={fileInput} type="file" className="hidden" onChange={handleAttachmentFile} />
    </div>
  );
}
