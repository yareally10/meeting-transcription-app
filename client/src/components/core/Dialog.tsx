import React, { useEffect } from 'react';
import './Dialog.css';

interface DialogProps {
  isOpen: boolean;
  onClose: () => void;
  title?: string;
  children: React.ReactNode;
  className?: string;
}

const Dialog: React.FC<DialogProps> = ({
  isOpen,
  onClose,
  title,
  children,
  className = ''
}) => {
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && isOpen) {
        onClose();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [isOpen, onClose]);

  if (!isOpen) return null;

  return (
    <div className="dialog-overlay" onClick={onClose}>
      <div
        className={`dialog ${className}`}
        onClick={(e) => e.stopPropagation()}
      >
        {title && (
          <div className="dialog-header">
            <h2 className="dialog-title">{title}</h2>
            <button
              className="dialog-close"
              onClick={onClose}
              aria-label="Close dialog"
            >
              ×
            </button>
          </div>
        )}
        <div className="dialog-content">
          {children}
        </div>
      </div>
    </div>
  );
};

export default Dialog;
