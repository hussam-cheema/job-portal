"use client";

import { KeyboardEvent, useState } from "react";

type Props = {
  values: string[];
  onChange: (values: string[]) => void;
  placeholder?: string;
};

export function TagInput({ values, onChange, placeholder = "Type and press Enter" }: Props) {
  const [draft, setDraft] = useState("");
  const safeValues = Array.isArray(values)
    ? values.filter((value): value is string => typeof value === "string")
    : [];

  function add(raw: string) {
    const parts = raw
      .split(",")
      .map((s) => s.trim())
      .filter(Boolean);
    if (!parts.length) return;
    const next = [...safeValues];
    for (const p of parts) {
      if (!next.some((v) => v.toLowerCase() === p.toLowerCase())) next.push(p);
    }
    onChange(next);
    setDraft("");
  }

  function onKeyDown(e: KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      add(draft);
    } else if (e.key === "Backspace" && !draft && safeValues.length) {
      onChange(safeValues.slice(0, -1));
    }
  }

  return (
    <div className="tag-input">
      {safeValues.map((v) => (
        <span key={v} className="tag tag-blue">
          {v}
          <button
            type="button"
            className="ml-1 opacity-70 hover:opacity-100"
            onClick={() => onChange(safeValues.filter((x) => x !== v))}
            aria-label={`Remove ${v}`}
          >
            ×
          </button>
        </span>
      ))}
      <input
        value={draft}
        onChange={(e) => setDraft(e.target.value)}
        onKeyDown={onKeyDown}
        onBlur={() => draft && add(draft)}
        placeholder={safeValues.length ? "" : placeholder}
      />
    </div>
  );
}
