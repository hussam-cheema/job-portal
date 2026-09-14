"use client";

import { useCallback, useEffect, useRef, type MouseEvent, type ReactNode, type SyntheticEvent } from "react";
import { trackToolEvent } from "@/lib/api";
import { getVisitorId } from "@/lib/visitorId";

export function ToolUsageObserver({ slug, children }: { slug: string; children: ReactNode }) {
  const lastInteractionAt = useRef(0);
  const record = useCallback((eventType: "open" | "interaction") => {
    if (eventType === "interaction") {
      const now = Date.now();
      if (now - lastInteractionAt.current < 30 * 60_000) return;
      lastInteractionAt.current = now;
    }
    void trackToolEvent(getVisitorId(), slug, eventType);
  }, [slug]);

  useEffect(() => {
    lastInteractionAt.current = 0;
    record("open");
  }, [record]);

  function onInput(event: SyntheticEvent<HTMLDivElement>) {
    const target = event.target;
    if (target instanceof Element && target.closest('input, textarea, select, [contenteditable="true"]')) {
      record("interaction");
    }
  }

  function onClick(event: MouseEvent<HTMLDivElement>) {
    const target = event.target;
    if (!(target instanceof Element)) return;
    const control = target.closest('button, input[type="button"], input[type="submit"], a[download]');
    if (control && !control.hasAttribute("disabled") && !control.closest("[data-tool-usage-ignore]")) {
      record("interaction");
    }
  }

  return <div data-testid="tool-usage-observer" style={{ display: "contents" }} onInputCapture={onInput} onChangeCapture={onInput} onClickCapture={onClick}>
    {children}
  </div>;
}
