import React, { useEffect, useState, useCallback } from 'react';
import axios from 'axios';
import { getBackendUrls } from '../../App';
import { useTranslation } from '../../i18n';

export interface UpdateInfo {
  status: string;
  update_available: boolean;
  current_version: string;
  latest_version: string;
  release_tag?: string;
  release_name?: string;
  release_notes?: string;
  release_url?: string;
  published_at?: string;
  asset_url?: string;
  asset_size?: number;
  pypi_wheel_url?: string;
  install_type?: string;
  from_cache?: boolean;
  network_warning?: string;
}

interface AboutModalProps {
  onClose: () => void;
  updateInfo?: UpdateInfo | null;
  onCheckUpdate?: (force?: boolean) => Promise<UpdateInfo | null>;
}

interface ServerInfo {
  port: number;
  token: string;
  local_url: string;
  remote_urls: Array<{
    ip: string;
    fqdn: string;
    display: string;
    raw_url: string;
  }>;
}

export const AboutModal: React.FC<AboutModalProps> = ({ onClose, updateInfo: initialUpdateInfo, onCheckUpdate }) => {
  const { t } = useTranslation();
  const [serverInfo, setServerInfo] = useState<ServerInfo | null>(null);
  const [showToken, setShowToken] = useState<boolean>(false);
  const [copiedKey, setCopiedKey] = useState<string | null>(null);

  // Update states
  const [updateInfo, setUpdateInfo] = useState<UpdateInfo | null>(initialUpdateInfo || null);
  const [checkingUpdates, setCheckingUpdates] = useState<boolean>(false);
  const [applyingUpdate, setApplyingUpdate] = useState<boolean>(false);
  const [updateError, setUpdateError] = useState<string | null>(null);
  const [updateSuccessMsg, setUpdateSuccessMsg] = useState<string | null>(null);
  const [restarting, setRestarting] = useState<boolean>(false);
  const [showReleaseNotes, setShowReleaseNotes] = useState<boolean>(false);

  // Close on escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onClose();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onClose]);

  // Fetch server access & security info
  useEffect(() => {
    let isMounted = true;
    const fetchServerInfo = async () => {
      try {
        const BACKEND_URL = getBackendUrls().http;
        const res = await axios.get(`${BACKEND_URL}/diagnostics/server_info`);
        if (isMounted && res.data && res.data.status === 'success') {
          setServerInfo(res.data);
        }
      } catch (err) {
        console.error('Failed to fetch server info in AboutModal:', err);
      }
    };
    fetchServerInfo();
    return () => {
      isMounted = false;
    };
  }, []);

  // Fetch or refresh update info if not supplied
  const handleCheckUpdates = useCallback(async (force = false) => {
    setCheckingUpdates(true);
    setUpdateError(null);
    try {
      if (onCheckUpdate) {
        const data = await onCheckUpdate(force);
        if (data) setUpdateInfo(data);
      } else {
        const BACKEND_URL = getBackendUrls().http;
        const res = await axios.get(`${BACKEND_URL}/updates/check${force ? '?force=true' : ''}`);
        if (res.data && res.data.status === 'success') {
          setUpdateInfo(res.data);
        }
      }
    } catch (err: any) {
      console.error('Failed to check for updates:', err);
      setUpdateError(err.response?.data?.detail || err.message || 'Failed to check updates');
    } finally {
      setCheckingUpdates(false);
    }
  }, [onCheckUpdate]);

  useEffect(() => {
    if (!initialUpdateInfo) {
      handleCheckUpdates(false);
    } else {
      setUpdateInfo(initialUpdateInfo);
    }
  }, [initialUpdateInfo, handleCheckUpdates]);

  const handleApplyUpdate = async () => {
    if (!updateInfo) return;
    setApplyingUpdate(true);
    setUpdateError(null);
    setUpdateSuccessMsg(null);
    try {
      const BACKEND_URL = getBackendUrls().http;
      const res = await axios.post(`${BACKEND_URL}/updates/apply`, {
        install_type: updateInfo.install_type,
        target_version: updateInfo.latest_version,
        wheel_url: updateInfo.pypi_wheel_url
      });
      if (res.data && res.data.status === 'success') {
        setUpdateSuccessMsg(res.data.message || t('aboutModal.updateSuccess', 'ComfyLAB was updated successfully!'));
      } else {
        setUpdateError(res.data?.message || 'Update failed');
      }
    } catch (err: any) {
      console.error('Failed to apply update:', err);
      setUpdateError(err.response?.data?.detail || err.message || 'Failed to apply update');
    } finally {
      setApplyingUpdate(false);
    }
  };

  const handleRestart = async () => {
    setRestarting(true);
    try {
      const BACKEND_URL = getBackendUrls().http;
      await axios.post(`${BACKEND_URL}/restart`);
    } catch (err) {
      console.debug('Restart call initiated:', err);
    }
    setTimeout(() => {
      window.location.reload();
    }, 2500);
  };

  const copyToClipboard = (text: string, key: string) => {
    navigator.clipboard.writeText(text);
    setCopiedKey(key);
    setTimeout(() => setCopiedKey(null), 2000);
  };

  const getInstallTypeLabel = (type?: string) => {
    switch (type) {
      case 'pip':
        return t('aboutModal.installTypePip', 'Python Package (pip)');
      case 'portable_zip':
        return t('aboutModal.installTypePortable', 'Compiled Frontend Package (Portable ZIP)');
      case 'standalone':
        return t('aboutModal.installTypeStandalone', 'Standalone Executable');
      case 'git':
        return t('aboutModal.installTypeGit', 'Git Repository Clone');
      default:
        return type || 'Unknown';
    }
  };

  return (
    <div
      className="modal-overlay"
      style={{ zIndex: 10000 }}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onClose();
        }
      }}
    >
      <div 
        className="modal-content glass-panel" 
        style={{
          maxWidth: '580px',
          width: '100%',
          maxHeight: '90vh',
          overflowY: 'auto'
        }}
      >
        <div className="modal-header">
          <h3>{t('topbar.about', 'About ComfyLAB')}</h3>
          <button className="modal-close-btn" onClick={onClose}>✕</button>
        </div>
        <div className="modal-body" style={{ padding: '24px 20px', lineHeight: '1.6', textAlign: 'center' }}>
          <h2 style={{ marginBottom: '8px', fontSize: '2rem', color: 'var(--text-color)' }}>
            <a 
              href="https://github.com/gateeit-ifgw/ComfyLAB" 
              target="_blank" 
              rel="noopener noreferrer"
              style={{ color: 'inherit', textDecoration: 'none' }}
              title={t('aboutModal.visitGithub', 'Visit ComfyLAB on GitHub')}
            >
              ComfyLAB
            </a>
          </h2>
          <div style={{ marginBottom: '6px', fontWeight: 'bold', color: 'var(--text-muted)' }}>
            {t('aboutModal.version', 'Version')} {updateInfo?.current_version || import.meta.env.VITE_APP_VERSION}
          </div>
          <div style={{ marginBottom: '20px', fontSize: '0.85rem' }}>
            <span style={{ color: 'var(--text-muted)', marginRight: '6px' }}>{t('aboutModal.homepage', 'Project Homepage:')}</span>
            <a 
              href="https://github.com/gateeit-ifgw/ComfyLAB" 
              target="_blank" 
              rel="noopener noreferrer"
              style={{ color: 'var(--accent-color, #a855f7)', textDecoration: 'none', fontWeight: 500 }}
              title={t('aboutModal.visitGithubRepo', 'Visit ComfyLAB repository on GitHub')}
            >
              https://github.com/gateeit-ifgw/ComfyLAB
            </a>
          </div>
          
          <p style={{ marginBottom: '20px', color: 'var(--text-color)', fontSize: '1.05rem' }}>
            <strong>Comfy LAB:</strong> {t('aboutModal.tagline', 'Comfortable Lab Automation Blocks')}
          </p>

          <p style={{ marginBottom: '20px', color: 'var(--text-color)' }}>
            {t('aboutModal.description', 'A flexible, block-based data acquisition and instrument control environment designed to simplify experimental workflows.')}
          </p>

          {/* Core Features Box */}
          <div style={{ textAlign: 'left', background: 'var(--input-bg)', padding: '16px', borderRadius: '8px', marginBottom: '16px', border: '1px solid var(--block-border)' }}>
            <h4 style={{ margin: '0 0 10px 0', color: 'var(--text-color)' }}>{t('aboutModal.features', 'Core Features')}</h4>
            <ul style={{ margin: '0 0 16px 0', paddingLeft: '24px', color: 'var(--text-muted)' }}>
              <li>{t('aboutModal.feature1', 'Intuitive block-based visual scripting interface')}</li>
              <li>{t('aboutModal.feature2', 'Seamless hardware interfacing via PyVISA')}</li>
              <li>{t('aboutModal.feature3', 'Real-time data visualization and array processing')}</li>
              <li>{t('aboutModal.feature4', 'Dynamic execution engine with block clustering')}</li>
            </ul>

            <h4 style={{ margin: '0 0 10px 0', color: 'var(--text-color)' }}>{t('aboutModal.poweredBy', 'Powered By')}</h4>
            <div style={{ display: 'flex', gap: '10px', flexWrap: 'wrap', color: 'var(--text-muted)', fontSize: '0.85rem' }}>
              <span style={{ padding: '4px 8px', background: 'var(--dnd-bg)', borderRadius: '4px', border: '1px solid var(--block-border)' }}>React</span>
              <span style={{ padding: '4px 8px', background: 'var(--dnd-bg)', borderRadius: '4px', border: '1px solid var(--block-border)' }}>XYFlow</span>
              <span style={{ padding: '4px 8px', background: 'var(--dnd-bg)', borderRadius: '4px', border: '1px solid var(--block-border)' }}>FastAPI</span>
              <span style={{ padding: '4px 8px', background: 'var(--dnd-bg)', borderRadius: '4px', border: '1px solid var(--block-border)' }}>PyVISA</span>
              <span style={{ padding: '4px 8px', background: 'var(--dnd-bg)', borderRadius: '4px', border: '1px solid var(--block-border)' }}>Plotly.js</span>
            </div>
          </div>

          {/* Software Updates Section */}
          <div style={{
            textAlign: 'left',
            background: updateInfo?.update_available ? 'rgba(16, 185, 129, 0.06)' : 'var(--input-bg)',
            padding: '16px',
            borderRadius: '8px',
            marginBottom: '16px',
            border: updateInfo?.update_available ? '1px solid #10b981' : '1px solid var(--block-border)',
            fontSize: '0.85rem'
          }}>
            <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '8px' }}>
              <h4 style={{ margin: 0, color: 'var(--text-color)', fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                🔄 {t('aboutModal.updateSectionTitle', 'Software Updates')}
              </h4>
              <button
                className="button-secondary"
                onClick={() => handleCheckUpdates(true)}
                disabled={checkingUpdates || applyingUpdate}
                style={{ padding: '2px 10px', fontSize: '0.75rem', height: '26px' }}
              >
                {checkingUpdates ? '⏳ ...' : t('aboutModal.checkForUpdates', 'Check for Updates')}
              </button>
            </div>

            {updateInfo?.install_type && (
              <div style={{ marginBottom: '10px', fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                <span>{t('aboutModal.installType', 'Installation Type')}: </span>
                <strong style={{ color: 'var(--text-color)' }}>{getInstallTypeLabel(updateInfo.install_type)}</strong>
              </div>
            )}

            {updateInfo?.update_available ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                <div style={{
                  background: 'var(--dnd-bg)',
                  padding: '10px 12px',
                  borderRadius: '6px',
                  border: '1px solid #10b981'
                }}>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
                    <span style={{ fontWeight: 600, color: '#10b981', fontSize: '0.9rem' }}>
                      🚀 {t('aboutModal.updateAvailableTitle', 'New Version Available: v{{version}}', { version: updateInfo.latest_version })}
                    </span>
                    {updateInfo.release_name && (
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-muted)' }}>
                        {updateInfo.release_name}
                      </span>
                    )}
                  </div>

                  {/* Release Notes toggle */}
                  {updateInfo.release_notes && (
                    <div style={{ marginTop: '8px' }}>
                      <button
                        onClick={() => setShowReleaseNotes(prev => !prev)}
                        style={{
                          background: 'transparent',
                          border: 'none',
                          color: 'var(--accent-color, #a855f7)',
                          cursor: 'pointer',
                          padding: 0,
                          fontSize: '0.78rem',
                          textDecoration: 'underline'
                        }}
                      >
                        {showReleaseNotes ? t('aboutModal.hideReleaseNotes', 'Hide Release Notes ▲') : t('aboutModal.viewReleaseNotes', 'View Release Notes ▼')}
                      </button>
                      {showReleaseNotes && (
                        <div style={{
                          marginTop: '6px',
                          maxHeight: '140px',
                          overflowY: 'auto',
                          background: 'var(--input-bg)',
                          padding: '8px 10px',
                          borderRadius: '4px',
                          fontSize: '0.75rem',
                          whiteSpace: 'pre-wrap',
                          lineHeight: '1.4',
                          border: '1px solid var(--block-border)',
                          color: 'var(--text-muted)'
                        }}>
                          {updateInfo.release_notes}
                        </div>
                      )}
                    </div>
                  )}
                </div>

                {/* Actions depending on install type */}
                {updateInfo.install_type === 'pip' && (
                  <div>
                    {!updateSuccessMsg ? (
                      <button
                        className="button-primary"
                        onClick={handleApplyUpdate}
                        disabled={applyingUpdate}
                        style={{
                          width: '100%',
                          padding: '8px 16px',
                          fontSize: '0.85rem',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '8px'
                        }}
                      >
                        {applyingUpdate ? (
                          <><span>⏳</span> {t('aboutModal.updating', 'Updating ComfyLAB...')}</>
                        ) : (
                          <><span>⬆️</span> {t('aboutModal.btnUpdatePip', 'Update ComfyLAB (pip)')}</>
                        )}
                      </button>
                    ) : null}
                  </div>
                )}

                {updateInfo.install_type === 'portable_zip' && (
                  <div>
                    {!updateSuccessMsg ? (
                      <button
                        className="button-primary"
                        onClick={handleApplyUpdate}
                        disabled={applyingUpdate}
                        style={{
                          width: '100%',
                          padding: '8px 16px',
                          fontSize: '0.85rem',
                          display: 'flex',
                          alignItems: 'center',
                          justifyContent: 'center',
                          gap: '8px'
                        }}
                      >
                        {applyingUpdate ? (
                          <><span>⏳</span> {t('aboutModal.updating', 'Updating ComfyLAB...')}</>
                        ) : (
                          <><span>📦</span> {t('aboutModal.btnUpdatePortable', 'Update ComfyLAB (Portable)')}</>
                        )}
                      </button>
                    ) : null}
                  </div>
                )}

                {updateInfo.install_type === 'standalone' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                      {t('aboutModal.standaloneUpdateHint', 'Pre-compiled executable detected. Download the latest release from GitHub.')}
                    </p>
                    <a
                      href={updateInfo.release_url || 'https://github.com/gateeit-ifgw/ComfyLAB/releases/latest'}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="button-primary"
                      style={{
                        padding: '6px 14px',
                        fontSize: '0.82rem',
                        textAlign: 'center',
                        textDecoration: 'none',
                        display: 'inline-block'
                      }}
                    >
                      {t('aboutModal.btnDownloadGitHub', 'Download from GitHub')}
                    </a>
                  </div>
                )}

                {updateInfo.install_type === 'git' && (
                  <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                    <p style={{ margin: 0, fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                      {t('aboutModal.gitUpdateHint', "Git repository detected. Update with 'git pull' in your terminal.")}
                    </p>
                    <div style={{ display: 'flex', gap: '8px' }}>
                      <code style={{ background: 'var(--dnd-bg)', padding: '4px 8px', borderRadius: '4px', border: '1px solid var(--block-border)', fontSize: '0.8rem', color: 'var(--accent-color, #a855f7)' }}>
                        git pull
                      </code>
                      <a
                        href={updateInfo.release_url || 'https://github.com/gateeit-ifgw/ComfyLAB/releases/latest'}
                        target="_blank"
                        rel="noopener noreferrer"
                        className="button-secondary"
                        style={{
                          padding: '4px 10px',
                          fontSize: '0.78rem',
                          textDecoration: 'none',
                          display: 'inline-flex',
                          alignItems: 'center'
                        }}
                      >
                        {t('aboutModal.visitGithubRepo', 'Visit GitHub')}
                      </a>
                    </div>
                  </div>
                )}

                {/* Success & Restart State */}
                {updateSuccessMsg && (
                  <div style={{
                    background: 'rgba(16, 185, 129, 0.15)',
                    padding: '10px 12px',
                    borderRadius: '6px',
                    border: '1px solid #10b981',
                    display: 'flex',
                    flexDirection: 'column',
                    gap: '8px'
                  }}>
                    <div style={{ color: '#10b981', fontWeight: 600 }}>
                      ✓ {updateSuccessMsg}
                    </div>
                    <div style={{ fontSize: '0.78rem', color: 'var(--text-muted)' }}>
                      {t('aboutModal.restartRequired', 'Please restart ComfyLAB to apply changes.')}
                    </div>
                    <button
                      className="button-primary"
                      onClick={handleRestart}
                      disabled={restarting}
                      style={{ padding: '6px 12px', fontSize: '0.82rem' }}
                    >
                      {restarting ? t('aboutModal.restarting', 'Restarting server...') : t('aboutModal.restartNow', 'Restart ComfyLAB Now')}
                    </button>
                  </div>
                )}

                {/* Error Banner */}
                {updateError && (
                  <div style={{
                    background: 'rgba(239, 68, 68, 0.15)',
                    color: '#ef4444',
                    padding: '8px 10px',
                    borderRadius: '6px',
                    fontSize: '0.78rem',
                    border: '1px solid #ef4444'
                  }}>
                    {t('aboutModal.updateFailed', 'Update failed:')} {updateError}
                  </div>
                )}
              </div>
            ) : (
              <div style={{ color: 'var(--text-muted)', fontSize: '0.82rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
                <span style={{ color: '#10b981', fontWeight: 'bold' }}>✓</span>
                <span>{t('aboutModal.upToDate', 'ComfyLAB is up to date.')} (v{updateInfo?.current_version || import.meta.env.VITE_APP_VERSION})</span>
              </div>
            )}
          </div>

          {/* Network Access & Security Section */}
          <div style={{
            textAlign: 'left',
            background: 'var(--input-bg)',
            padding: '14px 16px',
            borderRadius: '8px',
            marginBottom: '20px',
            border: '1px solid var(--block-border)',
            fontSize: '0.85rem'
          }}>
            <h4 style={{ margin: '0 0 10px 0', color: 'var(--text-color)', fontSize: '0.95rem', display: 'flex', alignItems: 'center', gap: '6px' }}>
              {t('aboutModal.networkAccess', '🌐 Network & Remote Access')}
            </h4>

            {serverInfo ? (
              <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                {/* Local Access */}
                <div>
                  <div style={{ fontWeight: 600, color: 'var(--text-muted)', marginBottom: '4px', fontSize: '0.78rem' }}>
                    {t('aboutModal.localAccess', 'LOCAL BROWSER ACCESS')}
                  </div>
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--dnd-bg)', padding: '6px 10px', borderRadius: '6px', border: '1px solid var(--block-border)' }}>
                    <code style={{ color: 'var(--accent-color, #a855f7)', fontFamily: 'monospace' }}>{serverInfo.local_url}</code>
                    <button
                      onClick={() => copyToClipboard(serverInfo.local_url, 'local')}
                      className="button-secondary"
                      style={{ padding: '2px 8px', fontSize: '0.75rem', height: 'auto' }}
                    >
                      {copiedKey === 'local' ? t('aboutModal.copied', '✓ Copied') : t('aboutModal.copy', 'Copy')}
                    </button>
                  </div>
                </div>

                {/* Remote Access */}
                {serverInfo.remote_urls && serverInfo.remote_urls.length > 0 && (
                  <div>
                    <div style={{ fontWeight: 600, color: 'var(--text-muted)', marginBottom: '4px', fontSize: '0.78rem' }}>
                      {t('aboutModal.remoteAccess', 'REMOTE ACCESS')}
                    </div>
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
                      {serverInfo.remote_urls.map((item, idx) => (
                        <div key={idx} style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--dnd-bg)', padding: '6px 10px', borderRadius: '6px', border: '1px solid var(--block-border)' }}>
                          <span style={{ fontFamily: 'monospace', color: 'var(--text-color)', fontSize: '0.78rem', wordBreak: 'break-all' }}>
                            {item.display}
                          </span>
                          <button
                            onClick={() => copyToClipboard(item.raw_url, `remote-${idx}`)}
                            className="button-secondary"
                            style={{ padding: '2px 8px', fontSize: '0.75rem', height: 'auto', flexShrink: 0, marginLeft: '8px' }}
                          >
                            {copiedKey === `remote-${idx}` ? t('aboutModal.copied', '✓ Copied') : t('aboutModal.copy', 'Copy')}
                          </button>
                        </div>
                      ))}
                    </div>
                  </div>
                )}

                {/* Remote Access Token */}
                {serverInfo.token && (
                  <div>
                    <div style={{ fontWeight: 600, color: 'var(--text-muted)', marginBottom: '4px', fontSize: '0.78rem' }}>
                      {t('aboutModal.tokenAccess', 'SESSION REMOTE ACCESS TOKEN')}
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', background: 'var(--dnd-bg)', padding: '6px 10px', borderRadius: '6px', border: '1px solid var(--block-border)' }}>
                      <code style={{ color: 'var(--text-color)', fontFamily: 'monospace', fontWeight: 'bold' }}>
                        {showToken ? serverInfo.token : '••••••••••••'}
                      </code>
                      <div style={{ display: 'flex', gap: '6px' }}>
                        <button
                          onClick={() => setShowToken(!showToken)}
                          className="button-secondary"
                          style={{ padding: '2px 8px', fontSize: '0.75rem', height: 'auto' }}
                          title={showToken ? t('aboutModal.hideTokenTitle', "Hide Access Token") : t('aboutModal.showTokenTitle', "Show Access Token")}
                        >
                          {showToken ? t('aboutModal.hideToken', '👁 Hide') : t('aboutModal.showToken', '👁 Show')}
                        </button>
                        <button
                          onClick={() => copyToClipboard(serverInfo.token, 'token')}
                          className="button-secondary"
                          style={{ padding: '2px 8px', fontSize: '0.75rem', height: 'auto' }}
                        >
                          {copiedKey === 'token' ? t('aboutModal.copied', '✓ Copied') : t('aboutModal.copy', 'Copy')}
                        </button>
                      </div>
                    </div>
                  </div>
                )}
              </div>
            ) : (
              <div style={{ color: 'var(--text-muted)', fontSize: '0.8rem', fontStyle: 'italic' }}>
                {t('aboutModal.loadingNetwork', 'Loading network access details...')}
              </div>
            )}
          </div>

          <div style={{ fontSize: '0.9rem', color: 'var(--text-muted)', marginTop: '20px' }}>
            <p>{t('aboutModal.copyright', 'Copyright © 2026 Paulo Felipe Jarschel')}</p>
            <p>{t('aboutModal.license', 'Released under the GNU General Public License v3.0')}</p>
          </div>
        </div>
        <div className="modal-footer" style={{ padding: '16px 20px', display: 'flex', justifyContent: 'center' }}>
          <button 
            className="button-secondary" 
            onClick={onClose} 
            style={{ width: '120px' }}
            autoFocus
          >
            {t('common.close', 'Close')}
          </button>
        </div>
      </div>
    </div>
  );
};
