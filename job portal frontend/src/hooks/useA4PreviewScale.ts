"use client";

import { useLayoutEffect, useRef, useState } from "react";
import type { CSSProperties } from "react";

type PreviewLayout = {
  height: number;
  scale: number;
  width: number;
};

const INITIAL_A4_WIDTH = 794;
const INITIAL_A4_HEIGHT = 1123;

/**
 * Keeps the source document at its real A4 dimensions while scaling only its
 * browser preview. PDF capture therefore receives the original layout and the
 * user never has to scroll inside the preview panel.
 */
export function useA4PreviewScale() {
  const shellRef = useRef<HTMLDivElement>(null);
  const documentRef = useRef<HTMLDivElement>(null);
  const [layout, setLayout] = useState<PreviewLayout>({
    height: INITIAL_A4_HEIGHT,
    scale: 1,
    width: INITIAL_A4_WIDTH,
  });

  useLayoutEffect(() => {
    const shell = shellRef.current;
    const document = documentRef.current;
    if (!shell || !document) return;

    const updateLayout = () => {
      const shellStyle = window.getComputedStyle(shell);
      const horizontalPadding =
        Number.parseFloat(shellStyle.paddingLeft) +
        Number.parseFloat(shellStyle.paddingRight);
      const availableWidth = Math.max(1, shell.clientWidth - horizontalPadding);
      const documentWidth = document.offsetWidth || INITIAL_A4_WIDTH;
      const documentHeight = Math.max(document.offsetHeight, document.scrollHeight);
      const scale = Math.min(1, availableWidth / documentWidth);
      const next = {
        height: Math.ceil(documentHeight * scale),
        scale,
        width: Math.ceil(documentWidth * scale),
      };

      setLayout((current) =>
        Math.abs(current.scale - next.scale) < 0.001 &&
        current.height === next.height &&
        current.width === next.width
          ? current
          : next
      );
    };

    const observer = new ResizeObserver(updateLayout);
    observer.observe(shell);
    observer.observe(document);
    updateLayout();

    return () => observer.disconnect();
  }, []);

  const stageStyle: CSSProperties = {
    height: `${layout.height}px`,
    width: `${layout.width}px`,
  };
  const documentStyle: CSSProperties = {
    transform: `scale(${layout.scale})`,
  };

  return { documentRef, documentStyle, shellRef, stageStyle };
}
