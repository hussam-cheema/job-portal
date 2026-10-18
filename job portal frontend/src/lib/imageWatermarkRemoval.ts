export const MAX_WATERMARK_REMOVAL_IMAGES = 3;

export type WatermarkBounds = {
  x: number;
  y: number;
  width: number;
  height: number;
};

export type WatermarkRemovalResult = {
  detected: boolean;
  repairedPixels: number;
  bounds: WatermarkBounds | null;
};

const SITE_WATERMARK_BOX_ALPHA = 50 / 255;

function insideRoundedRect(
  x: number,
  y: number,
  left: number,
  top: number,
  right: number,
  bottom: number,
  radius: number,
) {
  if (x < left || x >= right || y < top || y >= bottom) return false;
  const cornerX = x < left + radius ? left + radius : x >= right - radius ? right - radius - 1 : x;
  const cornerY = y < top + radius ? top + radius : y >= bottom - radius ? bottom - radius - 1 : y;
  const dx = x - cornerX;
  const dy = y - cornerY;
  return dx * dx + dy * dy <= radius * radius;
}

export function removeSiteWatermarkPixels(
  imageData: ImageData,
): WatermarkRemovalResult {
  const { width, height, data } = imageData;
  const pixelCount = width * height;
  const redMask = new Uint8Array(pixelCount);
  const bandTop = Math.max(0, Math.floor(height * 0.30));
  const bandBottom = Math.min(height, Math.ceil(height * 0.70));
  let minX = width;
  let minY = height;
  let maxX = -1;
  let maxY = -1;
  let redPixels = 0;

  // The site watermark is red text with a white stroke. Its red fill is the
  // most reliable signal and avoids changing a neutral or blue image.
  for (let y = bandTop; y < bandBottom; y += 1) {
    for (let x = 0; x < width; x += 1) {
      const offset = (y * width + x) * 4;
      if (data[offset + 3] < 24) continue;
      const red = data[offset];
      const green = data[offset + 1];
      const blue = data[offset + 2];
      const strongestOther = Math.max(green, blue);
      if (red < 105 || red - strongestOther < 18 || green > 246 || blue > 246) continue;
      redMask[y * width + x] = 1;
      redPixels += 1;
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);
    }
  }

  const boundsWidth = maxX - minX + 1;
  const boundsHeight = maxY - minY + 1;
  const minimumPixels = Math.max(24, Math.round(width * 0.008));
  if (
    maxX < minX
    || maxY < minY
    || redPixels < minimumPixels
    || boundsWidth < width * 0.12
    || boundsHeight < Math.max(8, height * 0.004)
    || boundsHeight > height * 0.24
    || (minX + maxX) / 2 < width * 0.2
    || (minX + maxX) / 2 > width * 0.8
  ) {
    return { detected: false, repairedPixels: 0, bounds: null };
  }

  const glyphHeight = Math.max(8, boundsHeight);

  // Lift the translucent black rounded rectangle before sampling its boundary.
  // This prevents the watermark shadow from being copied into the repair patch.
  const boxLeft = Math.max(0, minX - Math.round(glyphHeight * 0.24));
  const boxTop = Math.max(0, minY - Math.round(glyphHeight * 0.15));
  const boxRight = Math.min(width, maxX + Math.round(glyphHeight * 0.24) + 1);
  const boxBottom = Math.min(height, maxY + Math.round(glyphHeight * 0.15) + 1);
  const boxRadius = Math.max(4, Math.round(glyphHeight * 0.15));
  const fillLeft = Math.max(1, boxLeft - 3);
  const fillTop = Math.max(1, boxTop - 3);
  const fillRight = Math.min(width - 1, boxRight + 3);
  const fillBottom = Math.min(height - 1, boxBottom + 3);
  const mask = redMask;
  mask.fill(0);
  let repairedPixels = 0;
  for (let y = fillTop; y < fillBottom; y += 1) {
    for (let x = fillLeft; x < fillRight; x += 1) {
      const expandedRadius = boxRadius + 3;
      if (!insideRoundedRect(x, y, fillLeft, fillTop, fillRight, fillBottom, expandedRadius)) continue;
      mask[y * width + x] = 1;
      repairedPixels += 1;
    }
  }
  const inverseOpacity = 1 - SITE_WATERMARK_BOX_ALPHA;
  for (let y = boxTop; y < boxBottom; y += 1) {
    for (let x = boxLeft; x < boxRight; x += 1) {
      if (!insideRoundedRect(x, y, boxLeft, boxTop, boxRight, boxBottom, boxRadius)) continue;
      const offset = (y * width + x) * 4;
      data[offset] = Math.min(255, Math.round(data[offset] / inverseOpacity));
      data[offset + 1] = Math.min(255, Math.round(data[offset + 1] / inverseOpacity));
      data[offset + 2] = Math.min(255, Math.round(data[offset + 2] / inverseOpacity));
    }
  }

  // Sample from the de-shadowed pixels, otherwise the translucent watermark
  // box would be copied back into the repaired letter shapes as gray ghosts.
  const source = new Uint8ClampedArray(data);
  const smoothMask = new Uint8Array(mask);
  const regionLeft = Math.max(1, fillLeft - 1);
  const regionTop = Math.max(1, fillTop - 1);
  const regionRight = Math.min(width - 2, fillRight + 1);
  const regionBottom = Math.min(height - 2, fillBottom + 1);

  // Build a fast Coons-style patch from the four clean edges of the detected
  // box. This removes the whole watermark band without diagonal streaks or the
  // dark translucent rectangle showing through the repaired letters.
  const rowEdges = new Uint8ClampedArray(height * 8);
  for (let y = regionTop; y <= regionBottom; y += 1) {
    const leftOffset = (y * width + regionLeft) * 4;
    const rightOffset = (y * width + regionRight) * 4;
    const edgeOffset = y * 8;
    rowEdges.set(source.subarray(leftOffset, leftOffset + 4), edgeOffset);
    rowEdges.set(source.subarray(rightOffset, rightOffset + 4), edgeOffset + 4);
  }
  const columnEdges = new Uint8ClampedArray(width * 8);
  for (let x = regionLeft; x <= regionRight; x += 1) {
    const topOffset = (regionTop * width + x) * 4;
    const bottomOffset = (regionBottom * width + x) * 4;
    const edgeOffset = x * 8;
    columnEdges.set(source.subarray(topOffset, topOffset + 4), edgeOffset);
    columnEdges.set(source.subarray(bottomOffset, bottomOffset + 4), edgeOffset + 4);
  }
  const horizontalSpan = Math.max(1, regionRight - regionLeft);
  const verticalSpan = Math.max(1, regionBottom - regionTop);
  const preferHorizontal = horizontalSpan > verticalSpan * 2;
  const edgeBins = new Map<number, { count: number; red: number; green: number; blue: number; alpha: number }>();
  const addEdgeColor = (red: number, green: number, blue: number, alpha: number) => {
    const key = ((red >> 4) << 8) | ((green >> 4) << 4) | (blue >> 4);
    const bin = edgeBins.get(key) || { count: 0, red: 0, green: 0, blue: 0, alpha: 0 };
    bin.count += 1;
    bin.red += red;
    bin.green += green;
    bin.blue += blue;
    bin.alpha += alpha;
    edgeBins.set(key, bin);
  };
  for (let y = regionTop; y <= regionBottom; y += 1) {
    for (const offset of [y * 8, y * 8 + 4]) {
      addEdgeColor(rowEdges[offset], rowEdges[offset + 1], rowEdges[offset + 2], rowEdges[offset + 3]);
    }
  }
  for (let x = regionLeft; x <= regionRight; x += 1) {
    for (const offset of [x * 8, x * 8 + 4]) {
      addEdgeColor(columnEdges[offset], columnEdges[offset + 1], columnEdges[offset + 2], columnEdges[offset + 3]);
    }
  }
  const dominantBin = [...edgeBins.values()].sort(
    (a, b) => b.count - a.count,
  )[0] || { count: 1, red: 255, green: 255, blue: 255, alpha: 255 };
  const dominantEdge = [
    dominantBin.red / dominantBin.count,
    dominantBin.green / dominantBin.count,
    dominantBin.blue / dominantBin.count,
    dominantBin.alpha / dominantBin.count,
  ];
  for (let y = fillTop; y < fillBottom; y += 1) {
    const verticalPosition = (y - regionTop) / verticalSpan;
    for (let x = fillLeft; x < fillRight; x += 1) {
      const index = y * width + x;
      if (!mask[index]) continue;
      const horizontalPosition = (x - regionLeft) / horizontalSpan;
      const rowOffset = y * 8;
      const columnOffset = x * 8;
      const horizontalWeight = 1 / (Math.min(x - regionLeft, regionRight - x) + 1);
      const verticalWeight = preferHorizontal
        ? 0
        : 1 / (Math.min(y - regionTop, regionBottom - y) + 1);
      const weightTotal = horizontalWeight + verticalWeight;
      const offset = index * 4;
      for (let channel = 0; channel < 4; channel += 1) {
        const horizontal =
          rowEdges[rowOffset + channel] * (1 - horizontalPosition)
          + rowEdges[rowOffset + 4 + channel] * horizontalPosition;
        const vertical =
          columnEdges[columnOffset + channel] * (1 - verticalPosition)
          + columnEdges[columnOffset + 4 + channel] * verticalPosition;
        const interpolated =
          ((horizontal * horizontalWeight) + (vertical * verticalWeight)) / weightTotal;
        data[offset + channel] = Math.round(
          (dominantEdge[channel] * 0.82) + (interpolated * 0.18),
        );
      }
    }
  }

  // Apply one restrained smoothing pass only to repaired pixels so the patch
  // blends into its border without leaving a visible rectangle.
  for (let y = Math.max(1, fillTop); y <= Math.min(height - 2, fillBottom); y += 1) {
    for (let x = Math.max(1, fillLeft); x <= Math.min(width - 2, fillRight); x += 1) {
      const index = y * width + x;
      if (!smoothMask[index]) continue;
      let redTotal = 0;
      let greenTotal = 0;
      let blueTotal = 0;
      let samples = 0;
      for (let dy = -1; dy <= 1; dy += 1) {
        for (let dx = -1; dx <= 1; dx += 1) {
          const offset = ((y + dy) * width + (x + dx)) * 4;
          const weight = dx === 0 && dy === 0 ? 2 : 1;
          redTotal += data[offset] * weight;
          greenTotal += data[offset + 1] * weight;
          blueTotal += data[offset + 2] * weight;
          samples += weight;
        }
      }
      const offset = index * 4;
      data[offset] = Math.round(redTotal / samples);
      data[offset + 1] = Math.round(greenTotal / samples);
      data[offset + 2] = Math.round(blueTotal / samples);
    }
  }

  return {
    detected: true,
    repairedPixels,
    bounds: {
      x: minX,
      y: minY,
      width: boundsWidth,
      height: boundsHeight,
    },
  };
}

export function removeSiteWatermark(
  canvas: HTMLCanvasElement,
  source: CanvasImageSource,
  width: number,
  height: number,
): WatermarkRemovalResult {
  if (canvas.width !== width || canvas.height !== height) {
    canvas.width = width;
    canvas.height = height;
  }
  const context = canvas.getContext("2d", { alpha: true, willReadFrequently: true });
  if (!context) throw new Error("Your browser could not prepare the watermark remover.");
  context.clearRect(0, 0, width, height);
  context.drawImage(source, 0, 0, width, height);
  const imageData = context.getImageData(0, 0, width, height);
  const result = removeSiteWatermarkPixels(imageData);
  if (result.detected) context.putImageData(imageData, 0, 0);
  return result;
}

export function removeMaskedWatermarkPixels(
  imageData: ImageData,
  selectedMask: Uint8Array,
): WatermarkRemovalResult {
  const { width, height, data } = imageData;
  if (selectedMask.length !== width * height) {
    throw new Error("The selected repair area does not match this image.");
  }
  const source = new Uint8ClampedArray(data);
  const mask = new Uint8Array(selectedMask);
  const expand = Math.max(2, Math.round(Math.min(width, height) * 0.0025));
  const expanded = new Uint8Array(mask.length);
  let repairedPixels = 0;
  let minX = width;
  let minY = height;
  let maxX = -1;
  let maxY = -1;

  for (let y = 0; y < height; y += 1) {
    for (let x = 0; x < width; x += 1) {
      if (!mask[y * width + x]) continue;
      minX = Math.min(minX, x);
      minY = Math.min(minY, y);
      maxX = Math.max(maxX, x);
      maxY = Math.max(maxY, y);
      for (let dy = -expand; dy <= expand; dy += 1) {
        const ny = y + dy;
        if (ny < 0 || ny >= height) continue;
        for (let dx = -expand; dx <= expand; dx += 1) {
          if (dx * dx + dy * dy > expand * expand) continue;
          const nx = x + dx;
          if (nx < 0 || nx >= width) continue;
          const index = ny * width + nx;
          if (!expanded[index]) {
            expanded[index] = 1;
            repairedPixels += 1;
          }
        }
      }
    }
  }
  if (!repairedPixels) {
    return { detected: false, repairedPixels: 0, bounds: null };
  }

  const maxDistance = Math.max(32, Math.round(Math.max(width, height) * 0.08));
  const directions = [
    [-1, 0], [1, 0], [0, -1], [0, 1],
    [-1, -1], [1, -1], [-1, 1], [1, 1],
  ] as const;
  const sample = { red: 0, green: 0, blue: 0, alpha: 0 };

  for (let y = Math.max(0, minY - expand); y <= Math.min(height - 1, maxY + expand); y += 1) {
    for (let x = Math.max(0, minX - expand); x <= Math.min(width - 1, maxX + expand); x += 1) {
      const index = y * width + x;
      if (!expanded[index]) continue;
      const reds: number[] = [];
      const greens: number[] = [];
      const blues: number[] = [];
      const alphas: number[] = [];
      for (const [dx, dy] of directions) {
        for (let distance = 1; distance <= maxDistance; distance += 1) {
          const nx = x + dx * distance;
          const ny = y + dy * distance;
          if (nx < 0 || nx >= width || ny < 0 || ny >= height) break;
          const neighbour = ny * width + nx;
          if (expanded[neighbour]) continue;
          const offset = neighbour * 4;
          reds.push(source[offset]);
          greens.push(source[offset + 1]);
          blues.push(source[offset + 2]);
          alphas.push(source[offset + 3]);
          break;
        }
      }
      if (!reds.length) continue;
      reds.sort((a, b) => a - b);
      greens.sort((a, b) => a - b);
      blues.sort((a, b) => a - b);
      alphas.sort((a, b) => a - b);
      const middle = Math.floor(reds.length / 2);
      sample.red = reds[middle];
      sample.green = greens[middle];
      sample.blue = blues[middle];
      sample.alpha = alphas[middle];
      const offset = index * 4;
      data[offset] = sample.red;
      data[offset + 1] = sample.green;
      data[offset + 2] = sample.blue;
      data[offset + 3] = sample.alpha;
    }
  }

  // One small smoothing pass removes the hard edge of the brush selection.
  const smoothed = new Uint8ClampedArray(data);
  for (let y = Math.max(1, minY - expand); y <= Math.min(height - 2, maxY + expand); y += 1) {
    for (let x = Math.max(1, minX - expand); x <= Math.min(width - 2, maxX + expand); x += 1) {
      const index = y * width + x;
      if (!expanded[index]) continue;
      let redTotal = 0;
      let greenTotal = 0;
      let blueTotal = 0;
      let samples = 0;
      for (let dy = -1; dy <= 1; dy += 1) {
        for (let dx = -1; dx <= 1; dx += 1) {
          const offset = ((y + dy) * width + (x + dx)) * 4;
          const weight = dx === 0 && dy === 0 ? 2 : 1;
          redTotal += data[offset] * weight;
          greenTotal += data[offset + 1] * weight;
          blueTotal += data[offset + 2] * weight;
          samples += weight;
        }
      }
      const offset = index * 4;
      smoothed[offset] = Math.round(redTotal / samples);
      smoothed[offset + 1] = Math.round(greenTotal / samples);
      smoothed[offset + 2] = Math.round(blueTotal / samples);
    }
  }
  data.set(smoothed);

  return {
    detected: true,
    repairedPixels,
    bounds: {
      x: minX,
      y: minY,
      width: maxX - minX + 1,
      height: maxY - minY + 1,
    },
  };
}
