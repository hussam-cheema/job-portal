"use client";

import dynamic from "next/dynamic";
import type { QuillEditorProps } from "./QuillEditor";

const QuillEditor = dynamic(
  () => import("./QuillEditor").then((m) => m.QuillEditor),
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

export function RichTextEditor(props: QuillEditorProps) {
  return <QuillEditor {...props} />;
}
