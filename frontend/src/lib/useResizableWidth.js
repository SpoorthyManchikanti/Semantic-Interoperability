import { useRef, useState } from "react";

// Drag-to-resize for a list/detail split. Uses Pointer Events + pointer
// capture instead of window-level mousemove/mouseup listeners — capture
// routes all subsequent pointer events to the divider regardless of where
// the cursor ends up, so there's no manual add/removeEventListener
// bookkeeping and no risk of a stuck drag if the pointer leaves the window.
// State only (not persisted) — a page reload resets to defaultWidth.
export function useResizableWidth(defaultWidth, min, max) {
  const [width, setWidth] = useState(defaultWidth);
  const dragStartRef = useRef(null);

  function onPointerDown(e) {
    e.currentTarget.setPointerCapture(e.pointerId);
    dragStartRef.current = { x: e.clientX, width };
  }

  function onPointerMove(e) {
    if (!dragStartRef.current) return;
    const delta = e.clientX - dragStartRef.current.x;
    const next = Math.min(max, Math.max(min, dragStartRef.current.width + delta));
    setWidth(next);
  }

  function onPointerUp(e) {
    dragStartRef.current = null;
    e.currentTarget.releasePointerCapture(e.pointerId);
  }

  return { width, dividerProps: { onPointerDown, onPointerMove, onPointerUp } };
}
