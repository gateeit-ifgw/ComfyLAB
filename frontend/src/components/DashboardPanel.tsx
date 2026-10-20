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

import React, { useMemo } from 'react';
import { useTranslation } from '../i18n';
import { DashboardControlCard, DashboardMonitorCard } from './widgets/DashboardCard';
import type { DashboardItem, DashboardControlGroup } from './widgets/DashboardCard';

interface DashboardPanelProps {
  isOpen: boolean;
  onClose: () => void;
  isMaximized: boolean;
  setIsMaximized: (value: boolean | ((prev: boolean) => boolean)) => void;
  items: DashboardItem[];
  blocks: any[];
  blockRegistry: any;
  onJumpToBlock: (blockId: string) => void;
  onRemoveItem: (itemId: string) => void;
  onReorderItems: (newItems: DashboardItem[]) => void;
  onClearAll: () => void;
  onBlockDataChange: (blockId: string, key: string, value: any) => void;
  width?: number;
  onResizeHandlePointerDown?: (e: React.PointerEvent) => void;
}

export const DashboardPanel: React.FC<DashboardPanelProps> = ({
  isOpen,
  onClose,
  isMaximized,
  setIsMaximized,
  items,
  blocks,
  blockRegistry,
  onJumpToBlock,
  onRemoveItem,
  onReorderItems,
  onClearAll,
  onBlockDataChange,
  width = 440,
  onResizeHandlePointerDown,
}) => {
  const { t } = useTranslation();

  // Create lookup maps for fast access
  const blocksMap = useMemo(() => {
    const map = new Map<string, any>();
    blocks.forEach((b) => map.set(b.id, b));
    return map;
  }, [blocks]);

  // Group Controls from the same block into a single control group card, keeping monitors separate
  const { controlGroups, monitors } = useMemo(() => {
    const groupMap = new Map<string, DashboardControlGroup>();
    const groupOrder: string[] = [];
    const monList: DashboardItem[] = [];

    items.forEach((item) => {
      if (item.type === 'pin' && item.pinName) {
        if (!groupMap.has(item.blockId)) {
          groupMap.set(item.blockId, {
            id: `group_${item.blockId}`,
            blockId: item.blockId,
            pins: [{ itemId: item.id, pinName: item.pinName }],
            isConstantBlock: false,
          });
          groupOrder.push(item.blockId);
        } else {
          const grp = groupMap.get(item.blockId)!;
          if (!grp.pins.some((p) => p.pinName === item.pinName)) {
            grp.pins.push({ itemId: item.id, pinName: item.pinName });
          }
        }
      } else {
        const block = blocksMap.get(item.blockId);
        const layout = blockRegistry?.[block?.data?.action];
        const widgetType = layout?.ui_behavior?.custom_widget;
        if (widgetType === 'constant_number' || widgetType === 'constant_boolean' || widgetType === 'constant_string') {
          if (!groupMap.has(item.blockId)) {
            groupMap.set(item.blockId, {
              id: item.id,
              blockId: item.blockId,
              pins: [],
              isConstantBlock: true,
            });
            groupOrder.push(item.blockId);
          }
        } else {
          monList.push(item);
        }
      }
    });

    const groups = groupOrder.map((bId) => groupMap.get(bId)!);
    return { controlGroups: groups, monitors: monList };
  }, [items, blocksMap, blockRegistry]);

  // Reorder control groups
  const handleMoveControlGroup = (groupIndex: number, direction: 'up' | 'down') => {
    const targetIndex = direction === 'up' ? groupIndex - 1 : groupIndex + 1;
    if (targetIndex < 0 || targetIndex >= controlGroups.length) return;

    const newGroups = [...controlGroups];
    const [moved] = newGroups.splice(groupIndex, 1);
    newGroups.splice(targetIndex, 0, moved);

    const nextItems: DashboardItem[] = [];
    newGroups.forEach((g) => {
      if (g.isConstantBlock) {
        const found = items.find((i) => i.blockId === g.blockId && i.type === 'block');
        if (found) nextItems.push(found);
      } else {
        g.pins.forEach((p) => {
          const found = items.find((i) => i.id === p.itemId);
          if (found) nextItems.push(found);
        });
      }
    });
    nextItems.push(...monitors);
    onReorderItems(nextItems);
  };

  // Reorder monitors
  const handleMoveMonitor = (monitorIndex: number, direction: 'up' | 'down') => {
    const targetIndex = direction === 'up' ? monitorIndex - 1 : monitorIndex + 1;
    if (targetIndex < 0 || targetIndex >= monitors.length) return;

    const newMonitors = [...monitors];
    const [moved] = newMonitors.splice(monitorIndex, 1);
    newMonitors.splice(targetIndex, 0, moved);

    const nextItems: DashboardItem[] = [];
    controlGroups.forEach((g) => {
      if (g.isConstantBlock) {
        const found = items.find((i) => i.blockId === g.blockId && i.type === 'block');
        if (found) nextItems.push(found);
      } else {
        g.pins.forEach((p) => {
          const found = items.find((i) => i.id === p.itemId);
          if (found) nextItems.push(found);
        });
      }
    });
    nextItems.push(...newMonitors);
    onReorderItems(nextItems);
  };

  // Remove all controls of a block from dashboard
  const handleRemoveBlockControls = (blockId: string) => {
    const group = controlGroups.find((g) => g.blockId === blockId);
    if (!group) return;
    if (group.isConstantBlock) {
      const found = items.find((i) => i.blockId === blockId && i.type === 'block');
      if (found) onRemoveItem(found.id);
    } else {
      group.pins.forEach((p) => {
        onRemoveItem(p.itemId);
      });
    }
  };

  const totalCardsCount = controlGroups.length + monitors.length;

  if (!isOpen) return null;

  return (
    <div
      className={`dashboard-panel glass-panel nodrag nowheel ${isMaximized ? 'maximized' : ''}`}
      style={{ width: isMaximized ? '100%' : `${width}px` }}
      onMouseDown={(e) => e.stopPropagation()}
    >
      {/* Resizer Handle on Left Edge (when not maximized) */}
      {!isMaximized && onResizeHandlePointerDown && (
        <div
          className="sidebar-resize-handle left-edge"
          onPointerDown={onResizeHandlePointerDown}
          title={t('dashboard.resizeHandle', 'Drag to resize dashboard')}
        />
      )}

      {/* HEADER */}
      <div className="dashboard-header">
        <div className="dashboard-title-group">
          <span style={{ fontSize: '1.1rem' }}>📊</span>
          <h3 style={{ margin: 0, fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-color)' }}>
            {t('dashboard.title', 'Blueprint Dashboard')}
          </h3>
          <span className="dashboard-badge">
            {totalCardsCount} {totalCardsCount === 1 ? t('dashboard.block', 'block') : t('dashboard.blocks', 'blocks')}
          </span>
        </div>

        <div className="dashboard-header-actions">
          {items.length > 0 && (
            <button
              className="dashboard-icon-btn"
              onClick={onClearAll}
              title={t('dashboard.clearAll', 'Clear All Dashboard Items')}
            >
              🗑️
            </button>
          )}
          <button
            className="dashboard-icon-btn"
            onClick={() => setIsMaximized((prev) => !prev)}
            title={isMaximized ? t('dashboard.restore', 'Restore View') : t('dashboard.maximize', 'Maximize / Operator View')}
          >
            {isMaximized ? '⤢' : '⛶'}
          </button>
          <button
            className="dashboard-icon-btn"
            onClick={onClose}
            title={t('common.close', 'Close Dashboard')}
          >
            ✕
          </button>
        </div>
      </div>

      {/* CONTENT BODY */}
      <div className="dashboard-content">
        {totalCardsCount === 0 ? (
          <div className="dashboard-empty-state">
            <div className="dashboard-empty-icon">📊</div>
            <div style={{ fontSize: '0.95rem', fontWeight: 600, color: 'var(--text-color)' }}>
              {t('dashboard.emptyTitle', 'No Dashboard Items Yet')}
            </div>
            <div style={{ fontSize: '0.78rem', maxWidth: '280px', lineHeight: 1.4 }}>
              {t('dashboard.emptySubtitle', 'Click the 📊 icon on any block subtitle or input pin to project controls and monitors here.')}
            </div>
          </div>
        ) : (
          <>
            {/* CONTROLS SECTION */}
            {controlGroups.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div className="dashboard-section-title">
                  <span>🎛️</span>
                  <span>{t('dashboard.controlsSection', 'Controls & Parameters')}</span>
                  <span style={{ fontSize: '0.65rem', opacity: 0.6 }}>({controlGroups.length})</span>
                </div>
                <div className="dashboard-cards-grid">
                  {controlGroups.map((group, grpIdx) => {
                    const block = blocksMap.get(group.blockId);
                    const layout = blockRegistry?.[block?.data?.action];
                    return (
                      <DashboardControlCard
                        key={group.id}
                        group={group}
                        block={block}
                        layout={layout}
                        onJumpToBlock={onJumpToBlock}
                        onRemovePin={onRemoveItem}
                        onRemoveBlock={handleRemoveBlockControls}
                        onMoveUp={grpIdx > 0 ? () => handleMoveControlGroup(grpIdx, 'up') : undefined}
                        onMoveDown={grpIdx < controlGroups.length - 1 ? () => handleMoveControlGroup(grpIdx, 'down') : undefined}
                        onBlockDataChange={onBlockDataChange}
                      />
                    );
                  })}
                </div>
              </div>
            )}

            {/* MONITORS SECTION */}
            {monitors.length > 0 && (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div className="dashboard-section-title">
                  <span>📈</span>
                  <span>{t('dashboard.monitorsSection', 'Monitors & Displays')}</span>
                  <span style={{ fontSize: '0.65rem', opacity: 0.6 }}>({monitors.length})</span>
                </div>
                <div className="dashboard-cards-grid">
                  {monitors.map((item, monIdx) => {
                    const block = blocksMap.get(item.blockId);
                    const layout = blockRegistry?.[block?.data?.action];
                    return (
                      <DashboardMonitorCard
                        key={item.id}
                        item={item}
                        block={block}
                        layout={layout}
                        onJumpToBlock={onJumpToBlock}
                        onRemove={onRemoveItem}
                        onMoveUp={monIdx > 0 ? () => handleMoveMonitor(monIdx, 'up') : undefined}
                        onMoveDown={monIdx < monitors.length - 1 ? () => handleMoveMonitor(monIdx, 'down') : undefined}
                        onBlockDataChange={onBlockDataChange}
                      />
                    );
                  })}
                </div>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
};
