"use client";

import dynamic from "next/dynamic";
import { Component, type ErrorInfo, type ReactNode } from "react";
import type { QuillEditorProps } from "./QuillEditor";

async function loadQuillEditor() {
  let lastError: unknown;
  for (let attempt = 0; attempt < 3; attempt += 1) {
    try {
      const editorModule = await import("./QuillEditor");
      return editorModule.QuillEditor;
    } catch (error) {
      lastError = error;
      if (attempt < 2) {
        await new Promise((resolve) => setTimeout(resolve, 600 * (attempt + 1)));
      }
    }
  }
  throw lastError;
}

const QuillEditor = dynamic(
  loadQuillEditor,
  {
    ssr: false,
    loading: () => (
      <div className="quill-wrap">
        <div className="ql-toolbar ql-snow" style={{ minHeight: 42 }} />
        <div
          className="ql-container ql-snow"
          style={{
            minHeight: 220,
            padding: "12px 15px",
            fontFamily: "Helvetica, Arial, sans-serif",
            fontSize: 13,
            color: "#666",
            fontStyle: "italic",
          }}
        >
          Loading Quill editor…
        </div>
      </div>
    ),
  }
);

class EditorBoundary extends Component<{ children: ReactNode }, { failed: boolean }> {
  state = { failed: false };

  static getDerivedStateFromError() {
    return { failed: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    console.error("Rich-text editor failed to load", error, info);
  }

  render() {
    if (this.state.failed) {
      return (
        <div className="rounded-xl border border-[var(--danger)] p-4">
          <p className="field-error">
            The rich-text editor module could not be loaded. Your job data is still available.
          </p>
          <button
            type="button"
            className="btn btn-ghost mt-3"
            onClick={() => window.location.reload()}
          >
            Reload editor
          </button>
        </div>
      );
    }
    return this.props.children;
  }
}

export function RichTextEditor(props: QuillEditorProps) {
  return (
    <EditorBoundary>
      <QuillEditor {...props} />
    </EditorBoundary>
  );
}
