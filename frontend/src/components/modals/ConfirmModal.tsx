import React, { useEffect, useRef } from 'react';
import { useTranslation } from '../../i18n';

interface ConfirmModalProps {
  message: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export const ConfirmModal: React.FC<ConfirmModalProps> = ({
  message,
  onConfirm,
  onCancel,
}) => {
  const { t } = useTranslation();
  const modalRef = useRef<HTMLDivElement>(null);

  // Close on escape key
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onCancel();
      } else if (e.key === 'Enter') {
        onConfirm();
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [onCancel, onConfirm]);

  return (
    <div
      className="modal-overlay"
      style={{
        zIndex: 10000, // Ensure it's above everything else
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget) {
          onCancel();
        }
      }}
    >
      <div 
        className="modal-content glass-panel" 
        ref={modalRef}
        style={{
          maxWidth: '450px',
          width: '100%',
        }}
      >
        <div className="modal-header">
          <h3>{t('modals.confirmTitle', 'Confirmation')}</h3>
          <button className="modal-close-btn" onClick={onCancel}>✕</button>
        </div>
        <div className="modal-body" style={{ padding: '24px 20px', lineHeight: '1.5' }}>
          <p style={{ margin: 0, color: 'var(--text-color)', whiteSpace: 'pre-wrap' }}>{message}</p>
        </div>
        <div className="modal-footer" style={{ padding: '16px 20px', display: 'flex', justifyContent: 'flex-end', gap: '12px' }}>
          <button 
            className="button-secondary" 
            onClick={onCancel} 
            style={{ width: '100px' }}
          >
            {t('common.cancel', 'Cancel')}
          </button>
          <button 
            className="button-primary" 
            onClick={onConfirm} 
            style={{ width: '100px', background: '#ef4444' }} // Use a danger color for confirms by default
            autoFocus
          >
            {t('modals.confirm', 'Confirm')}
          </button>
        </div>
      </div>
    </div>
  );
};
