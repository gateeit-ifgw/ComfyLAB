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

import { useEffect } from 'react';

const LONG_PRESS_MS = 550;
const MOVE_TOLERANCE_PX = 10;

/**
 * Opens the regular right-click context menus with a touch long-press.
 * Android already fires a native `contextmenu` on long-press, iOS does not, so a synthetic one is
 * dispatched at the press location; whichever comes first wins and the other is swallowed, so a
 * menu never opens twice. The tap that ends the press is swallowed too, so it can't close the menu.
 */
export const useLongPressContextMenu = (ref: React.RefObject<HTMLElement | null>) => {
  useEffect(() => {
    const el = ref.current;
    if (!el) return;

    let timer: number | null = null;
    let startX = 0;
    let startY = 0;
    let activePointers = 0;
    let menuOpenedThisPress = false;
    let swallowUntil = 0;

    const cancel = () => {
      if (timer !== null) {
        window.clearTimeout(timer);
        timer = null;
      }
    };

    const onPointerDown = (e: PointerEvent) => {
      if (e.pointerType !== 'touch') return;
      activePointers++;
      cancel();
      menuOpenedThisPress = false;
      // Two fingers = pinch/pan gesture, never a long-press
      if (activePointers > 1) return;
      startX = e.clientX;
      startY = e.clientY;
      const target = e.target as Element;
      timer = window.setTimeout(() => {
        timer = null;
        menuOpenedThisPress = true;
        target.dispatchEvent(new MouseEvent('contextmenu', {
          bubbles: true,
          cancelable: true,
          clientX: startX,
          clientY: startY,
          button: 2,
        }));
      }, LONG_PRESS_MS);
    };

    const onPointerMove = (e: PointerEvent) => {
      if (timer === null || e.pointerType !== 'touch') return;
      if (Math.hypot(e.clientX - startX, e.clientY - startY) > MOVE_TOLERANCE_PX) cancel();
    };

    const onPointerEnd = (e: PointerEvent) => {
      if (e.pointerType !== 'touch') return;
      activePointers = Math.max(0, activePointers - 1);
      cancel();
      if (menuOpenedThisPress) swallowUntil = Date.now() + 700;
    };

    const onNativeContextMenu = (e: MouseEvent) => {
      if (!e.isTrusted) return;
      if (menuOpenedThisPress) {
        // Our synthetic menu already opened for this press
        e.preventDefault();
        e.stopPropagation();
      } else if (timer !== null) {
        // The browser beat us to it (Android); let the native event through
        cancel();
        menuOpenedThisPress = true;
      }
    };

    const swallowTrailingTap = (e: Event) => {
      if (Date.now() < swallowUntil) {
        e.preventDefault();
        e.stopPropagation();
      }
    };

    el.addEventListener('pointerdown', onPointerDown, true);
    el.addEventListener('pointermove', onPointerMove, true);
    el.addEventListener('pointerup', onPointerEnd, true);
    el.addEventListener('pointercancel', onPointerEnd, true);
    el.addEventListener('contextmenu', onNativeContextMenu, true);
    // Document level: the outside-click handler that closes menus listens on document in capture phase
    window.addEventListener('mousedown', swallowTrailingTap, true);
    window.addEventListener('click', swallowTrailingTap, true);
    return () => {
      cancel();
      el.removeEventListener('pointerdown', onPointerDown, true);
      el.removeEventListener('pointermove', onPointerMove, true);
      el.removeEventListener('pointerup', onPointerEnd, true);
      el.removeEventListener('pointercancel', onPointerEnd, true);
      el.removeEventListener('contextmenu', onNativeContextMenu, true);
      window.removeEventListener('mousedown', swallowTrailingTap, true);
      window.removeEventListener('click', swallowTrailingTap, true);
    };
  }, [ref]);
};
