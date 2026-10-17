import React from 'react';
import {
  Eye,
  BarChart3,
  TrendingUp,
  Activity,
  FileText,
  AlertCircle,
  ChevronLeft,
  ChevronRight,
  ShieldCheck,
  CheckCircle2
} from 'lucide-react';

export default function NavRail({
  activeTab,
  onTabChange,
  isCollapsed,
  onToggleCollapse,
  activeCase,
  caseResults,
  backendHealth,
  hasValidationErrors
}) {
  const effectiveCaseId = caseResults?.case_id || activeCase?.case_id;
  const isHealthy = backendHealth && backendHealth.status === 'healthy';

  const navItems = [
    {
      id: 'workstation',
      label: 'MRI Workstation',
      icon: Eye,
      badge: effectiveCaseId ? 'ACTIVE' : null,
      badgeColor: '#2373F4',
      desc: 'Multiplanar 2D/3D Viewer'
    },
    {
      id: 'analytics',
      label: 'Volumetric Analytics',
      icon: BarChart3,
      badge: caseResults?.regions ? 'VALID' : null,
      badgeColor: '#10B981',
      desc: 'WT, TC, ET Physical Volume (mL)'
    },
    {
      id: 'longitudinal',
      label: 'Longitudinal Compare',
      icon: TrendingUp,
      badge: 'RANO',
      badgeColor: '#578EF5',
      desc: 'Synchronized Dual-Study Viewer'
    },
    {
      id: 'trust',
      label: 'AI Trust & Uncertainty',
      icon: Activity,
      badge: null,
      desc: 'Entropy & Modality Sensitivity'
    },
    {
      id: 'audit',
      label: 'Provenance & Reports',
      icon: FileText,
      badge: 'PDF',
      badgeColor: '#64748B',
      desc: 'Audit Trail & NIfTI/DICOM-SEG'
    },
    {
      id: 'diagnostics',
      label: 'Diagnostics',
      icon: AlertCircle,
      badge: hasValidationErrors ? 'ALERT' : null,
      badgeColor: '#EF4444',
      desc: 'Spatial Affine & Header Checks'
    }
  ];

  return (
    <aside
      className={`nav-rail-sidebar ${isCollapsed ? 'collapsed' : 'expanded'}`}
      aria-label="Application Navigation Rail"
    >
      {/* Top Brand Block */}
      <div className="nav-rail-brand">
        <div className="nav-rail-logo">NS</div>
        {!isCollapsed && (
          <div className="nav-rail-brand-text">
            <span className="nav-rail-title">NeuroScope 3D</span>
            <span className="nav-rail-tagline">MONAI SegResNet mpMRI</span>
          </div>
        )}
      </div>

      {/* Navigation Items List */}
      <nav className="nav-rail-nav">
        {navItems.map((item) => {
          const Icon = item.icon;
          const isActive = activeTab === item.id;
          return (
            <button
              key={item.id}
              type="button"
              className={`nav-rail-item ${isActive ? 'active' : ''}`}
              onClick={() => onTabChange(item.id)}
              title={isCollapsed ? `${item.label} — ${item.desc}` : item.desc}
              aria-current={isActive ? 'page' : undefined}
            >
              <div className="nav-rail-item-icon-wrapper">
                <Icon size={18} className="nav-rail-icon" />
                {isCollapsed && item.badge && (
                  <span
                    className="nav-rail-dot-badge"
                    style={{ backgroundColor: item.badgeColor || 'var(--primary-accent)' }}
                  />
                )}
              </div>

              {!isCollapsed && (
                <div className="nav-rail-item-content">
                  <span className="nav-rail-item-label">{item.label}</span>
                  {item.badge && (
                    <span
                      className="nav-rail-item-badge"
                      style={item.badgeColor ? { borderColor: item.badgeColor, color: item.badgeColor } : {}}
                    >
                      {item.badge}
                    </span>
                  )}
                </div>
              )}
            </button>
          );
        })}
      </nav>

      {/* Bottom Context & Collapse Toggle */}
      <div className="nav-rail-footer">
        {!isCollapsed && (
          <div className="nav-rail-case-pill">
            <div className="nav-rail-case-indicator">
              <span className={`status-dot ${isHealthy ? 'online' : 'offline'}`} />
              <span className="nav-rail-case-id">
                {effectiveCaseId ? effectiveCaseId.substring(0, 15) : 'No Study Active'}
              </span>
            </div>
            <span className="nav-rail-case-status">
              {caseResults?.status === 'completed'
                ? 'SEGMENTED (WT/TC/ET)'
                : activeCase
                ? 'STUDY INGESTED'
                : 'STANDBY'}
            </span>
          </div>
        )}

        <button
          type="button"
          className="nav-rail-toggle-btn"
          onClick={onToggleCollapse}
          title={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          aria-label={isCollapsed ? 'Expand sidebar' : 'Collapse sidebar'}
        >
          {isCollapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          {!isCollapsed && <span style={{ fontSize: '11px', fontWeight: 500 }}>Collapse</span>}
        </button>
      </div>
    </aside>
  );
}
