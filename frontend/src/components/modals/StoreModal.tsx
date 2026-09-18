/*
 * Copyright (C) 2026 Paulo Felipe Jarschel
 * 
 * This program is free software: you can redistribute it and/or modify
 * it under the terms of the GNU General Public License as published by
 * the Free Software Foundation, either version 3 of the License, or
 * (at your option) any later version.
 */

import React, { useEffect, useState, useMemo, useCallback } from 'react';
import axios from 'axios';
import { getBackendUrls } from '../../App';
import { useTranslation } from '../../i18n';

interface StoreModalProps {
  onClose: () => void;
  onRefreshRegistry?: () => void;
  initialTab?: 'browse' | 'subscriptions' | 'installed';
}

interface PackageItem {
  id: string;
  name: string;
  vendor?: string;
  vendor_slug?: string;
  type: string;
  version: string;
  description: string;
  author?: string;
  path: string;
  files?: string[];
  hashes?: Record<string, string>;
  dependencies?: string[];
  provides?: string[];
  i18n?: Record<string, { name?: string; description?: string }>;
}

interface CatalogData {
  schema_version: string;
  store_name?: string;
  official_public_key?: string;
  categories: string[];
  packages: PackageItem[];
}

interface InstalledPackage {
  id: string;
  name: string;
  version: string;
  vendor?: string;
  category?: string;
  type: string;
  path: string;
  files: string[];
  dependencies?: string[];
  installed_at: number;
  i18n?: Record<string, { name?: string; description?: string }>;
}

interface SubscriptionItem {
  type: 'category' | 'vendor' | 'package' | 'all';
  target: string;
  name?: string;
}

interface SubscriptionsData {
  auto_sync_on_startup: boolean;
  auto_install_new_in_subscriptions: boolean;
  subscriptions: SubscriptionItem[];
}

interface StoreStatusResponse {
  installed: Record<string, InstalledPackage>;
  subscriptions: SubscriptionsData;
  updates_count: number;
  available_updates: Array<{
    id: string;
    name: string;
    current_version: string;
    latest_version: string;
    vendor?: string;
  }>;
  new_in_subscriptions_count: number;
  new_in_subscriptions: Array<{
    id: string;
    name: string;
    version: string;
    vendor?: string;
    type: string;
    matched_subscription: string;
  }>;
}

export const StoreModal: React.FC<StoreModalProps> = ({ onClose, onRefreshRegistry, initialTab = 'browse' }) => {
  const { t } = useTranslation();
  const [activeTab, setActiveTab] = useState<'browse' | 'subscriptions' | 'installed'>(initialTab);
  const [catalog, setCatalog] = useState<CatalogData | null>(null);
  const [status, setStatus] = useState<StoreStatusResponse | null>(null);
  const [loading, setLoading] = useState<boolean>(true);
  const [actionInProgress, setActionInProgress] = useState<string | null>(null);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [selectedCategory, setSelectedCategory] = useState<string>('all');
  const [selectedVendor, setSelectedVendor] = useState<string>('all');
  const [message, setMessage] = useState<{ type: 'success' | 'error'; text: string } | null>(null);

  const BACKEND_URL = getBackendUrls().http;

  // Load catalog and status
  const loadData = useCallback(async (forceCatalog = false) => {
    setLoading(true);
    try {
      const [catRes, statusRes] = await Promise.all([
        axios.get(`${BACKEND_URL}/store/catalog?force=${forceCatalog}`),
        axios.get(`${BACKEND_URL}/store/status?force_catalog=${forceCatalog}`)
      ]);
      setCatalog(catRes.data.catalog);
      setStatus(statusRes.data);
    } catch (err: any) {
      console.error('Failed to fetch store data:', err);
      setMessage({ type: 'error', text: err.response?.data?.detail || err.message || 'Failed to connect to Store.' });
    } finally {
      setLoading(false);
    }
  }, [BACKEND_URL]);

  useEffect(() => {
    loadData();
  }, [loadData]);

  // Handle escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') onClose();
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // Unique vendors from catalog
  const vendors = useMemo(() => {
    if (!catalog?.packages) return [];
    const set = new Set<string>();
    catalog.packages.forEach((p) => {
      if (p.vendor) set.add(p.vendor);
    });
    return Array.from(set).sort();
  }, [catalog]);

  // Filtered packages
  const getPackageName = (pkg: { name: string; id?: string; i18n?: Record<string, { name?: string; description?: string }> }) => {
    const lang = i18n.language;
    return pkg.i18n?.[lang]?.name || pkg.i18n?.['en']?.name || pkg.name;
  };

  const getPackageDescription = (pkg: { description?: string; i18n?: Record<string, { name?: string; description?: string }> }) => {
    const lang = i18n.language;
    return pkg.i18n?.[lang]?.description || pkg.i18n?.['en']?.description || pkg.description || '';
  };

  const filteredPackages = useMemo(() => {
    if (!catalog?.packages) return [];
    return catalog.packages.filter((pkg) => {
      // Category filter
      if (selectedCategory !== 'all') {
        if (selectedCategory === 'instruments' && pkg.type !== 'instrument') return false;
        if (selectedCategory === 'blocks' && pkg.type !== 'block') return false;
        if (selectedCategory === 'clusters' && pkg.type !== 'cluster') return false;
        if (selectedCategory === 'blueprints' && pkg.type !== 'blueprint') return false;
      }

      // Vendor filter
      if (selectedVendor !== 'all' && pkg.vendor !== selectedVendor) {
        return false;
      }

      // Search query
      if (searchQuery.trim()) {
        const q = searchQuery.toLowerCase();
        const localizedName = getPackageName(pkg).toLowerCase();
        const localizedDesc = getPackageDescription(pkg).toLowerCase();
        const matchesName = pkg.name.toLowerCase().includes(q) || localizedName.includes(q);
        const matchesDesc = pkg.description?.toLowerCase().includes(q) || localizedDesc.includes(q);
        const matchesVendor = pkg.vendor?.toLowerCase().includes(q);
        const matchesId = pkg.id.toLowerCase().includes(q);
        if (!matchesName && !matchesDesc && !matchesVendor && !matchesId) {
          return false;
        }
      }

      return true;
    });
  }, [catalog, selectedCategory, selectedVendor, searchQuery]);

  // Install package
  const handleInstall = async (pkgId: string) => {
    setActionInProgress(pkgId);
    setMessage(null);
    try {
      const res = await axios.post(`${BACKEND_URL}/store/install`, { package_ids: [pkgId] });
      if (res.data.status === 'success' || res.data.status === 'partial_success') {
        const count = res.data.installed?.length || 1;
        const msg = count > 1
          ? t('storeModal.installedSuccessMulti', 'Installed {{id}} and {{count}} dependencies successfully!', { id: pkgId, count: count - 1 })
          : t('storeModal.installedSuccessSingle', 'Installed {{id}} successfully!', { id: pkgId });
        setMessage({ type: 'success', text: msg });
        await loadData();
        if (onRefreshRegistry) onRefreshRegistry();
      } else {
        setMessage({ type: 'error', text: res.data.errors?.join(', ') || 'Installation failed.' });
      }
    } catch (err: any) {
      setMessage({ type: 'error', text: err.response?.data?.detail || err.message });
    } finally {
      setActionInProgress(null);
    }
  };

  // Uninstall package
  const handleUninstall = async (pkgId: string) => {
    setActionInProgress(pkgId);
    setMessage(null);
    try {
      await axios.post(`${BACKEND_URL}/store/uninstall`, { package_id: pkgId });
      setMessage({ type: 'success', text: t('storeModal.uninstalledSuccess', 'Uninstalled {{id}}.', { id: pkgId }) });
      await loadData();
      if (onRefreshRegistry) onRefreshRegistry();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.response?.data?.detail || err.message });
    } finally {
      setActionInProgress(null);
    }
  };

  // Toggle subscription
  const handleToggleSubscribe = async (type: string, target: string, name: string, currentlySubscribed: boolean) => {
    setActionInProgress(`sub-${target}`);
    setMessage(null);
    try {
      await axios.post(`${BACKEND_URL}/store/subscribe`, {
        type,
        target,
        name,
        subscribed: !currentlySubscribed
      });
      await loadData();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.response?.data?.detail || err.message });
    } finally {
      setActionInProgress(null);
    }
  };

  // Sync subscriptions
  const handleSyncNow = async () => {
    setActionInProgress('sync');
    setMessage(null);
    try {
      const res = await axios.post(`${BACKEND_URL}/store/sync`);
      setMessage({
        type: 'success',
        text: t('storeModal.syncSuccess', 'Successfully synchronized packages!') + ` (${res.data.synced_count} updated/installed)`
      });
      await loadData();
      if (onRefreshRegistry) onRefreshRegistry();
    } catch (err: any) {
      setMessage({ type: 'error', text: err.response?.data?.detail || err.message });
    } finally {
      setActionInProgress(null);
    }
  };

  // Check if vendor or category is subscribed
  const isSubscribed = (type: string, target: string): boolean => {
    if (!status?.subscriptions?.subscriptions) return false;
    const targetLower = target.toLowerCase();
    return status.subscriptions.subscriptions.some(
      (s) => (s.type === 'all' || s.target === '*') || (s.type === type && s.target.toLowerCase() === targetLower)
    );
  };

  const getTypeIcon = (type: string) => {
    switch (type) {
      case 'instrument':
        return '🎛️';
      case 'block':
        return '🧩';
      case 'cluster':
        return '📦';
      case 'blueprint':
        return '📋';
      default:
        return '📦';
    }
  };

  const installedCount = Object.keys(status?.installed || {}).length;
  const updatesCount = status?.updates_count || 0;
  const newSubscribedCount = status?.new_in_subscriptions_count || 0;

  return (
    <div
      className="modal-overlay"
      style={{ zIndex: 10000 }}
      onClick={(e) => {
        if (e.target === e.currentTarget) onClose();
      }}
    >
      <div
        className="modal-content glass-panel nodrag nowheel"
        style={{
          maxWidth: '900px',
          width: '95%',
          height: '85vh',
          minHeight: '520px',
          display: 'flex',
          flexDirection: 'column',
          overflow: 'hidden',
          padding: 0,
        }}
      >
        {/* Header */}
        <div className="modal-header" style={{ padding: '16px 24px', borderBottom: '1px solid var(--block-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span style={{ fontSize: '1.6rem' }}>🛍️</span>
            <div>
              <h3 style={{ margin: 0, fontSize: '1.3rem', color: 'var(--text-color)' }}>
                {t('storeModal.title', 'ComfyLAB Store')}
              </h3>
              <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                {t('storeModal.subtitle', 'Modular instrument drivers, custom blocks, clusters, and blueprints')}
              </span>
            </div>
          </div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
            <button
              className="button-secondary"
              onClick={() => loadData(true)}
              title={t('topbar.reload', 'Refresh Store catalog')}
              disabled={loading}
              style={{ height: '32px', padding: '0 10px', fontSize: '0.85rem' }}
            >
              🔄 {t('common.refresh', 'Refresh')}
            </button>
            <button className="modal-close-btn" onClick={onClose} style={{ fontSize: '1.2rem', padding: '4px 8px' }}>
              ✕
            </button>
          </div>
        </div>

        {/* Message Banner */}
        {message && (
          <div
            style={{
              padding: '10px 20px',
              fontSize: '0.85rem',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'space-between',
              background: message.type === 'success' ? 'rgba(16, 185, 129, 0.15)' : 'rgba(239, 68, 68, 0.15)',
              color: message.type === 'success' ? '#10b981' : '#ef4444',
              borderBottom: '1px solid var(--block-border)'
            }}
          >
            <span>{message.text}</span>
            <button
              onClick={() => setMessage(null)}
              style={{ background: 'transparent', border: 'none', color: 'inherit', cursor: 'pointer', fontWeight: 'bold' }}
            >
              ✕
            </button>
          </div>
        )}

        {/* Tab Navigation */}
        <div style={{ display: 'flex', gap: '8px', padding: '12px 24px 0', borderBottom: '1px solid var(--block-border)', background: 'rgba(0,0,0,0.05)' }}>
          <button
            className={`button-secondary ${activeTab === 'browse' ? 'active' : ''}`}
            onClick={() => setActiveTab('browse')}
            style={{
              borderRadius: '8px 8px 0 0',
              padding: '8px 16px',
              fontWeight: 600,
              fontSize: '0.9rem',
              borderBottom: activeTab === 'browse' ? '2px solid var(--accent-color, #38bdf8)' : 'none',
              background: activeTab === 'browse' ? 'var(--bg-panel)' : 'transparent',
              color: activeTab === 'browse' ? 'var(--accent-color, #38bdf8)' : 'var(--text-muted)'
            }}
          >
            🔍 {t('storeModal.tabBrowse', 'Browse')} ({catalog?.packages?.length || 0})
          </button>

          <button
            className={`button-secondary ${activeTab === 'subscriptions' ? 'active' : ''}`}
            onClick={() => setActiveTab('subscriptions')}
            style={{
              borderRadius: '8px 8px 0 0',
              padding: '8px 16px',
              fontWeight: 600,
              fontSize: '0.9rem',
              display: 'flex',
              alignItems: 'center',
              gap: '6px',
              borderBottom: activeTab === 'subscriptions' ? '2px solid var(--accent-color, #38bdf8)' : 'none',
              background: activeTab === 'subscriptions' ? 'var(--bg-panel)' : 'transparent',
              color: activeTab === 'subscriptions' ? 'var(--accent-color, #38bdf8)' : 'var(--text-muted)'
            }}
          >
            <span>🔔 {t('storeModal.tabSubscriptions', 'Subscriptions')}</span>
            {(updatesCount > 0 || newSubscribedCount > 0) && (
              <span
                style={{
                  background: '#10b981',
                  color: '#ffffff',
                  fontSize: '0.7rem',
                  padding: '1px 6px',
                  borderRadius: '10px',
                  fontWeight: 'bold'
                }}
              >
                {updatesCount + newSubscribedCount}
              </span>
            )}
          </button>

          <button
            className={`button-secondary ${activeTab === 'installed' ? 'active' : ''}`}
            onClick={() => setActiveTab('installed')}
            style={{
              borderRadius: '8px 8px 0 0',
              padding: '8px 16px',
              fontWeight: 600,
              fontSize: '0.9rem',
              borderBottom: activeTab === 'installed' ? '2px solid var(--accent-color, #38bdf8)' : 'none',
              background: activeTab === 'installed' ? 'var(--bg-panel)' : 'transparent',
              color: activeTab === 'installed' ? 'var(--accent-color, #38bdf8)' : 'var(--text-muted)'
            }}
          >
            💾 {t('storeModal.tabInstalled', 'Installed')} ({installedCount})
          </button>
        </div>

        {/* Tab Body */}
        <div style={{ flex: 1, overflowY: 'auto', padding: '20px 24px' }}>
          {loading && !catalog ? (
            <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
              <div style={{ fontSize: '2rem', marginBottom: '10px' }}>⏳</div>
              <div>{t('common.loading', 'Loading Store catalog...')}</div>
            </div>
          ) : (
            <>
              {/* TAB 1: BROWSE */}
              {activeTab === 'browse' && (
                <div>
                  {/* First-Run Recommendation Banner */}
                  {installedCount === 0 && (
                    <div
                      style={{
                        padding: '16px',
                        borderRadius: '8px',
                        background: 'rgba(56, 189, 248, 0.1)',
                        border: '1px solid rgba(56, 189, 248, 0.3)',
                        marginBottom: '20px',
                        display: 'flex',
                        alignItems: 'center',
                        justifyContent: 'space-between',
                        gap: '16px'
                      }}
                    >
                      <div>
                        <h4 style={{ margin: '0 0 4px 0', color: '#38bdf8' }}>
                          ✨ {t('storeModal.welcomeTitle', 'Expand Your Instrument Library')}
                        </h4>
                        <p style={{ margin: 0, fontSize: '0.85rem', color: 'var(--text-color)' }}>
                          {t('storeModal.welcomeDesc', 'ComfyLAB ships with generic and virtual instruments. Use the Store to install support for your specific lab equipment.')}
                        </p>
                      </div>
                      <button
                        className="button-primary"
                        onClick={() => handleToggleSubscribe('category', 'instruments', 'All Instruments', false)}
                        disabled={actionInProgress !== null}
                        style={{ whiteSpace: 'nowrap', padding: '8px 14px', fontSize: '0.85rem' }}
                      >
                        ⚡ {t('storeModal.subscribeAllInstruments', 'Subscribe to All Instruments')}
                      </button>
                    </div>
                  )}

                  {/* Search and Filters Bar */}
                  <div style={{ display: 'flex', gap: '12px', marginBottom: '16px', flexWrap: 'wrap' }}>
                    <div style={{ flex: 1, minWidth: '220px', position: 'relative' }}>
                      <input
                        type="text"
                        placeholder={t('storeModal.searchPlaceholder', 'Search instruments, blocks, vendors...')}
                        value={searchQuery}
                        onChange={(e) => setSearchQuery(e.target.value)}
                        className="sidebar-search-input"
                        style={{ width: '100%', height: '36px', borderRadius: '6px' }}
                      />
                      {searchQuery && (
                        <button
                          onClick={() => setSearchQuery('')}
                          style={{
                            position: 'absolute',
                            right: '8px',
                            top: '50%',
                            transform: 'translateY(-50%)',
                            background: 'transparent',
                            border: 'none',
                            color: 'var(--text-muted)',
                            cursor: 'pointer'
                          }}
                        >
                          ✕
                        </button>
                      )}
                    </div>

                    <select
                      value={selectedCategory}
                      onChange={(e) => setSelectedCategory(e.target.value)}
                      className="button-secondary"
                      style={{ height: '36px', borderRadius: '6px', padding: '0 10px', fontSize: '0.85rem' }}
                    >
                      <option value="all">{t('storeModal.allCategories', 'All Categories')}</option>
                      <option value="instruments">🎛️ {t('storeModal.instruments', 'Instruments')}</option>
                      <option value="blocks">🧩 {t('storeModal.blocks', 'Blocks')}</option>
                      <option value="clusters">📦 {t('storeModal.clusters', 'Clusters')}</option>
                      <option value="blueprints">📋 {t('storeModal.blueprints', 'Blueprints')}</option>
                    </select>

                    <select
                      value={selectedVendor}
                      onChange={(e) => setSelectedVendor(e.target.value)}
                      className="button-secondary"
                      style={{ height: '36px', borderRadius: '6px', padding: '0 10px', fontSize: '0.85rem' }}
                    >
                      <option value="all">{t('storeModal.allVendors', 'All Vendors')}</option>
                      {vendors.map((v) => (
                        <option key={v} value={v}>
                          {v}
                        </option>
                      ))}
                    </select>
                  </div>

                  {/* Package Cards Grid */}
                  {filteredPackages.length === 0 ? (
                    <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                      {t('storeModal.emptyBrowse', 'No packages found matching your filter.')}
                    </div>
                  ) : (
                    <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(270px, 1fr))', gap: '14px' }}>
                      {filteredPackages.map((pkg) => {
                        const installed = status?.installed?.[pkg.id];
                        const updateInfo = status?.available_updates?.find((u) => u.id === pkg.id);
                        const isInstalled = Boolean(installed);
                        const isProcessing = actionInProgress === pkg.id;

                        return (
                          <div
                            key={pkg.id}
                            style={{
                              background: 'var(--bg-panel)',
                              border: isInstalled ? '1px solid rgba(16, 185, 129, 0.4)' : '1px solid var(--block-border)',
                              borderRadius: '8px',
                              padding: '14px',
                              display: 'flex',
                              flexDirection: 'column',
                              justifyContent: 'space-between',
                              boxShadow: '0 2px 8px rgba(0,0,0,0.05)'
                            }}
                          >
                            <div>
                              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '8px' }}>
                                <span style={{ fontSize: '1.4rem' }}>{getTypeIcon(pkg.type)}</span>
                                <div style={{ display: 'flex', gap: '6px', alignItems: 'center' }}>
                                  {pkg.vendor && (
                                    <span
                                      style={{
                                        fontSize: '0.7rem',
                                        background: 'rgba(56, 189, 248, 0.15)',
                                        color: '#38bdf8',
                                        padding: '2px 6px',
                                        borderRadius: '4px',
                                        fontWeight: 600
                                      }}
                                    >
                                      {pkg.vendor}
                                    </span>
                                  )}
                                  <span
                                    style={{
                                      fontSize: '0.7rem',
                                      background: 'rgba(100, 116, 139, 0.2)',
                                      color: 'var(--text-muted)',
                                      padding: '2px 6px',
                                      borderRadius: '4px'
                                    }}
                                  >
                                    v{pkg.version}
                                  </span>
                                </div>
                              </div>

                              <h4 style={{ margin: '0 0 6px 0', fontSize: '1rem', color: 'var(--text-color)' }}>
                                {getPackageName(pkg)}
                              </h4>
                              <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-muted)', lineHeight: '1.4', maxHeight: '56px', overflow: 'hidden' }}>
                                {getPackageDescription(pkg)}
                              </p>
                              {pkg.dependencies && pkg.dependencies.length > 0 && (
                                <div style={{ marginTop: '8px', display: 'flex', alignItems: 'center', gap: '4px', flexWrap: 'wrap' }}>
                                  <span
                                    style={{
                                      fontSize: '0.7rem',
                                      background: 'rgba(168, 85, 247, 0.15)',
                                      color: '#c084fc',
                                      padding: '2px 6px',
                                      borderRadius: '4px',
                                      display: 'inline-flex',
                                      alignItems: 'center',
                                      gap: '3px'
                                    }}
                                    title={`Dependencies:\n${pkg.dependencies.join('\n')}`}
                                  >
                                    🔗 {pkg.dependencies.length} {pkg.dependencies.length === 1 ? t('storeModal.dependencySingular', 'dependency') : t('storeModal.dependencyPlural', 'dependencies')}
                                  </span>
                                </div>
                              )}
                            </div>

                            <div style={{ marginTop: '14px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                              {isInstalled ? (
                                updateInfo ? (
                                  <button
                                    className="button-primary"
                                    onClick={() => handleInstall(pkg.id)}
                                    disabled={isProcessing}
                                    style={{ padding: '6px 12px', fontSize: '0.8rem', background: '#10b981', color: '#fff', border: 'none' }}
                                  >
                                    {isProcessing ? '⏳' : `⬆ v${updateInfo.latest_version}`}
                                  </button>
                                ) : (
                                  <span style={{ fontSize: '0.8rem', color: '#10b981', fontWeight: 600, display: 'flex', alignItems: 'center', gap: '4px' }}>
                                    ✓ {t('storeModal.installed', 'Installed')}
                                  </span>
                                )
                              ) : (
                                <button
                                  className="button-primary"
                                  onClick={() => handleInstall(pkg.id)}
                                  disabled={isProcessing}
                                  style={{ padding: '6px 14px', fontSize: '0.8rem' }}
                                >
                                  {isProcessing ? '⏳' : `➕ ${t('storeModal.install', 'Install')}`}
                                </button>
                              )}

                              {isInstalled && (
                                <button
                                  className="button-secondary"
                                  onClick={() => handleUninstall(pkg.id)}
                                  disabled={isProcessing}
                                  title={t('storeModal.uninstall', 'Uninstall')}
                                  style={{ padding: '4px 8px', fontSize: '0.75rem', color: '#ef4444' }}
                                >
                                  🗑️
                                </button>
                              )}
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  )}
                </div>
              )}

              {/* TAB 2: SUBSCRIPTIONS */}
              {activeTab === 'subscriptions' && (
                <div>
                  {/* Action Bar */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px', flexWrap: 'wrap', gap: '10px' }}>
                    <div>
                      <h4 style={{ margin: '0 0 4px 0', color: 'var(--text-color)' }}>
                        {t('storeModal.tabSubscriptions', 'Subscriptions')}
                      </h4>
                      <span style={{ fontSize: '0.85rem', color: 'var(--text-muted)' }}>
                        {t('storeModal.subscriptionsSubtitle', 'Subscribe to categories or specific instrument makers to keep them automatically installed and updated.')}
                      </span>
                    </div>

                    <button
                      className="button-primary"
                      onClick={handleSyncNow}
                      disabled={actionInProgress !== null}
                      style={{ display: 'flex', alignItems: 'center', gap: '6px', padding: '8px 16px' }}
                    >
                      <span>🔄</span>
                      <span>{actionInProgress === 'sync' ? t('storeModal.syncing', 'Syncing...') : t('storeModal.syncNow', 'Sync Now')}</span>
                      {(updatesCount > 0 || newSubscribedCount > 0) && (
                        <span style={{ background: '#ffffff', color: '#0f172a', padding: '1px 6px', borderRadius: '8px', fontSize: '0.75rem', fontWeight: 'bold' }}>
                          {updatesCount + newSubscribedCount}
                        </span>
                      )}
                    </button>
                  </div>

                  {/* Category Subscription Cards */}
                  <h5 style={{ margin: '0 0 10px 0', color: 'var(--text-color)', fontSize: '0.95rem' }}>{t('storeModal.categories', 'Categories')}</h5>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '12px', marginBottom: '24px' }}>
                    {[
                      { type: 'category', target: 'instruments', name: t('storeModal.catAllInstruments', 'All Instruments'), icon: '🎛️', desc: t('storeModal.catAllInstrumentsDesc', 'Auto-sync all lab equipment drivers and blocks.') },
                      { type: 'category', target: 'blocks', name: t('storeModal.catBlocks', 'Domain Blocks'), icon: '🧩', desc: t('storeModal.catBlocksDesc', 'Audio, signal processing, and custom utility blocks.') },
                      { type: 'category', target: 'clusters', name: t('storeModal.catClusters', 'Community Clusters'), icon: '📦', desc: t('storeModal.catClustersDesc', 'Reusable composite subgraphs & algorithms.') },
                      { type: 'category', target: 'blueprints', name: t('storeModal.catBlueprints', 'Example Blueprints'), icon: '📋', desc: t('storeModal.catBlueprintsDesc', 'Ready-to-run test & measurement workflows.') },
                    ].map((cat) => {
                      const subscribed = isSubscribed(cat.type, cat.target);
                      const isProc = actionInProgress === `sub-${cat.target}`;

                      return (
                        <div
                          key={cat.target}
                          style={{
                            background: 'var(--bg-panel)',
                            border: subscribed ? '1px solid rgba(56, 189, 248, 0.6)' : '1px solid var(--block-border)',
                            borderRadius: '8px',
                            padding: '14px',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center'
                          }}
                        >
                          <div>
                            <div style={{ display: 'flex', alignItems: 'center', gap: '6px', marginBottom: '4px' }}>
                              <span>{cat.icon}</span>
                              <strong style={{ fontSize: '0.9rem', color: 'var(--text-color)' }}>{cat.name}</strong>
                            </div>
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>{cat.desc}</span>
                          </div>

                          <button
                            className={subscribed ? 'button-primary' : 'button-secondary'}
                            onClick={() => handleToggleSubscribe(cat.type, cat.target, cat.name, subscribed)}
                            disabled={isProc}
                            style={{
                              padding: '6px 12px',
                              fontSize: '0.8rem',
                              background: subscribed ? '#0284c7' : undefined,
                              minWidth: '90px'
                            }}
                          >
                            {isProc ? '⏳' : subscribed ? t('storeModal.subscribed', 'Subscribed ✓') : t('storeModal.subscribe', 'Subscribe')}
                          </button>
                        </div>
                      );
                    })}
                  </div>

                  {/* Vendor Subscription Cards */}
                  <h5 style={{ margin: '0 0 10px 0', color: 'var(--text-color)', fontSize: '0.95rem' }}>{t('storeModal.instrumentVendors', 'Instrument Vendors')}</h5>
                  <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(260px, 1fr))', gap: '12px' }}>
                    {vendors.map((v) => {
                      const subscribed = isSubscribed('vendor', v);
                      const isProc = actionInProgress === `sub-${v}`;
                      const vendorPkgsCount = catalog?.packages?.filter((p) => p.vendor === v).length || 0;

                      return (
                        <div
                          key={v}
                          style={{
                            background: 'var(--bg-panel)',
                            border: subscribed ? '1px solid rgba(56, 189, 248, 0.6)' : '1px solid var(--block-border)',
                            borderRadius: '8px',
                            padding: '12px 14px',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center'
                          }}
                        >
                          <div>
                            <strong style={{ fontSize: '0.9rem', color: 'var(--text-color)', display: 'block' }}>{v}</strong>
                            <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
                              {vendorPkgsCount} {vendorPkgsCount === 1 ? t('storeModal.packageSingular', 'package') : t('storeModal.packagePlural', 'packages')}
                            </span>
                          </div>

                          <button
                            className={subscribed ? 'button-primary' : 'button-secondary'}
                            onClick={() => handleToggleSubscribe('vendor', v, v, subscribed)}
                            disabled={isProc}
                            style={{
                              padding: '6px 12px',
                              fontSize: '0.8rem',
                              background: subscribed ? '#0284c7' : undefined,
                              minWidth: '90px'
                            }}
                          >
                            {isProc ? '⏳' : subscribed ? t('storeModal.subscribed', 'Subscribed ✓') : t('storeModal.subscribe', 'Subscribe')}
                          </button>
                        </div>
                      );
                    })}
                  </div>
                </div>
              )}

              {/* TAB 3: INSTALLED */}
              {activeTab === 'installed' && (
                <div>
                  {installedCount === 0 ? (
                    <div style={{ textAlign: 'center', padding: '40px', color: 'var(--text-muted)' }}>
                      <div style={{ fontSize: '2.5rem', marginBottom: '10px' }}>📦</div>
                      <p>{t('storeModal.emptyInstalled', 'No Store packages currently installed.')}</p>
                      <button className="button-primary" onClick={() => setActiveTab('browse')}>
                        {t('storeModal.browseStore', 'Browse Store')}
                      </button>
                    </div>
                  ) : (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                      {Object.values(status?.installed || {}).map((pkg) => (
                        <div
                          key={pkg.id}
                          style={{
                            background: 'var(--bg-panel)',
                            border: '1px solid var(--block-border)',
                            borderRadius: '8px',
                            padding: '12px 16px',
                            display: 'flex',
                            justifyContent: 'space-between',
                            alignItems: 'center'
                          }}
                        >
                          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                            <span style={{ fontSize: '1.4rem' }}>{getTypeIcon(pkg.type)}</span>
                            <div>
                              <strong style={{ color: 'var(--text-color)' }}>{getPackageName(pkg)}</strong>
                              <div style={{ display: 'flex', gap: '8px', fontSize: '0.75rem', color: 'var(--text-muted)', marginTop: '2px' }}>
                                {pkg.vendor && <span>{pkg.vendor}</span>}
                                <span>v{pkg.version}</span>
                                <span>({pkg.files?.length || 0} {pkg.files?.length === 1 ? t('storeModal.fileSingular', 'file') : t('storeModal.filePlural', 'files')})</span>
                              </div>
                            </div>
                          </div>

                          <button
                            className="button-secondary"
                            onClick={() => handleUninstall(pkg.id)}
                            disabled={actionInProgress === pkg.id}
                            style={{ color: '#ef4444', padding: '6px 12px', fontSize: '0.8rem' }}
                          >
                            {actionInProgress === pkg.id ? '⏳' : t('storeModal.uninstall', 'Uninstall')}
                          </button>
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              )}
            </>
          )}
        </div>

        {/* Footer */}
        <div style={{ padding: '12px 24px', borderTop: '1px solid var(--block-border)', display: 'flex', justifyContent: 'space-between', alignItems: 'center', background: 'rgba(0,0,0,0.05)' }}>
          <span style={{ fontSize: '0.75rem', color: 'var(--text-muted)' }}>
            {t('storeModal.officialCatalog', 'Official Catalog')}: <a href="https://github.com/gateeit-ifgw/comfylab-store" target="_blank" rel="noreferrer" style={{ color: 'var(--accent-color, #38bdf8)' }}>gateeit-ifgw/comfylab-store</a>
          </span>
          <button className="button-secondary" onClick={onClose} style={{ padding: '6px 16px' }}>
            {t('storeModal.close', 'Close')}
          </button>
        </div>
      </div>
    </div>
  );
};
