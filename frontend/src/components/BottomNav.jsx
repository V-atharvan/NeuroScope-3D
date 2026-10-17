import React from 'react';
import { Layers, UploadCloud, Sliders, ShieldCheck, FileText, AlertCircle } from 'lucide-react';

export default function BottomNav({
  activeTab,
  onTabChange,
  workstationSubTab = 'viewer',
  onWorkstationSubTabChange,
  hasValidationErrors = false,
}) {
  // Navigation tabs definition
  const navItems = [
    {
      id: 'workstation-viewer',
      label: 'Viewer',
      icon: Layers,
      isActive: activeTab === 'workstation' && workstationSubTab === 'viewer',
      onClick: () => {
        onTabChange('workstation');
        if (onWorkstationSubTabChange) onWorkstationSubTabChange('viewer');
      },
    },
    {
      id: 'workstation-controls',
      label: 'Ingest & AI',
      icon: UploadCloud,
      isActive: activeTab === 'workstation' && workstationSubTab === 'controls',
      onClick: () => {
        onTabChange('workstation');
        if (onWorkstationSubTabChange) onWorkstationSubTabChange('controls');
      },
    },
    {
      id: 'workstation-series',
      label: 'Series',
      icon: Sliders,
      isActive: activeTab === 'workstation' && workstationSubTab === 'series',
      onClick: () => {
        onTabChange('workstation');
        if (onWorkstationSubTabChange) onWorkstationSubTabChange('series');
      },
    },
    {
      id: 'trust',
      label: 'Trust',
      icon: ShieldCheck,
      isActive: activeTab === 'trust',
      onClick: () => {
        onTabChange('trust');
      },
    },
    {
      id: 'audit',
      label: 'Audit',
      icon: FileText,
      isActive: activeTab === 'audit' || activeTab === 'cohort' || activeTab === 'diagnostics',
      hasBadge: hasValidationErrors,
      onClick: () => {
        // If there are validation errors, go directly to diagnostics, else audit
        if (hasValidationErrors) {
          onTabChange('diagnostics');
        } else {
          onTabChange('audit');
        }
      },
    },
  ];

  return (
    <nav className="mobile-bottom-nav" aria-label="Mobile Navigation">
      <div className="mobile-bottom-nav-inner">
        {navItems.map((item) => {
          const Icon = item.icon;
          return (
            <button
              key={item.id}
              type="button"
              className={`bottom-nav-item ${item.isActive ? 'active' : ''}`}
              onClick={item.onClick}
              aria-label={item.label}
              aria-current={item.isActive ? 'page' : undefined}
            >
              <div className="bottom-nav-icon-container">
                <Icon size={20} strokeWidth={item.isActive ? 2.2 : 1.8} />
                {item.hasBadge && (
                  <span className="bottom-nav-badge" title="Validation Alert">
                    <span className="badge-pulse" />
                  </span>
                )}
              </div>
              <span className="bottom-nav-label">{item.label}</span>
            </button>
          );
        })}
      </div>
    </nav>
  );
}
