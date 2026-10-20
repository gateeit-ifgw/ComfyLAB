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

import React, { useCallback } from 'react';

interface Point {
  x: number;
  y: number;
}

interface Annotation {
  id: string;
  type: string;
  color: string;
  strokeWidth?: number;
  width?: number;
  height?: number;
  x?: number;
  y?: number;
  cx?: number;
  cy?: number;
  r?: number;
  rx?: number;
  ry?: number;
  x1?: number;
  y1?: number;
  x2?: number;
  y2?: number;
  points?: Point[];
  style?: string;
  fill?: boolean;
  fillColor?: string;
  fillOpacity?: number;
  text?: string;
  fontSize?: number;
  startCap?: 'none' | 'arrow' | 'dot' | 'bar';
  endCap?: 'none' | 'arrow' | 'dot' | 'bar';
  arrowEnd?: boolean;
}

interface WhiteboardOverlayProps {
  showAnnotations: boolean;
  drawTool: string;
  canvasMode: 'select' | 'pan' | 'cut' | 'draw';
  viewport: { x: number; y: number; zoom: number };
  annotations: Annotation[];
  currentAnnotation: Annotation | null;
  eraserPath: Point[] | null;
  markedForDeletion: Set<string>;
  hoverPoint: Point | null;
  editingTextId: string | null;
  selectedAnnotationId?: string | null;
  blocks: any[];
  edges: any[];
  pushStateToHistory: (blocks: any[], edges: any[], annotations: any[]) => void;
  setAnnotations: (annotations: Annotation[]) => void;
  setEditingTextId: (id: string | null) => void;
  onMouseDown: (e: React.MouseEvent<SVGSVGElement>) => void;
  onMouseMove: (e: React.MouseEvent<SVGSVGElement>) => void;
  onMouseUp: (e: React.MouseEvent<SVGSVGElement>) => void;
  onDoubleClick: (e: React.MouseEvent<SVGSVGElement>) => void;
  onWheel: (e: React.WheelEvent<SVGSVGElement>) => void;
  onStartResize?: (handle: string, e: React.MouseEvent) => void;
}

export const WhiteboardOverlay = ({
  showAnnotations,
  drawTool,
  canvasMode,
  viewport,
  annotations,
  currentAnnotation,
  eraserPath,
  markedForDeletion,
  hoverPoint,
  editingTextId,
  selectedAnnotationId,
  blocks,
  edges,
  pushStateToHistory,
  setAnnotations,
  setEditingTextId,
  onMouseDown,
  onMouseMove,
  onMouseUp,
  onDoubleClick,
  onWheel,
  onStartResize,
}: WhiteboardOverlayProps) => {


  const renderLineCap = (
    type: 'none' | 'arrow' | 'dot' | 'bar',
    px: number,
    py: number,
    angle: number,
    color: string,
    strokeWidth: number,
    neonFilter: string | undefined,
    commonProps: any
  ) => {
    if (type === 'none') return null;

    const { key: _, className: commonClassName, ...otherCommonProps } = commonProps;

    if (type === 'arrow') {
      const d = Math.max(12, strokeWidth * 2.5);
      const arrowX1 = px - d * Math.cos(angle - Math.PI / 6);
      const arrowY1 = py - d * Math.sin(angle - Math.PI / 6);
      const arrowX2 = px - d * Math.cos(angle + Math.PI / 6);
      const arrowY2 = py - d * Math.sin(angle + Math.PI / 6);
      const pointsStr = `${px},${py} ${arrowX1},${arrowY1} ${arrowX2},${arrowY2}`;

      return (
        <polygon
          key={`arrow-${px}-${py}-${angle}`}
          points={pointsStr}
          className={`${commonClassName || 'annotation-element'} fill-element`}
          {...otherCommonProps}
          style={{
            fill: color,
            '--annotation-fill': color,
            filter: neonFilter,
          } as any}
        />
      );
    }

    if (type === 'dot') {
      const r = Math.max(6, strokeWidth * 1.5);
      return (
        <circle
          key={`dot-${px}-${py}`}
          cx={px}
          cy={py}
          r={r}
          className={`${commonClassName || 'annotation-element'} fill-element`}
          {...otherCommonProps}
          style={{
            fill: color,
            '--annotation-fill': color,
            filter: neonFilter,
          } as any}
        />
      );
    }

    if (type === 'bar') {
      const h = Math.max(8, strokeWidth * 2);
      const perpAngle = angle + Math.PI / 2;
      const x1 = px + h * Math.cos(perpAngle);
      const y1 = py + h * Math.sin(perpAngle);
      const x2 = px - h * Math.cos(perpAngle);
      const y2 = py - h * Math.sin(perpAngle);

      return (
        <line
          key={`bar-${px}-${py}`}
          x1={x1}
          y1={y1}
          x2={x2}
          y2={y2}
          className={`${commonClassName || 'annotation-element'} stroke-element`}
          {...otherCommonProps}
          style={{
            stroke: color,
            strokeWidth: strokeWidth,
            strokeLinecap: 'round',
            filter: neonFilter,
          }}
        />
      );
    }

    return null;
  };

  const renderAnnotation = useCallback((ann: Annotation) => {
    const isEditing = editingTextId === ann.id;
    const isEraser = drawTool === 'eraser';
    const isMarked = markedForDeletion.has(ann.id);

    const isCurrentPreview = ann.id === currentAnnotation?.id;

    const commonProps = {
      className: `annotation-element ${isEraser ? 'hoverable-eraser' : ''}`,
      onPointerDown: (e: React.MouseEvent) => {
        if (drawTool === 'select') {
          return;
        }
        if (isEraser) {
          e.stopPropagation();
          return;
        }
        // When drawing (polyline, polygon, pen, etc.), do NOT stop propagation so handleSvgMouseDown gets the click!
      },
      onClick: (e: React.MouseEvent) => {
        if (isEraser) {
          e.stopPropagation();
          pushStateToHistory(blocks, edges, annotations);
          const nextAnnotations = annotations.filter(a => a.id !== ann.id);
          setAnnotations(nextAnnotations);
        }
      },
    };

    let strokeWidth = 4;
    if (ann.strokeWidth !== undefined) {
      strokeWidth = ann.strokeWidth;
    } else if (ann.type !== 'rectangle' && ann.width !== undefined) {
      strokeWidth = ann.width;
    }
    const isNeon = ann.style === 'neon' || ann.style === 'neon-dashed';
    const isDashed = ann.style === 'dashed' || ann.style === 'neon-dashed';

    const strokeStyle = {
      stroke: isMarked ? '#ef4444' : ann.color,
      strokeWidth: strokeWidth,
      strokeLinecap: 'round' as const,
      strokeLinejoin: 'round' as const,
      cursor: isEraser ? 'cell' : (drawTool === 'select' ? 'grab' : 'pointer'),
      pointerEvents: isCurrentPreview ? ('none' as const) : undefined,
      strokeDasharray: isDashed
        ? `${strokeWidth * (isNeon ? 4 : 3)} ${strokeWidth * (isNeon ? 4 : 2)}`
        : undefined,
      filter: isNeon && !isMarked
        ? `drop-shadow(0 0 ${Math.max(2, strokeWidth / 2)}px ${ann.color}) drop-shadow(0 0 ${strokeWidth}px ${ann.color})`
        : isMarked
        ? 'drop-shadow(0 0 6px #ef4444)'
        : undefined,
      opacity: isMarked ? 0.4 : undefined,
    };

    switch (ann.type) {
      case 'pen': {
        if (!ann.points || ann.points.length === 0) return null;
        const d = ann.points.map((p, idx) => (idx === 0 ? `M ${p.x} ${p.y}` : `L ${p.x} ${p.y}`)).join(' ');
        return (
          <path
            key={ann.id}
            d={d}
            {...commonProps}
            className={`${commonProps.className} stroke-element`}
            style={{ ...strokeStyle }}
            fill="none"
          />
        );
      }
      case 'polygon': {
        if (!ann.points || ann.points.length === 0) return null;

        let pts = [...ann.points];
        if (ann.id === currentAnnotation?.id && hoverPoint) {
          pts.push(hoverPoint);
        }

        if (pts.length < 2) return null;

        let pointsStr = pts.map((p) => `${p.x},${p.y}`).join(' ');

        const strokePoly = (
          <polygon
            key={ann.id}
            points={pointsStr}
            {...commonProps}
            className={`${commonProps.className} stroke-element`}
            style={{
              ...strokeStyle,
              fill: 'none',
              '--annotation-fill': 'none',
            } as any}
          />
        );
        
        let polyElement = strokePoly;
        if (ann.fill) {
          const fillColorVal = isMarked ? '#ef4444' : ann.fillColor;
          const fillOpacityVal = isMarked ? 0.2 : ann.fillOpacity;
          const fillPoly = (
            <polygon
              points={pointsStr}
              style={{
                fill: fillColorVal,
                fillOpacity: fillOpacityVal,
                stroke: 'none',
                cursor: strokeStyle.cursor,
                '--annotation-fill': fillColorVal,
                '--annotation-fill-opacity': fillOpacityVal,
              } as any}
              className="annotation-element fill-element"
              onPointerDown={(e) => { if (drawTool === 'select') return; if (isEraser) e.stopPropagation(); }}
            />
          );
          polyElement = (
            <g key={ann.id}>
              {fillPoly}
              {strokePoly}
            </g>
          );
        }
        
        let previewClosingLine = null;
        if (ann.id === currentAnnotation?.id && hoverPoint && ann.points.length > 0) {
           const startPoint = ann.points[0];
           previewClosingLine = (
             <line 
                x1={hoverPoint.x} y1={hoverPoint.y} x2={startPoint.x} y2={startPoint.y}
                stroke={ann.color} strokeWidth={Math.max(1, strokeWidth / 2)} strokeDasharray="4 4" opacity={0.5}
             />
           );
        }
        
        return (
           <g key={ann.id}>
              {polyElement}
              {previewClosingLine}
           </g>
        );
      }
      case 'polyline': {
        if (!ann.points || ann.points.length === 0) return null;

        let pts = [...ann.points];
        if (ann.id === currentAnnotation?.id && hoverPoint) {
          pts.push(hoverPoint);
        }

        if (pts.length < 2) return null;

        const displayPoints = pts.map(p => ({ ...p }));
        const startAngle = Math.atan2(displayPoints[1].y - displayPoints[0].y, displayPoints[1].x - displayPoints[0].x);
        const startCap = ann.startCap || 'none';
        
        if (startCap === 'arrow') {
          const d = Math.max(12, strokeWidth * 2.5);
          displayPoints[0].x += d * 0.8 * Math.cos(startAngle);
          displayPoints[0].y += d * 0.8 * Math.sin(startAngle);
        } else if (startCap === 'dot') {
          const r = Math.max(6, strokeWidth * 1.5);
          displayPoints[0].x += r * 0.5 * Math.cos(startAngle);
          displayPoints[0].y += r * 0.5 * Math.sin(startAngle);
        }

        const n = displayPoints.length;
        const endAngle = Math.atan2(displayPoints[n-1].y - displayPoints[n-2].y, displayPoints[n-1].x - displayPoints[n-2].x);
        const endCap = ann.endCap || (ann.arrowEnd ? 'arrow' : 'none');

        if (endCap === 'arrow') {
          const d = Math.max(12, strokeWidth * 2.5);
          displayPoints[n-1].x -= d * 0.8 * Math.cos(endAngle);
          displayPoints[n-1].y -= d * 0.8 * Math.sin(endAngle);
        } else if (endCap === 'dot') {
          const r = Math.max(6, strokeWidth * 1.5);
          displayPoints[n-1].x -= r * 0.5 * Math.cos(endAngle);
          displayPoints[n-1].y -= r * 0.5 * Math.sin(endAngle);
        }

        const dAttr = displayPoints
          .map((p, idx) => (idx === 0 ? `M ${p.x} ${p.y}` : `L ${p.x} ${p.y}`))
          .join(' ');

        const pathEl = (
          <path
            key={ann.id}
            d={dAttr}
            {...commonProps}
            className={`${commonProps.className} stroke-element`}
            style={{ ...strokeStyle }}
            fill="none"
          />
        );

        const caps: React.ReactNode[] = [];
        const startCapEl = renderLineCap(
          startCap,
          ann.points[0].x,
          ann.points[0].y,
          startAngle + Math.PI,
          isMarked ? '#ef4444' : ann.color,
          strokeWidth,
          strokeStyle.filter,
          commonProps
        );
        if (startCapEl) caps.push(startCapEl);

        const endCapEl = renderLineCap(
          endCap,
          pts[pts.length - 1].x,
          pts[pts.length - 1].y,
          endAngle,
          isMarked ? '#ef4444' : ann.color,
          strokeWidth,
          strokeStyle.filter,
          commonProps
        );
        if (endCapEl) caps.push(endCapEl);

        return (
          <g key={ann.id}>
            {pathEl}
            {caps}
          </g>
        );
      }
      case 'line': {
        const angle = Math.atan2((ann.y2 || 0) - (ann.y1 || 0), (ann.x2 || 0) - (ann.x1 || 0));
        const startCap = ann.startCap || 'none';
        const endCap = ann.endCap || (ann.arrowEnd ? 'arrow' : 'none');

        let drawX1 = ann.x1 || 0;
        let drawY1 = ann.y1 || 0;
        let drawX2 = ann.x2 || 0;
        let drawY2 = ann.y2 || 0;

        if (startCap === 'arrow') {
          const d = Math.max(12, strokeWidth * 2.5);
          drawX1 += d * 0.8 * Math.cos(angle);
          drawY1 += d * 0.8 * Math.sin(angle);
        } else if (startCap === 'dot') {
          const r = Math.max(6, strokeWidth * 1.5);
          drawX1 += r * 0.5 * Math.cos(angle);
          drawY1 += r * 0.5 * Math.sin(angle);
        }

        if (endCap === 'arrow') {
          const d = Math.max(12, strokeWidth * 2.5);
          drawX2 -= d * 0.8 * Math.cos(angle);
          drawY2 -= d * 0.8 * Math.sin(angle);
        } else if (endCap === 'dot') {
          const r = Math.max(6, strokeWidth * 1.5);
          drawX2 -= r * 0.5 * Math.cos(angle);
          drawY2 -= r * 0.5 * Math.sin(angle);
        }

        const lineEl = (
          <line
            key={ann.id}
            x1={drawX1}
            y1={drawY1}
            x2={drawX2}
            y2={drawY2}
            {...commonProps}
            className={`${commonProps.className} stroke-element`}
            style={{ ...strokeStyle }}
          />
        );

        const caps: React.ReactNode[] = [];
        const startCapEl = renderLineCap(
          startCap,
          ann.x1 || 0,
          ann.y1 || 0,
          angle + Math.PI,
          isMarked ? '#ef4444' : ann.color,
          strokeWidth,
          strokeStyle.filter,
          commonProps
        );
        if (startCapEl) caps.push(startCapEl);

        const endCapEl = renderLineCap(
          endCap,
          ann.x2 || 0,
          ann.y2 || 0,
          angle,
          isMarked ? '#ef4444' : ann.color,
          strokeWidth,
          strokeStyle.filter,
          commonProps
        );
        if (endCapEl) caps.push(endCapEl);

        return (
          <g key={ann.id}>
            {lineEl}
            {caps}
          </g>
        );
      }
      case 'rectangle': {
        const strokeRect = (
          <rect
            key={ann.id}
            x={ann.x}
            y={ann.y}
            width={ann.width}
            height={ann.height}
            rx={8}
            ry={8}
            {...commonProps}
            className={`${commonProps.className} stroke-element`}
            style={{
              ...strokeStyle,
              fill: 'none',
              '--annotation-fill': 'none',
            } as any}
          />
        );

        if (ann.fill) {
          const fillColorVal = isMarked ? '#ef4444' : ann.fillColor;
          const fillOpacityVal = isMarked ? 0.2 : ann.fillOpacity;
          const fillRect = (
            <rect
              key={ann.id}
              x={ann.x}
              y={ann.y}
              width={ann.width}
              height={ann.height}
              rx={8}
              ry={8}
              style={{
                fill: fillColorVal,
                fillOpacity: fillOpacityVal,
                stroke: 'none',
                cursor: strokeStyle.cursor,
                '--annotation-fill': fillColorVal,
                '--annotation-fill-opacity': fillOpacityVal,
              } as any}
              className="annotation-element fill-element"
              onPointerDown={(e) => { if (drawTool === 'select') return; if (isEraser) e.stopPropagation(); }}
            />
          );
          return (
            <g key={ann.id}>
              {fillRect}
              {strokeRect}
            </g>
          );
        }
        return strokeRect;
      }
      case 'circle': {
        const rx = ann.rx !== undefined ? ann.rx : (ann.r || 0);
        const ry = ann.ry !== undefined ? ann.ry : (ann.r || 0);
        const strokeCircle = (
          <ellipse
            key={ann.id}
            cx={ann.cx}
            cy={ann.cy}
            rx={rx}
            ry={ry}
            {...commonProps}
            className={`${commonProps.className} stroke-element`}
            style={{
              ...strokeStyle,
              fill: 'none',
              '--annotation-fill': 'none',
            } as any}
          />
        );

        if (ann.fill) {
          const fillColorVal = isMarked ? '#ef4444' : ann.fillColor;
          const fillOpacityVal = isMarked ? 0.2 : ann.fillOpacity;
          const fillCircle = (
            <ellipse
              cx={ann.cx}
              cy={ann.cy}
              rx={rx}
              ry={ry}
              style={{
                fill: fillColorVal,
                fillOpacity: fillOpacityVal,
                stroke: 'none',
                cursor: strokeStyle.cursor,
                '--annotation-fill': fillColorVal,
                '--annotation-fill-opacity': fillOpacityVal,
              } as any}
              className="annotation-element fill-element"
              onPointerDown={(e) => { if (drawTool === 'select') return; if (isEraser) e.stopPropagation(); }}
            />
          );
          return (
            <g key={ann.id}>
              {fillCircle}
              {strokeCircle}
            </g>
          );
        }
        return strokeCircle;
      }
      case 'note': {
        const isSelected = selectedAnnotationId === ann.id;
        const width = Math.max(ann.width || 180, 80);
        const height = Math.max(ann.height || 140, 60);
        const x = ann.x || 0;
        const y = ann.y || 0;

        if (isEditing) {
          return (
            <foreignObject
              key={ann.id}
              x={x}
              y={y}
              width={width}
              height={height}
              style={{ overflow: 'visible' }}
              onPointerDown={(e) => e.stopPropagation()}
              onPointerUp={(e) => e.stopPropagation()}
              onClick={(e) => e.stopPropagation()}
            >
              <div
                className="annotation-note-container editing"
                style={{
                  width: '100%',
                  height: '100%',
                  borderColor: isMarked ? '#ef4444' : ann.color,
                  backgroundColor: isMarked ? 'rgba(239,68,68,0.2)' : (ann.fillColor || 'rgba(15, 23, 42, 0.85)'),
                  filter: strokeStyle.filter,
                }}
              >
                <textarea
                  defaultValue={ann.text || ''}
                  placeholder="Type note..."
                  ref={(el) => {
                    if (el && document.activeElement !== el) {
                      el.focus();
                    }
                  }}
                  onChange={(e) => {
                    const val = e.target.value;
                    const nextAnnotations = annotations.map(a => a.id === ann.id ? { ...a, text: val } : a);
                    setAnnotations(nextAnnotations);
                  }}
                  onBlur={() => {
                    setEditingTextId(null);
                    pushStateToHistory(blocks, edges, annotations);
                  }}
                  onKeyDown={(e) => {
                    e.stopPropagation();
                    if (e.key === 'Escape') {
                      e.preventDefault();
                      e.currentTarget.blur();
                    }
                  }}
                  className="annotation-note-textarea"
                  style={{
                    color: '#e2e8f0',
                    fontSize: `${ann.fontSize || 14}px`,
                  }}
                />
              </div>
            </foreignObject>
          );
        }

        return (
          <foreignObject
            key={ann.id}
            x={x}
            y={y}
            width={width}
            height={height}
            style={{ overflow: 'visible' }}
            onPointerDown={(e) => {
              if (drawTool !== 'select') {
                e.stopPropagation();
              }
            }}
            onClick={(e) => {
              if (isEraser) {
                e.stopPropagation();
                pushStateToHistory(blocks, edges, annotations);
                setAnnotations(annotations.filter(a => a.id !== ann.id));
              } else if (canvasMode === 'draw' && drawTool === 'note') {
                e.stopPropagation();
                setEditingTextId(ann.id);
              }
            }}
          >
            <div
              className={`annotation-note-container ${isSelected ? 'selected' : ''} ${isEraser ? 'hoverable-eraser' : ''}`}
              style={{
                width: '100%',
                height: '100%',
                borderColor: isMarked ? '#ef4444' : (isSelected ? '#3b82f6' : ann.color),
                backgroundColor: isMarked ? 'rgba(239,68,68,0.2)' : (ann.fillColor || 'rgba(15, 23, 42, 0.85)'),
                filter: strokeStyle.filter,
                opacity: isMarked ? 0.4 : undefined,
                cursor: isEraser ? 'cell' : (drawTool === 'select' ? 'grab' : 'pointer'),
              }}
            >
              <div className="annotation-note-content" style={{ color: isMarked ? '#ef4444' : '#e2e8f0', fontSize: `${ann.fontSize || 14}px` }}>
                {ann.text || <span className="annotation-note-placeholder">Empty Sticky Note...</span>}
              </div>
            </div>
          </foreignObject>
        );
      }
      case 'text': {
        if (isEditing) {
          return (
            <foreignObject
              key={ann.id}
              x={ann.x}
              y={(ann.y || 0) - 12}
              width={250}
              height={120}
              style={{ overflow: 'visible' }}
              onPointerDown={(e) => e.stopPropagation()}
              onPointerUp={(e) => e.stopPropagation()}
              onClick={(e) => e.stopPropagation()}
            >
              <textarea
                defaultValue={ann.text === 'Text Label' || ann.text === 'Text Note' ? '' : ann.text}
                placeholder="Type text..."
                ref={(el) => {
                  if (el && document.activeElement !== el) {
                    el.focus();
                    if (el.value === 'Text Label' || el.value === 'Text Note') {
                      el.select();
                    }
                  }
                }}
                onChange={(e) => {
                  const val = e.target.value.trim() || 'Text Label';
                  const nextAnnotations = annotations.map(a => a.id === ann.id ? { ...a, text: val } : a);
                  setAnnotations(nextAnnotations);
                }}
                onBlur={() => {
                  setEditingTextId(null);
                  pushStateToHistory(blocks, edges, annotations);
                }}
                onKeyDown={(e) => {
                  e.stopPropagation();
                  if (e.key === 'Escape') {
                    e.preventDefault();
                    e.currentTarget.blur();
                  } else if (e.key === 'Enter' && !e.shiftKey) {
                    e.preventDefault();
                    e.currentTarget.blur();
                  }
                }}
                className="annotation-text-input"
                style={{
                  color: ann.color,
                  fontSize: `${ann.fontSize || 16}px`,
                }}
              />
            </foreignObject>
          );
        }
        const { onClick: commonOnClick, ...otherCommonProps } = commonProps;
        return (
          <text
            x={ann.x}
            y={ann.y}
            fill={isMarked ? '#ef4444' : ann.color}
            fontSize={ann.fontSize || 16}
            fontFamily="'Outfit', 'Inter', sans-serif"
            fontWeight="600"
            style={{
              cursor: isEraser ? 'cell' : (drawTool === 'select' ? 'grab' : (canvasMode === 'draw' ? 'pointer' : 'default')),
              userSelect: 'none',
              filter: strokeStyle.filter,
              opacity: isMarked ? 0.4 : undefined,
            }}
            onClick={(e) => {
              if (isEraser) {
                e.stopPropagation();
                if (commonOnClick) commonOnClick(e);
              } else if (canvasMode === 'draw' && drawTool === 'text') {
                e.stopPropagation();
                setEditingTextId(ann.id);
              }
            }}
            onDoubleClick={(e) => {
              if (canvasMode === 'draw' && drawTool === 'select') {
                e.stopPropagation();
                setEditingTextId(ann.id);
              }
            }}
            {...otherCommonProps}
          >
            {(ann.text || '').split('\n').map((line, i) => (
              <tspan x={ann.x} dy={i === 0 ? 0 : '1.2em'} key={i}>
                {line}
              </tspan>
            ))}
          </text>
        );
      }
      default:
        return null;
    }
  }, [editingTextId, drawTool, canvasMode, pushStateToHistory, annotations, blocks, edges, setAnnotations, setEditingTextId, hoverPoint, markedForDeletion, selectedAnnotationId]);

  const renderSelectionBox = useCallback(() => {
    if (!selectedAnnotationId || drawTool !== 'select') return null;
    const ann = annotations.find((a) => a.id === selectedAnnotationId);
    if (!ann) return null;

    let minX = 0, minY = 0, maxX = 0, maxY = 0;

    if (ann.type === 'rectangle' || ann.type === 'note') {
      minX = ann.x ?? 0;
      minY = ann.y ?? 0;
      maxX = minX + (ann.width ?? 0);
      maxY = minY + (ann.height ?? 0);
    } else if (ann.type === 'circle') {
      const cx = ann.cx ?? 0, cy = ann.cy ?? 0;
      const rx = ann.rx !== undefined ? ann.rx : (ann.r ?? 0);
      const ry = ann.ry !== undefined ? ann.ry : (ann.r ?? 0);
      minX = cx - rx;
      minY = cy - ry;
      maxX = cx + rx;
      maxY = cy + ry;
    } else if (ann.type === 'line') {
      minX = Math.min(ann.x1 ?? 0, ann.x2 ?? 0);
      minY = Math.min(ann.y1 ?? 0, ann.y2 ?? 0);
      maxX = Math.max(ann.x1 ?? 0, ann.x2 ?? 0);
      maxY = Math.max(ann.y1 ?? 0, ann.y2 ?? 0);
    } else if (ann.type === 'pen' || ann.type === 'polyline' || ann.type === 'polygon') {
      if (!ann.points || ann.points.length === 0) return null;
      const xs = ann.points.map((p: Point) => p.x);
      const ys = ann.points.map((p: Point) => p.y);
      minX = Math.min(...xs);
      minY = Math.min(...ys);
      maxX = Math.max(...xs);
      maxY = Math.max(...ys);
    } else if (ann.type === 'text') {
      const fontSize = ann.fontSize || 16;
      const lines = (ann.text || '').split('\n');
      const w = Math.max(...lines.map((l: string) => l.length), 1) * fontSize * 0.6;
      const h = lines.length * fontSize * 1.2;
      minX = ann.x ?? 0;
      minY = (ann.y ?? 0) - fontSize;
      maxX = minX + w;
      maxY = minY + h;
    } else {
      return null;
    }

    if (ann.type === 'line') {
      const p1x = ann.x1 ?? 0;
      const p1y = ann.y1 ?? 0;
      const p2x = ann.x2 ?? 0;
      const p2y = ann.y2 ?? 0;
      return (
        <g key="selection-overlay" className="annotation-selection-overlay">
          <line
            x1={p1x}
            y1={p1y}
            x2={p2x}
            y2={p2y}
            stroke="#3b82f6"
            strokeWidth="2"
            strokeDasharray="4 4"
            style={{ pointerEvents: 'none' }}
          />
          <circle
            cx={p1x}
            cy={p1y}
            r="6"
            fill="#ffffff"
            stroke="#3b82f6"
            strokeWidth="2"
            style={{ cursor: 'crosshair', pointerEvents: 'auto' }}
            onPointerDown={(e) => {
              e.stopPropagation();
              if (onStartResize) onStartResize('p1', e);
            }}
          />
          <circle
            cx={p2x}
            cy={p2y}
            r="6"
            fill="#ffffff"
            stroke="#3b82f6"
            strokeWidth="2"
            style={{ cursor: 'crosshair', pointerEvents: 'auto' }}
            onPointerDown={(e) => {
              e.stopPropagation();
              if (onStartResize) onStartResize('p2', e);
            }}
          />
        </g>
      );
    }

    const pad = 6;
    const boxX = minX - pad;
    const boxY = minY - pad;
    const boxW = Math.max(maxX - minX + pad * 2, 20);
    const boxH = Math.max(maxY - minY + pad * 2, 20);

    const handles = [
      { key: 'nw', cx: boxX, cy: boxY, cursor: 'nwse-resize' },
      { key: 'n', cx: boxX + boxW / 2, cy: boxY, cursor: 'ns-resize' },
      { key: 'ne', cx: boxX + boxW, cy: boxY, cursor: 'nesw-resize' },
      { key: 'e', cx: boxX + boxW, cy: boxY + boxH / 2, cursor: 'ew-resize' },
      { key: 'se', cx: boxX + boxW, cy: boxY + boxH, cursor: 'nwse-resize' },
      { key: 's', cx: boxX + boxW / 2, cy: boxY + boxH, cursor: 'ns-resize' },
      { key: 'sw', cx: boxX, cy: boxY + boxH, cursor: 'nesw-resize' },
      { key: 'w', cx: boxX, cy: boxY + boxH / 2, cursor: 'ew-resize' },
    ];

    return (
      <g key="selection-overlay" className="annotation-selection-overlay">
        <rect
          x={boxX}
          y={boxY}
          width={boxW}
          height={boxH}
          fill="rgba(59, 130, 246, 0.08)"
          stroke="#3b82f6"
          strokeWidth="2"
          strokeDasharray="5 5"
          rx="6"
          ry="6"
          style={{
            pointerEvents: 'none',
            filter: 'drop-shadow(0 0 8px rgba(59, 130, 246, 0.6))',
          }}
        />
        {handles.map((h) => (
          <circle
            key={h.key}
            cx={h.cx}
            cy={h.cy}
            r="5"
            fill="#ffffff"
            stroke="#3b82f6"
            strokeWidth="2"
            style={{ cursor: h.cursor, pointerEvents: 'auto' }}
            onPointerDown={(e) => {
              e.stopPropagation();
              if (onStartResize) onStartResize(h.key, e);
            }}
          />
        ))}
      </g>
    );
  }, [selectedAnnotationId, drawTool, annotations, onStartResize]);

  if (!showAnnotations) return null;

  return (
    <svg
      className={`annotations-overlay mode-${drawTool}`}
      style={{
        position: 'absolute',
        top: 0,
        left: 0,
        width: '100%',
        height: '100%',
        pointerEvents: canvasMode === 'draw' ? 'auto' : 'none',
        // Stop the browser from panning/scrolling so a finger or pen can draw
        touchAction: canvasMode === 'draw' ? 'none' : undefined,
        zIndex: canvasMode === 'draw' ? 999 : 1,
      }}
      onPointerDown={canvasMode === 'draw' ? onMouseDown : undefined}
      onPointerMove={canvasMode === 'draw' ? onMouseMove : undefined}
      onPointerUp={canvasMode === 'draw' ? onMouseUp : undefined}
      onDoubleClick={canvasMode === 'draw' ? onDoubleClick : undefined}
      onContextMenu={(e) => { if (canvasMode === 'draw') e.preventDefault(); }}
      onWheel={canvasMode === 'draw' ? onWheel : undefined}
    >
      <defs>
        <filter id="neon-glow" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="5" result="blur" />
          <feMerge>
            <feMergeNode in="blur" />
            <feMergeNode in="SourceGraphic" />
          </feMerge>
        </filter>
      </defs>
      <g transform={`translate(${viewport.x}, ${viewport.y}) scale(${viewport.zoom})`}>
        {annotations.map((ann) => renderAnnotation(ann))}
        {currentAnnotation && renderAnnotation(currentAnnotation)}
        {renderSelectionBox()}

        {/* Eraser path visual guide */}
        {eraserPath && eraserPath.length > 1 && (
          <path
            d={eraserPath.map((p, idx) => (idx === 0 ? `M ${p.x} ${p.y}` : `L ${p.x} ${p.y}`)).join(' ')}
            fill="none"
            stroke="#ef4444"
            strokeWidth="12"
            strokeOpacity="0.3"
            strokeLinecap="round"
            strokeLinejoin="round"
            style={{ pointerEvents: 'none' }}
          />
        )}
      </g>
    </svg>
  );
};
