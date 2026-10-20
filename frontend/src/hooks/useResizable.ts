/*
 * Copyright (C) 2026 Paulo Felipe Jarschel
 * 
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 * 
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
 * GNU General Public License for more details.
 */

import { useState, useCallback, useEffect, useRef } from 'react';

interface UseResizableOptions {
  direction: 'left' | 'right'; // 'left' = panel is on the left, handle on right edge; 'right' = panel on right, handle on left edge
  defaultWidth?: number;
  minWidth?: number;
  maxWidth?: number;
  storageKey?: string;
  onWidthChange?: (newWidth: number) => void;
}

export const useResizable = ({
  direction,
  defaultWidth = 320,
  minWidth = 240,
  maxWidth = 850,
  storageKey,
  onWidthChange,
}: UseResizableOptions) => {
  const [width, setWidth] = useState<number>(() => {
    if (storageKey) {
      try {
        const saved = localStorage.getItem(storageKey);
        if (saved) {
          const parsed = parseInt(saved, 10);
          if (!isNaN(parsed) && parsed >= minWidth && parsed <= maxWidth) {
            return parsed;
          }
        }
      } catch (e) {
        // Ignore localStorage read errors
      }
    }
    return defaultWidth;
  });

  const [isResizing, setIsResizing] = useState(false);
  const startXRef = useRef(0);
  const startWidthRef = useRef(width);
  const isResizingRef = useRef(false);

  const startResizing = useCallback((e: React.PointerEvent) => {
    e.preventDefault();
    e.stopPropagation();
    startXRef.current = e.clientX;
    startWidthRef.current = width;
    isResizingRef.current = true;
    setIsResizing(true);
    document.body.style.cursor = 'col-resize';
    document.body.style.userSelect = 'none';
  }, [width]);

  useEffect(() => {
    const handlePointerMove = (e: PointerEvent) => {
      if (!isResizingRef.current) return;
      const deltaX = e.clientX - startXRef.current;
      // If panel is on left: dragging right (deltaX > 0) expands panel
      // If panel is on right: dragging left (deltaX < 0) expands panel
      const newWidthRaw = direction === 'left'
        ? startWidthRef.current + deltaX
        : startWidthRef.current - deltaX;

      const clampedWidth = Math.max(minWidth, Math.min(maxWidth, newWidthRaw));
      setWidth(clampedWidth);
      if (onWidthChange) {
        onWidthChange(clampedWidth);
      }
    };

    const handlePointerUp = () => {
      if (!isResizingRef.current) return;
      isResizingRef.current = false;
      setIsResizing(false);
      document.body.style.cursor = '';
      document.body.style.userSelect = '';

      if (storageKey) {
        try {
          localStorage.setItem(storageKey, String(width));
        } catch (e) {
          // Ignore write errors
        }
      }
    };

    // Pointer events cover mouse, touch and pen alike
    window.addEventListener('pointermove', handlePointerMove);
    window.addEventListener('pointerup', handlePointerUp);
    window.addEventListener('pointercancel', handlePointerUp);
    return () => {
      window.removeEventListener('pointermove', handlePointerMove);
      window.removeEventListener('pointerup', handlePointerUp);
      window.removeEventListener('pointercancel', handlePointerUp);
    };
  }, [direction, minWidth, maxWidth, storageKey, onWidthChange, width]);

  // Sync width to localStorage whenever width changes after resizing completes
  useEffect(() => {
    if (storageKey && !isResizing) {
      try {
        localStorage.setItem(storageKey, String(width));
      } catch (e) {}
    }
  }, [width, storageKey, isResizing]);

  return {
    width,
    setWidth,
    isResizing,
    handleProps: {
      onPointerDown: startResizing,
    },
  };
};
