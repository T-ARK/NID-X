import React from 'react';
import { NavLink } from 'react-router-dom';
import './NavigationRail.css';

const NAV_ITEMS = [
  { path: '/', label: 'Overview', icon: '◈' },
  { path: '/traffic', label: 'Traffic Analysis', icon: '⇅' },
  { path: '/performance', label: 'Model Performance', icon: '▦' },
  { path: '/alerts', label: 'Alerts', icon: '⚑' },
  { path: '/reports', label: 'Reports', icon: '⊞' },
  { path: '/settings', label: 'Settings', icon: '⊙' },
];

export function NavigationRail() {
  return (
    <nav className="nav-rail" aria-label="Main navigation">
      <div className="nav-brand font-mono">
        <span className="nav-brand-main">NID</span>
        <span className="nav-brand-dash text-red">-X</span>
      </div>
      <div className="nav-sep" />
      <ul className="nav-list">
        {NAV_ITEMS.map(({ path, label, icon }) => (
          <li key={path}>
            <NavLink
              to={path}
              end={path === '/'}
              className={({ isActive }) => `nav-item${isActive ? ' nav-item-active' : ''}`}
              aria-label={label}
            >
              <span className="nav-icon" aria-hidden>{icon}</span>
              <span className="nav-label">{label}</span>
            </NavLink>
          </li>
        ))}
      </ul>
      <div className="nav-footer font-mono text-mute">
        <span>NIDS</span>
        <span>ML</span>
      </div>
    </nav>
  );
}

export function MobileNavigation() {
  const [open, setOpen] = React.useState(false);
  return (
    <div className="mobile-nav">
      <button
        className="mobile-nav-toggle font-mono"
        onClick={() => setOpen(o => !o)}
        aria-expanded={open}
        aria-controls="mobile-nav-menu"
        aria-label="Toggle navigation"
      >
        <span className="text-red">NID-X</span>
        <span className="mobile-nav-icon">{open ? '✕' : '☰'}</span>
      </button>
      {open && (
        <div id="mobile-nav-menu" className="mobile-nav-menu" role="dialog" aria-label="Navigation menu">
          <ul>
            {NAV_ITEMS.map(({ path, label, icon }) => (
              <li key={path}>
                <NavLink
                  to={path}
                  end={path === '/'}
                  className={({ isActive }) => `mobile-nav-item${isActive ? ' mobile-nav-item-active' : ''}`}
                  onClick={() => setOpen(false)}
                >
                  <span aria-hidden>{icon}</span> {label}
                </NavLink>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );
}
