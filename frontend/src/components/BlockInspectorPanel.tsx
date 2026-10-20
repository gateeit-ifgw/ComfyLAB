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

import { useContext, useState, useEffect } from 'react';
import { RegistryContext } from '../context/RegistryContext';
import { getPinColor } from './ActionBlock';
import { useTranslation } from '../i18n';
import { getBlockTitle, getBlockDescription, getBlockCategory, getPinLabel } from '../utils/blockI18n';

interface PinSchema {
  name: string;
  label: string;
  type?: string;
  widget?: string;
  optional?: boolean;
  defaultVal?: any;
}

interface NodeSchema {
  name: string;
  icon: string;
  category: string;
  description: string;
  author?: string;
  filepath?: string;
  execIns: string[];
  execOuts: string[];
  dataIns: PinSchema[];
  dataOuts: { name: string; label: string; type?: string }[];
  isPassthrough?: boolean;
}

interface BlockInspectorPanelProps {
  isOpen: boolean;
  blockId: string | null;
  blocks: any[];
  edges: any[];
  onClose: () => void;
  onBlockDataChange: (id: string, key: string, value: any) => void;
  onReloadRegistry?: () => void;
  width?: number;
  onResizeHandlePointerDown?: (e: React.PointerEvent) => void;
  onToggleDashboard?: (blockId: string) => void;
  onTogglePinDashboard?: (blockId: string, pinName: string) => void;
  isBlockInDashboard?: boolean;
  dashboardPins?: string[];
}

export const BlockInspectorPanel = ({
  isOpen,
  blockId,
  blocks,
  edges,
  onClose,
  onBlockDataChange,
  onReloadRegistry,
  width,
  onResizeHandlePointerDown,
  onToggleDashboard,
  onTogglePinDashboard,
  isBlockInDashboard,
  dashboardPins = [],
}: BlockInspectorPanelProps) => {

  const { t } = useTranslation();
  const blockRegistry = useContext(RegistryContext) as Record<string, any> | null;
  const [isCopyingPath, setIsCopyingPath] = useState(false);

  const [isEditingCluster, setIsEditingCluster] = useState(false);
  const [editCategory, setEditCategory] = useState('');
  const [editIcon, setEditIcon] = useState('');
  const [editDescription, setEditDescription] = useState('');
  const [editError, setEditError] = useState<string | null>(null);

  // Close with Escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [isOpen, onClose]);

  if (!isOpen || !blockId) return null;

  // Find inspected block
  const block = blocks.find((n) => n.id === blockId);
  if (!block) return null;

  const action = block.data?.action;
  const isScriptNode = action === 'script/python';
  const isBoundary = action && (action.startsWith('cluster/boundary/') || action === 'cluster/input' || action === 'cluster/output');
  const isCluster = !isBoundary && action && (action.startsWith('user/cluster/') || action.startsWith('workspace/cluster/') || action.startsWith('builtin/cluster/') || action.startsWith('cluster/') || action.startsWith('clusters/'));
  const isLibraryCallNode = !!action && ['ffi/call', 'library/call', 'dll/so/call', 'external_libraries/dll/call'].includes(action.toLowerCase().replace(/\\/g, ''));

  // Get layout details from registry
  const registryLayout = blockRegistry?.[action] as NodeSchema | undefined;
  
  // Construct dynamic layout for script blocks or clusters if layout doesn't fully exist
  let layout: NodeSchema | undefined = registryLayout;
  if (isScriptNode && registryLayout) {
    layout = {
      ...registryLayout,
      dataIns: (block.data.customInputs || []).map((inp: any) => ({
        name: inp.name,
        label: inp.name,
        type: inp.type || 'any',
        widget: inp.widget,
        optional: inp.optional || false,
      })),
      dataOuts: (block.data.customOutputs || []).map((out: any) => ({
        name: out.name,
        label: out.name,
        type: out.type || 'any',
      })),
    };
  }

  if (action === 'math/basic/calculator' && registryLayout) {
    const variables: string[] = Array.isArray(block.data.variables)
      ? block.data.variables
      : typeof block.data.variables === 'string'
        ? block.data.variables.split(',').map((v: string) => v.trim()).filter(Boolean)
        : ['a', 'b'];
    layout = {
      ...registryLayout,
      dataIns: variables.map((v: string) => ({
        name: v,
        label: v,
        type: 'number',
        widget: 'number',
      })),
    };
  }

  if (action === 'math/signal_processing/filter' && registryLayout) {
    const filterType = block.data.FilterType ?? 'Moving Average';
    layout = {
      ...registryLayout,
      dataIns: registryLayout.dataIns.filter((pin: any) => {
        if (pin.name === 'Signal' || pin.name === 'FilterType') return true;
        if (filterType === 'Moving Average') {
          return pin.name === 'Window';
        } else if (filterType === 'Low-pass' || filterType === 'High-pass') {
          return pin.name === 'Cutoff' || pin.name === 'Order';
        } else if (filterType === 'Band-pass') {
          return pin.name === 'LowCutoff' || pin.name === 'HighCutoff' || pin.name === 'Order';
        }
        return true;
      }),
    };
  }

  const displayName = block.data?.customName || (layout ? getBlockTitle(layout) : action) || 'Unknown Block';
  const category = layout ? getBlockCategory(layout) : (isCluster ? 'Cluster' : 'General');
  const icon = layout?.icon || (isCluster ? '📦' : '⚙️');
  const description = layout ? getBlockDescription(layout) : (isCluster ? 'Custom grouped cluster block containing sub-workflows.' : '');
  const author = layout?.author || '';
  const filepath = layout?.filepath || '';

  // Copy filepath to clipboard
  const handleCopyPath = () => {
    if (!filepath) return;
    navigator.clipboard.writeText(filepath);
    setIsCopyingPath(true);
    setTimeout(() => setIsCopyingPath(false), 2000);
  };

  // Find incoming and outgoing links
  const incomingEdges = edges.filter((e) => e.target === blockId);
  const outgoingEdges = edges.filter((e) => e.source === blockId);

  // Helper to resolve block display name by ID
  const getNodeNameById = (id: string) => {
    const targetBlock = blocks.find((n) => n.id === id);
    if (!targetBlock) return 'Unknown Block';
    const targetAction = targetBlock.data?.action;
    const targetLayout = blockRegistry?.[targetAction];
    return targetBlock.data?.customName || targetLayout?.name || targetAction || id;
  };

  const handleSaveClusterMetadata = async () => {
    if (!action) return;
    setEditError(null);
    try {
      const BACKEND_URL = 'http://localhost:8000';
      // Ensure axios is available or use fetch
      const res = await fetch(`${BACKEND_URL}/blocks/update_cluster/${encodeURIComponent(action)}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          category: editCategory.trim() || 'User/Clusters',
          icon: editIcon.trim() || '📦',
          description: editDescription.trim()
        })
      });
      if (!res.ok) {
        const data = await res.json();
        throw new Error(data.detail || 'Failed to update cluster');
      }
      setIsEditingCluster(false);
      if (onReloadRegistry) {
        onReloadRegistry();
      }
    } catch (err: any) {
      setEditError(err.message);
    }
  };

  return (
    <div
      className="sidebar-container right-sidebar glass-panel nodrag nowheel animate-slide-in-right"
      style={{
        width: width ? `${width}px` : undefined,
        zIndex: 5,
        pointerEvents: 'auto',
        borderLeft: '1px solid var(--block-border)',
        boxShadow: '-10px 0 40px rgba(0, 0, 0, 0.4)',
        display: 'flex',
        flexDirection: 'column',
      }}
      onMouseDown={(e) => e.stopPropagation()}
    >
      {onResizeHandlePointerDown && (
        <div
          className="sidebar-resize-handle left-edge"
          onPointerDown={onResizeHandlePointerDown}
          title="Drag to resize inspector"
        />
      )}
      {/* HEADER */}
      <div className="sidebar-header" style={{ padding: '16px 20px' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px', flex: 1, minWidth: 0 }}>
          <div
            className="block-icon"
            style={{
              minWidth: '24px',
              height: '24px',
              fontSize: '12px',
              borderRadius: '6px',
            }}
          >
            {icon}
          </div>
          <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden', width: '100%' }}>
            <input
              type="text"
              value={displayName}
              onChange={(e) => onBlockDataChange(blockId, 'customName', e.target.value)}
              style={{
                background: 'transparent',
                border: 'none',
                borderBottom: '1px dashed transparent',
                color: 'var(--text-color)',
                fontSize: '0.95rem',
                fontWeight: 600,
                outline: 'none',
                padding: '2px 0',
                width: '100%',
                transition: 'border-color 0.2s',
              }}
              onFocus={(e) => (e.target.style.borderBottomColor = 'var(--accent-color)')}
              onBlur={(e) => (e.target.style.borderBottomColor = 'transparent')}
              placeholder="Rename block..."
              title="Click to rename block"
            />
            <span
              style={{
                fontSize: '0.65rem',
                color: 'var(--text-muted)',
                fontFamily: 'monospace',
                overflow: 'hidden',
                textOverflow: 'ellipsis',
                whiteSpace: 'nowrap',
              }}
            >
              {action}
            </span>
          </div>
        </div>
        <div style={{ display: 'flex', alignItems: 'center', gap: '6px', flexShrink: 0 }}>
          {onToggleDashboard && (
            <button
              className={`block-dashboard-btn ${isBlockInDashboard ? 'active' : ''}`}
              onClick={() => onToggleDashboard(blockId)}
              title={isBlockInDashboard ? t('dashboard.removeFromDashboard', 'Remove from Dashboard') : t('dashboard.addToDashboard', 'Add block to Dashboard')}
              style={{ fontSize: '0.85rem', padding: '3px 6px' }}
            >
              📊
            </button>
          )}
          <button
            className="sidebar-close-btn"
            onClick={onClose}
            style={{
              background: 'none',
              border: 'none',
              color: '#94a3b8',
              cursor: 'pointer',
              fontSize: '1rem',
              padding: '4px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              transition: 'color 0.15s ease',
            }}
            title="Close Inspector (Esc)"
          >
            ✕
          </button>
        </div>
      </div>


      <div className="sidebar-content" style={{ flex: 1, overflowY: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', gap: '20px' }}>
        {/* METADATA SECTION */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
            <span className="sidebar-label" style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)' }}>
              {t('inspector.description', 'Block Details')}
            </span>
            {!isEditingCluster && (
              <span
                style={{
                  fontSize: '0.65rem',
                  padding: '2px 6px',
                  borderRadius: '4px',
                  background: 'rgba(59, 130, 246, 0.15)',
                  color: '#60a5fa',
                  fontWeight: 600,
                  border: '1px solid rgba(59, 130, 246, 0.25)',
                }}
              >
                {category}
              </span>
            )}
          </div>
          
          {!isEditingCluster && description && (
            <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-color)', lineHeight: '1.4', background: 'var(--input-bg)', padding: '10px', borderRadius: '6px', border: '1px solid var(--block-border)' }}>
              {description}
            </p>
          )}

          {isCluster && !isEditingCluster && (
            <div style={{ display: 'flex', justifyContent: 'flex-start' }}>
              <button
                className="button-secondary"
                style={{ padding: '4px 12px', fontSize: '0.75rem' }}
                onClick={() => {
                  setEditCategory(category);
                  setEditIcon(icon);
                  setEditDescription(description || '');
                  setIsEditingCluster(true);
                }}
              >
                {t('inspector.editCluster', 'Edit Cluster')}
              </button>
            </div>
          )}

          {isEditingCluster && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '10px', background: 'rgba(255,255,255,0.03)', padding: '12px', borderRadius: '8px', border: '1px solid var(--block-border)' }}>
              <div style={{ display: 'flex', gap: '8px' }}>
                <div style={{ flex: 1 }}>
                  <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>{t('scriptEditor.iconLabel', 'Icon')}</label>
                  <input
                    type="text"
                    value={editIcon}
                    onChange={(e) => setEditIcon(e.target.value)}
                    style={{ background: 'var(--input-bg)', border: '1px solid var(--block-border)', color: 'var(--text-color)', padding: '6px', borderRadius: '4px', width: '100%', fontSize: '0.8rem' }}
                  />
                </div>
                <div style={{ flex: 3 }}>
                  <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>{t('scriptEditor.category', 'Category')}</label>
                  <input
                    type="text"
                    value={editCategory}
                    onChange={(e) => setEditCategory(e.target.value)}
                    style={{ background: 'var(--input-bg)', border: '1px solid var(--block-border)', color: 'var(--text-color)', padding: '6px', borderRadius: '4px', width: '100%', fontSize: '0.8rem' }}
                  />
                </div>
              </div>
              <div>
                <label style={{ fontSize: '0.7rem', color: 'var(--text-muted)', display: 'block', marginBottom: '4px' }}>{t('scriptEditor.description', 'Description')}</label>
                <textarea
                  value={editDescription}
                  onChange={(e) => setEditDescription(e.target.value)}
                  rows={2}
                  style={{ background: 'var(--input-bg)', border: '1px solid var(--block-border)', color: 'var(--text-color)', padding: '6px', borderRadius: '4px', width: '100%', fontSize: '0.8rem', resize: 'vertical' }}
                />
              </div>
              {editError && (
                <div style={{ color: '#ef4444', fontSize: '0.75rem' }}>{editError}</div>
              )}
              <div style={{ display: 'flex', gap: '8px', marginTop: '4px' }}>
                <button className="button-primary" style={{ flex: 1, padding: '6px', fontSize: '0.75rem' }} onClick={handleSaveClusterMetadata}>
                  {t('inspector.saveDefinition', 'Save Definition')}
                </button>
                <button className="button-secondary" style={{ flex: 1, padding: '6px', fontSize: '0.75rem' }} onClick={() => setIsEditingCluster(false)}>
                  {t('common.cancel', 'Cancel')}
                </button>
              </div>
            </div>
          )}

          {author && (
            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', fontSize: '0.75rem', color: 'var(--text-muted)' }}>
              <span>✍️</span>
              <span>{t('inspector.author', 'Author')}: <strong style={{ color: 'var(--text-color)' }}>{author}</strong></span>
            </div>
          )}

          {filepath && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', marginTop: '4px' }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{t('inspector.filepath', 'Source File')}:</span>
              <div
                style={{
                  display: 'flex',
                  alignItems: 'center',
                  background: 'rgba(2, 6, 23, 0.4)',
                  border: '1px solid var(--block-border)',
                  borderRadius: '6px',
                  padding: '4px 8px',
                  fontFamily: 'monospace',
                  fontSize: '0.7rem',
                  color: '#34d399',
                  overflow: 'hidden',
                }}
              >
                <span style={{ overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', flex: 1 }} title={filepath}>
                  {filepath}
                </span>
                <button
                  onClick={handleCopyPath}
                  style={{
                    background: 'none',
                    border: 'none',
                    color: isCopyingPath ? '#10b981' : 'var(--text-muted)',
                    cursor: 'pointer',
                    fontSize: '0.75rem',
                    padding: '2px 4px',
                    marginLeft: '8px',
                  }}
                  title={t('inspector.copyPath', 'Copy Path')}
                >
                  {isCopyingPath ? t('inspector.copied', 'Copied!') : '📋'}
                </button>
              </div>
            </div>
          )}

          {isCluster && block.data?.onNavigateInto && (
            <button
              className="script-edit-button nodrag"
              style={{
                background: 'linear-gradient(135deg, rgba(139, 92, 246, 0.2) 0%, rgba(99, 102, 241, 0.2) 100%)',
                border: '1px solid rgba(139, 92, 246, 0.4)',
                color: '#c4b5fd',
                marginTop: '6px',
              }}
              onClick={() => block.data.onNavigateInto(blockId, action)}
            >
              {t('inspector.openCluster', '📦 Open Cluster Blueprint')}
            </button>
          )}
        </div>

        <div className="sidebar-divider" style={{ borderBottom: '1px solid rgba(148, 163, 184, 0.08)' }} />

        {/* Library Signature Summary (read-only, library/call blocks only) */}
        {isLibraryCallNode && (() => {
          const libraryArgs: any[] = block.data?.library_args || block.data?.ffi_args || [];
          const DIRECTION_LABELS: Record<string, string> = {
            in:           'Input',
            out_buffer:   'Output (data)',
            out_ptr:      'Output (pointer data)',
            inout_buffer: 'Input/Output (data)',
            out:          'Output',
            inout:        'Input/Output',
          };
          const DIRECTION_COLORS: Record<string, string> = {
            in:           '#60a5fa',
            out_buffer:   '#34d399',
            out_ptr:      '#a78bfa',
            inout_buffer: '#f59e0b',
            out:          '#34d399',
            inout:        '#f59e0b',
          };
          return (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span className="sidebar-label" style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)' }}>
                  {t('inspector.librarySignature', 'Library Signature')}
                </span>
                <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                  {libraryArgs.length} {t('libraryEditor.argumentsCount', 'argument(s)')}
                </span>
              </div>
              {libraryArgs.length === 0 ? (
                <p style={{ margin: 0, fontSize: '0.75rem', color: 'var(--text-muted)', fontStyle: 'italic', padding: '8px', background: 'var(--input-bg)', borderRadius: '6px', border: '1px solid var(--block-border)' }}>
                  {t('inspector.noArgumentsConfigured', 'No arguments configured. Open the block and click ⚙️ Edit Signature.')}
                </p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                  {libraryArgs.map((arg: any, i: number) => {
                    const col = DIRECTION_COLORS[arg.direction] || '#64748b';
                    const lbl = DIRECTION_LABELS[arg.direction] || arg.direction;
                    return (
                      <div
                        key={i}
                        style={{
                          display: 'flex',
                          alignItems: 'center',
                          gap: '8px',
                          padding: '4px 8px',
                          background: 'var(--block-bg)',
                          border: `1px solid var(--block-border)`,
                          borderLeft: `3px solid ${col}`,
                          borderRadius: '5px',
                          fontSize: '0.7rem',
                        }}
                      >
                        <span style={{ fontFamily: 'monospace', color: 'var(--text-color)', fontWeight: 600, flex: 1, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap' }}>
                          {arg.name || `(${t('libraryEditor.unnamed', 'unnamed')})`}
                        </span>
                        <span style={{ color: '#64748b', fontFamily: 'monospace', fontSize: '0.65rem', whiteSpace: 'nowrap' }}>
                          {arg.c_type}
                        </span>
                        <span style={{ color: col, fontSize: '0.65rem', whiteSpace: 'nowrap' }}>
                          {lbl}
                        </span>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          );
        })()}

        {isLibraryCallNode && (
          <div className="sidebar-divider" style={{ borderBottom: '1px solid rgba(148, 163, 184, 0.08)' }} />
        )}

        {/* GENERAL COMMENTS / NOTES SECTION */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px' }}>
          <span className="sidebar-label" style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)' }}>
            {t('inspector.commentsNotes', 'Comments & Notes 💬')}
          </span>
          <textarea
            value={block.data?.notes || ''}
            onChange={(e) => onBlockDataChange(blockId, 'notes', e.target.value)}
            placeholder={t('inspector.notesPlaceholder', 'Add documentation, experimental setup details, or personal reminders for this block...')}
            rows={4}
            className="nodrag"
            style={{
              width: '100%',
              background: 'var(--input-bg)',
              border: '1px solid var(--block-border)',
              color: 'var(--text-color)',
              padding: '10px',
              borderRadius: '6px',
              resize: 'vertical',
              fontSize: '0.8rem',
              fontFamily: 'inherit',
              lineHeight: '1.4',
              outline: 'none',
              transition: 'border-color 0.2s',
            }}
            onFocus={(e) => (e.target.style.borderColor = 'var(--accent-color)')}
            onBlur={(e) => (e.target.style.borderColor = 'var(--block-border)')}
          />
        </div>

        <div className="sidebar-divider" style={{ borderBottom: '1px solid rgba(148, 163, 184, 0.08)' }} />

        {/* PERSISTENCE SECTION */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px', background: 'var(--input-bg)', borderRadius: '6px', border: '1px solid var(--block-border)' }}>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '2px' }}>
              <span style={{ fontSize: '0.8rem', fontWeight: 600, color: 'var(--text-color)' }}>
                {t('inspector.persistence', 'Persistent Block State')}
              </span>
              <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)' }}>
                {t('inspector.persistenceHint', 'Keep block handle/memory alive between runs')}
              </span>
            </div>
            <label className="switch" style={{ position: 'relative', display: 'inline-block', width: '38px', height: '20px' }}>
              <input
                type="checkbox"
                checked={!!block.data?.isPersistent}
                onChange={(e) => {
                  const val = e.target.checked;
                  onBlockDataChange(blockId, 'isPersistent', val);
                  if (val) {
                    onBlockDataChange(blockId, 'autoClearPersistent', true);
                  }
                }}
                style={{ opacity: 0, width: 0, height: 0 }}
              />
              <span className="slider round" style={{
                position: 'absolute', cursor: 'pointer', top: 0, left: 0, right: 0, bottom: 0,
                backgroundColor: block.data?.isPersistent ? '#10b981' : '#475569',
                transition: '0.3s', borderRadius: '20px'
              }}>
                <span style={{
                  position: 'absolute', content: '""', height: '14px', width: '14px', left: block.data?.isPersistent ? '20px' : '3px', bottom: '3px',
                  backgroundColor: 'white', transition: '0.3s', borderRadius: '50%'
                }} />
              </span>
            </label>
          </div>

          {block.data?.isPersistent && (
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', padding: '10px', background: 'var(--input-bg)', borderRadius: '6px', border: '1px solid var(--block-border)', animation: 'fadeIn 0.2s' }}>
              <div style={{ display: 'flex', flexDirection: 'column', gap: '2px', maxWidth: '80%' }}>
                <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-color)' }}>
                  {t('inspector.autoClear', 'Auto Clear Persistent Data')}
                </span>
                <span style={{ fontSize: '0.62rem', color: 'var(--text-muted)', lineHeight: '1.2' }}>
                  {t('inspector.autoClearHint', 'Re-initialize automatically if inspector parameters are modified')}
                </span>
              </div>
              <label className="switch" style={{ position: 'relative', display: 'inline-block', width: '38px', height: '20px' }}>
                <input
                  type="checkbox"
                  checked={block.data?.autoClearPersistent !== false}
                  onChange={(e) => onBlockDataChange(blockId, 'autoClearPersistent', e.target.checked)}
                  style={{ opacity: 0, width: 0, height: 0 }}
                />
                <span className="slider round" style={{
                  position: 'absolute', cursor: 'pointer', top: 0, left: 0, right: 0, bottom: 0,
                  backgroundColor: block.data?.autoClearPersistent !== false ? '#10b981' : '#475569',
                  transition: '0.3s', borderRadius: '20px'
                }}>
                  <span style={{
                    position: 'absolute', content: '""', height: '14px', width: '14px', left: block.data?.autoClearPersistent !== false ? '20px' : '3px', bottom: '3px',
                    backgroundColor: 'white', transition: '0.3s', borderRadius: '50%'
                  }} />
                </span>
              </label>
            </div>
          )}
        </div>

        <div className="sidebar-divider" style={{ borderBottom: '1px solid rgba(148, 163, 184, 0.08)' }} />

        {/* CONNECTIONS SUMMARY */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <span className="sidebar-label" style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)' }}>
            {t('inspector.incomingEdges', 'Incoming Connections')}
          </span>

          {/* Inputs list */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-color)' }}>{t('inspector.inputs', 'Input Pins')}:</span>
            {/* Exec Inputs */}
            {layout?.execIns.map((pinName) => {
              const edge = incomingEdges.find((e) => e.targetHandle === pinName);
              return (
                <div key={`in-exec-${pinName}`} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.7rem', padding: '4px 8px', background: 'rgba(167, 139, 250, 0.05)', border: '1px solid rgba(167, 139, 250, 0.15)', borderRadius: '4px' }}>
                  <span style={{ color: '#c084fc', fontWeight: 600 }}>⧓ {pinName}</span>
                  {edge ? (
                    <span style={{ color: 'var(--text-color)', textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '140px' }} title={`${getNodeNameById(edge.source)} (${edge.sourceHandle})`}>
                      ← {getNodeNameById(edge.source)}
                    </span>
                  ) : (
                    <span style={{ color: 'var(--text-muted)' }}>{t('inspector.notConnected', 'Not connected')}</span>
                  )}
                </div>
              );
            })}
            {/* Data Inputs */}
            {layout?.dataIns.map((pin) => {
              const edge = incomingEdges.find((e) => e.targetHandle === pin.name);
              const color = getPinColor(pin.type);
              const pinLabel = layout ? getPinLabel(layout, pin.name) : pin.label;
              return (
                <div key={`in-data-${pin.name}`} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', fontSize: '0.7rem', padding: '4px 8px', background: 'var(--block-bg)', border: '1px solid var(--block-border)', borderRadius: '4px' }}>
                  <div style={{ display: 'flex', alignItems: 'center', gap: '6px' }}>
                    <span style={{ color, fontWeight: 600 }}>● {pinLabel}</span>
                    {onTogglePinDashboard && (
                      <button
                        className={`pin-dashboard-btn ${dashboardPins.includes(pin.name) ? 'active' : ''}`}
                        onClick={() => onTogglePinDashboard(blockId, pin.name)}
                        title={dashboardPins.includes(pin.name) ? t('dashboard.removePinFromDashboard', 'Remove control from Dashboard') : t('dashboard.addPinToDashboard', 'Add control to Dashboard')}
                      >
                        📊
                      </button>
                    )}
                  </div>
                  {edge ? (
                    <span style={{ color: 'var(--text-color)', textAlign: 'right', overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '140px' }} title={`${getNodeNameById(edge.source)} (${edge.sourceHandle})`}>
                      ← {getNodeNameById(edge.source)}
                    </span>
                  ) : (
                    <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}>
                      Inline value ({String(block.data[pin.name] ?? pin.defaultVal ?? '')})
                    </span>
                  )}
                </div>

              );
            })}
            {(!layout || (layout.execIns.length === 0 && layout.dataIns.length === 0)) && (
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontStyle: 'italic', paddingLeft: '8px' }}>{t('inspector.noInputs', 'No input pins')}</span>
            )}
          </div>

          {/* Outputs list */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '6px' }}>
            <span style={{ fontSize: '0.75rem', fontWeight: 600, color: 'var(--text-color)' }}>{t('inspector.outputs', 'Output Pins')}:</span>
            {/* Exec Outputs */}
            {layout?.execOuts.map((pinName) => {
              const connected = outgoingEdges.filter((e) => e.sourceHandle === pinName);
              return (
                <div key={`out-exec-${pinName}`} style={{ display: 'flex', flexDirection: 'column', gap: '2px', fontSize: '0.7rem', padding: '4px 8px', background: 'rgba(167, 139, 250, 0.05)', border: '1px solid rgba(167, 139, 250, 0.15)', borderRadius: '4px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color: '#c084fc', fontWeight: 600 }}>⧓ {pinName}</span>
                    <span style={{ color: 'var(--text-muted)' }}>{connected.length} link(s)</span>
                  </div>
                  {connected.map((edge) => (
                    <div key={edge.id} style={{ display: 'flex', justifyContent: 'flex-end', color: 'var(--text-color)', fontSize: '0.65rem', paddingLeft: '10px' }}>
                      → {getNodeNameById(edge.target)} ({edge.targetHandle})
                    </div>
                  ))}
                </div>
              );
            })}
            {/* Data Outputs */}
            {layout?.dataOuts.map((pin) => {
              const connected = outgoingEdges.filter((e) => e.sourceHandle === pin.name);
              const color = getPinColor(pin.type);
              return (
                <div key={`out-data-${pin.name}`} style={{ display: 'flex', flexDirection: 'column', gap: '2px', fontSize: '0.7rem', padding: '4px 8px', background: 'var(--block-bg)', border: '1px solid var(--block-border)', borderRadius: '4px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                    <span style={{ color, fontWeight: 600 }}>● {pin.label}</span>
                    <span style={{ color: 'var(--text-muted)' }}>{connected.length} link(s)</span>
                  </div>
                  {connected.map((edge) => (
                    <div key={edge.id} style={{ display: 'flex', justifyContent: 'flex-end', color: 'var(--text-color)', fontSize: '0.65rem', paddingLeft: '10px' }}>
                      → {getNodeNameById(edge.target)} ({edge.targetHandle})
                    </div>
                  ))}
                </div>
              );
            })}
            {(!layout || (layout.execOuts.length === 0 && layout.dataOuts.length === 0)) && (
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)', fontStyle: 'italic', paddingLeft: '8px' }}>{t('inspector.noOutputs', 'No output pins')}</span>
            )}
          </div>
        </div>

        <div className="sidebar-divider" style={{ borderBottom: '1px solid rgba(148, 163, 184, 0.08)' }} />

        {/* EXECUTION DIAGNOSTICS */}
        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
          <span className="sidebar-label" style={{ fontSize: '0.75rem', textTransform: 'uppercase', letterSpacing: '0.5px', color: 'var(--text-muted)' }}>
            {t('inspector.executionStatus', 'Execution Status & Diagnostics')}
          </span>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{t('inspector.status', 'Status:')}</span>
            {(() => {
              const status = block.data?.status || 'idle';
              let badgeBg = 'rgba(148, 163, 184, 0.1)';
              let badgeBorder = 'rgba(148, 163, 184, 0.2)';
              let badgeText = '#94a3b8';

              if (status === 'running') {
                badgeBg = 'rgba(59, 130, 246, 0.15)';
                badgeBorder = 'rgba(59, 130, 246, 0.25)';
                badgeText = '#60a5fa';
              } else if (status === 'success') {
                badgeBg = 'rgba(16, 185, 129, 0.15)';
                badgeBorder = 'rgba(16, 185, 129, 0.25)';
                badgeText = '#34d399';
              } else if (status === 'error') {
                badgeBg = 'rgba(239, 68, 68, 0.15)';
                badgeBorder = 'rgba(239, 68, 68, 0.25)';
                badgeText = '#f87171';
              }

              return (
                <span
                  style={{
                    fontSize: '0.7rem',
                    fontWeight: 700,
                    textTransform: 'uppercase',
                    padding: '2px 8px',
                    borderRadius: '4px',
                    background: badgeBg,
                    border: `1px solid ${badgeBorder}`,
                    color: badgeText,
                  }}
                >
                  {status}
                </span>
              );
            })()}
          </div>

          {block.data?.resultMessage && (
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
              <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{t('inspector.resultOutput', 'Result Output:')}</span>
              <pre
                style={{
                  margin: 0,
                  fontSize: '0.7rem',
                  fontFamily: 'monospace',
                  background: 'rgba(2, 6, 23, 0.6)',
                  border: '1px solid var(--block-border)',
                  borderRadius: '6px',
                  padding: '8px 12px',
                  color: block.data?.status === 'error' ? '#f87171' : 'var(--text-color)',
                  overflowX: 'auto',
                  whiteSpace: 'pre-wrap',
                  wordBreak: 'break-all',
                }}
              >
                {block.data.resultMessage}
              </pre>
            </div>
          )}

          {/* Optional inline property visualization */}
          <div style={{ display: 'flex', flexDirection: 'column', gap: '6px', marginTop: '4px' }}>
            <span style={{ fontSize: '0.7rem', color: 'var(--text-muted)' }}>{t('inspector.blockParameters', 'Block Parameters:')}</span>
            <div style={{ display: 'flex', flexDirection: 'column', gap: '4px', background: 'rgba(2, 6, 23, 0.2)', border: '1px solid var(--block-border)', borderRadius: '6px', padding: '6px' }}>
              {Object.keys(block.data)
                .filter((key) => !['action', 'status', 'resultMessage', 'result', 'history', 'waveform', 'onChange', 'onEditScript', 'onNavigateInto', 'onInspect', 'customInputs', 'customOutputs', 'code', 'notes', 'customName', 'displayValue', 'ffi_args', 'onEditFFISignature', 'library_args', 'onEditLibrarySignature'].includes(key))
                .map((key) => (
                   <div key={`param-${key}`} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', fontSize: '0.7rem', fontFamily: 'monospace' }}>
                    <span style={{ color: 'var(--text-muted)' }}>{key}:</span>
                    <span 
                      style={{ color: 'var(--text-color)', fontWeight: 600, overflow: 'hidden', textOverflow: 'ellipsis', whiteSpace: 'nowrap', maxWidth: '140px', textAlign: 'right' }}
                      title={String(block.data[key])}
                    >
                      {(() => {
                        const valStr = String(block.data[key]);
                        return valStr.length > 30 ? valStr.substring(0, 27) + '...' : valStr;
                      })()}
                    </span>
                  </div>
                ))}
              {Object.keys(block.data).filter((key) => !['action', 'status', 'resultMessage', 'result', 'history', 'waveform', 'onChange', 'onEditScript', 'onNavigateInto', 'onInspect', 'customInputs', 'customOutputs', 'code', 'notes', 'customName', 'displayValue', 'ffi_args', 'onEditFFISignature', 'library_args', 'onEditLibrarySignature'].includes(key)).length === 0 && (
                <span style={{ fontSize: '0.65rem', color: 'var(--text-muted)', fontStyle: 'italic', textAlign: 'center' }}>No internal parameters</span>
              )}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
