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

import { useState } from 'react';
import { useTranslation } from '../i18n';
import { getBlockTitle, getBlockDescription } from '../utils/blockI18n';

export interface SidebarNode {
  type: string;
  name: string;
  icon: string;
  description: string;
  i18n?: Record<string, any>;
  isDevice?: boolean;
  isConnected?: boolean;
}

export interface SidebarCategoryNode {
  directNodes: SidebarNode[];
  children: Record<string, SidebarCategoryNode>;
}

interface SidebarProps {
  sidebarOpen: boolean;
  setSidebarOpen: (open: boolean) => void;
  searchQuery: string;
  setSearchQuery: (query: string) => void;
  filteredTree: Record<string, SidebarCategoryNode>;
  onReloadRegistry: () => void;
  connectedOnly: boolean;
  setConnectedOnly: (value: boolean | ((prev: boolean) => boolean)) => void;
  isScanningVisa?: boolean;
  connectedCount?: number;
  width?: number;
  onResizeHandlePointerDown?: (e: React.PointerEvent) => void;
  // Touch/pen taps on a block item add it to the canvas (HTML5 drag-and-drop is unreliable on touch screens)
  onTapAddBlock?: (type: string) => void;
}


interface CategoryTreeItemProps {
  catName: string;
  path: string;
  node: SidebarCategoryNode;
  level: number;
  searchQuery: string;
  expandedMap: Record<string, boolean>;
  toggleExpand: (path: string) => void;
  onTapAddBlock?: (type: string) => void;
}

const CategoryTreeItem = ({
  catName,
  path,
  node,
  level,
  searchQuery,
  expandedMap,
  toggleExpand,
  onTapAddBlock,
}: CategoryTreeItemProps) => {
  const isExpanded = searchQuery.trim() !== '' || expandedMap[path];
  const isTopLevel = level === 0;
  const isUserCat = isTopLevel && catName.toLowerCase() === 'user';

  const childEntries = Object.entries(node.children).sort((a, b) => a[0].localeCompare(b[0]));
  const sortedDirectNodes = [...node.directNodes].sort((a, b) => 
    getBlockTitle(a).localeCompare(getBlockTitle(b))
  );

  const displayCategoryName = catName;

  return (
    <div>
      {isUserCat && <div className="sidebar-category-separator" />}
      <div className={isTopLevel ? "sidebar-category-group" : "sidebar-subcategory-group"}>
        <div 
          className={isTopLevel ? "sidebar-category-header" : "sidebar-subcategory-header"}
          onClick={() => toggleExpand(path)}
        >
          <span className="expand-icon">{isExpanded ? '▼' : '▶'}</span>
          <span className={isTopLevel ? "category-title" : "subcategory-title"}>{displayCategoryName}</span>
        </div>

        {isExpanded && (
          <div className={isTopLevel ? "sidebar-category-content" : "sidebar-subcategory-content"}>
            {/* Direct Blocks at this level */}
            {sortedDirectNodes.map((block) => {
              const title = getBlockTitle(block);
              const desc = getBlockDescription(block);
              const isConnected = block.isConnected;
              return (
                <div 
                  key={block.type} 
                  className="dndblock" 
                  onDragStart={(e) => { e.dataTransfer.setData('application/reactflow', block.type); }} 
                  // pointerup only fires for a tap; a scroll gesture ends in pointercancel instead
                  onPointerUp={(e) => { if (e.pointerType !== 'mouse') onTapAddBlock?.(block.type); }}
                  draggable
                  title={desc}
                  style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                    <span style={{ fontSize: '0.95rem', flexShrink: 0 }}>{block.icon || '⚙️'}</span> 
                    <span style={{ overflow: 'hidden', textOverflow: 'ellipsis' }}>{title}</span>
                  </div>
                  {isConnected && (
                    <span 
                      title="Connected in lab" 
                      style={{
                        width: '8px',
                        height: '8px',
                        borderRadius: '50%',
                        backgroundColor: '#22c55e',
                        boxShadow: '0 0 6px rgba(34, 197, 94, 0.7)',
                        flexShrink: 0,
                        marginLeft: '6px'
                      }} 
                    />
                  )}
                </div>
              );
            })}

            {/* Child subcategories */}
            {childEntries.map(([childName, childNode]) => (
              <CategoryTreeItem
                key={childName}
                catName={childName}
                path={`${path}/${childName}`}
                node={childNode}
                level={level + 1}
                searchQuery={searchQuery}
                expandedMap={expandedMap}
                toggleExpand={toggleExpand}
                onTapAddBlock={onTapAddBlock}
              />
            ))}
          </div>
        )}
      </div>
    </div>
  );
};

export const Sidebar = ({
  sidebarOpen,
  setSidebarOpen,
  searchQuery,
  setSearchQuery,
  filteredTree,
  onReloadRegistry,
  connectedOnly,
  setConnectedOnly,
  isScanningVisa,
  connectedCount,
  width,
  onResizeHandlePointerDown,
  onTapAddBlock,
}: SidebarProps) => {
  const { t } = useTranslation();
  const [expandedMap, setExpandedMap] = useState<Record<string, boolean>>({});

  const toggleExpand = (path: string) => {
    setExpandedMap((prev) => ({ ...prev, [path]: !prev[path] }));
  };

  if (!sidebarOpen) return null;

  const topLevelEntries = Object.entries(filteredTree).sort((a, b) => {
    if (a[0].toLowerCase() === 'user') return 1;
    if (b[0].toLowerCase() === 'user') return -1;
    return a[0].localeCompare(b[0]);
  });

  return (
    <div 
      className="sidebar-container glass-panel nodrag nowheel"
      style={{ width: width ? `${width}px` : undefined }}
    >
      {onResizeHandlePointerDown && (
        <div 
          className="sidebar-resize-handle right-edge" 
          onPointerDown={onResizeHandlePointerDown}
          title="Drag to resize library"
        />
      )}
      <div className="sidebar-header">

        <h3>{t('sidebar.title', 'Block Library')}</h3>
        <div style={{ display: 'flex', gap: '6px' }}>
          <button
            className="button-secondary"
            onClick={onReloadRegistry}
            title={t('topbar.reload', 'Refresh block library')}
            style={{ height: '30px', padding: '0 8px', fontSize: '0.8rem' }}
          >
            <span>🔄</span>
          </button>
          <button 
            className="button-secondary library-toggle-btn active"
            onClick={() => setSidebarOpen(false)}
            title={t('common.close', 'Hide Block Library')}
            style={{ height: '30px', padding: '0 10px', fontSize: '0.8rem', gap: '6px' }}
          >
            <span>📚</span>
            <span>{t('common.close', 'Hide')}</span>
          </button>
        </div>
      </div>
      <div className="sidebar-search-container" style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
        <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
          <div style={{ position: 'relative', flex: 1 }}>
            <input
              type="text"
              placeholder={t('sidebar.search', 'Search blocks...')}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="sidebar-search-input"
              style={{ width: '100%', paddingRight: searchQuery ? '24px' : '8px' }}
            />
            {searchQuery && (
              <button 
                className="sidebar-search-clear"
                onClick={() => setSearchQuery('')}
                title={t('common.cancel', 'Clear search')}
                style={{ position: 'absolute', right: '6px', top: '50%', transform: 'translateY(-50%)' }}
              >
                ✕
              </button>
            )}
          </div>
          <button
            className={`button-secondary ${connectedOnly ? 'active' : ''}`}
            onClick={() => setConnectedOnly(prev => !prev)}
            title={t('sidebar.connectedOnlyTitle', 'Filter to show only connected instruments in the lab')}
            style={{
              height: '32px',
              padding: '0 8px',
              fontSize: '0.78rem',
              display: 'flex',
              alignItems: 'center',
              gap: '4px',
              backgroundColor: connectedOnly ? 'rgba(34, 197, 94, 0.2)' : undefined,
              borderColor: connectedOnly ? '#22c55e' : undefined,
              color: connectedOnly ? '#4ade80' : undefined,
              flexShrink: 0
            }}
          >
            <span style={{ fontSize: '0.9rem' }}>⚡</span>
            <span>{t('sidebar.connectedOnly', 'Connected')}</span>
            {typeof connectedCount === 'number' && connectedCount > 0 && (
              <span style={{
                backgroundColor: connectedOnly ? '#22c55e' : 'rgba(100, 116, 139, 0.3)',
                color: connectedOnly ? '#0f172a' : '#94a3b8',
                fontSize: '0.7rem',
                fontWeight: 'bold',
                padding: '1px 5px',
                borderRadius: '10px',
                marginLeft: '2px'
              }}>
                {connectedCount}
              </span>
            )}
          </button>
        </div>
        {isScanningVisa && (
          <div style={{ fontSize: '0.75rem', color: '#60a5fa', display: 'flex', alignItems: 'center', gap: '6px', paddingLeft: '4px' }}>
            <span style={{ display: 'inline-block', width: '10px', height: '10px', border: '2px solid rgba(96,165,250,0.3)', borderTopColor: '#60a5fa', borderRadius: '50%', animation: 'spin 1s linear infinite' }} />
            <span>{t('sidebar.scanningVisa', 'Scanning for connected instruments...')}</span>
          </div>
        )}
      </div>
      <div className="sidebar-content">
        {topLevelEntries.length === 0 && (
          <div style={{ color: '#64748b', fontSize: '0.85rem', textAlign: 'center', marginTop: '20px' }}>
            {t('sidebar.noBlocks', 'No matching blocks found')}
          </div>
        )}
        {topLevelEntries.map(([catName, node]) => (
          <CategoryTreeItem
            key={catName}
            catName={catName}
            path={catName}
            node={node}
            level={0}
            searchQuery={searchQuery}
            expandedMap={expandedMap}
            toggleExpand={toggleExpand}
            onTapAddBlock={onTapAddBlock}
          />
        ))}
      </div>
    </div>
  );
};

