import React from 'react';

export type NavTab = 'dashboard' | 'live' | 'events' | 'economic' | 'market' | 'entities' | 'graph' | 'map' | 'status';

interface NavbarProps {
  activeTab: NavTab;
  onSelectTab: (tab: NavTab) => void;
  searchQuery: string;
  onSearchChange: (q: string) => void;
  onSearchSubmit: () => void;
}

export const Navbar: React.FC<NavbarProps> = ({
  activeTab,
  onSelectTab,
  searchQuery,
  onSearchChange,
  onSearchSubmit,
}) => {
  return (
    <header className="navbar">
      <div className="brand-section">
        <svg
          className="brand-icon"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="12" cy="12" r="10" />
          <line x1="2" y1="12" x2="22" y2="12" />
          <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
        </svg>
        <span className="brand-title">Global Intelligence</span>
        <span className="brand-version">V0.8</span>
      </div>

      <nav className="nav-links">
        <button
          className={`nav-item ${activeTab === 'dashboard' ? 'active' : ''}`}
          onClick={() => onSelectTab('dashboard')}
        >
          Overview
        </button>
        <button
          className={`nav-item ${activeTab === 'live' ? 'active' : ''}`}
          onClick={() => onSelectTab('live')}
          style={{ position: 'relative' }}
        >
          <span style={{ display: 'inline-block', width: '6px', height: '6px', borderRadius: '50%', background: 'var(--accent-emerald)', marginRight: '5px' }}></span>
          Live Feed
        </button>
        <button
          className={`nav-item ${activeTab === 'economic' ? 'active' : ''}`}
          onClick={() => onSelectTab('economic')}
        >
          Economic Desk
        </button>
        <button
          className={`nav-item ${activeTab === 'market' ? 'active' : ''}`}
          onClick={() => onSelectTab('market')}
        >
          Market Desk
        </button>
        <button
          className={`nav-item ${activeTab === 'events' ? 'active' : ''}`}
          onClick={() => onSelectTab('events')}
        >
          Event Feed
        </button>
        <button
          className={`nav-item ${activeTab === 'entities' ? 'active' : ''}`}
          onClick={() => onSelectTab('entities')}
        >
          Entities
        </button>
        <button
          className={`nav-item ${activeTab === 'graph' ? 'active' : ''}`}
          onClick={() => onSelectTab('graph')}
        >
          Knowledge Graph
        </button>
        <button
          className={`nav-item ${activeTab === 'map' ? 'active' : ''}`}
          onClick={() => onSelectTab('map')}
        >
          Geo View
        </button>
        <button
          className={`nav-item ${activeTab === 'status' ? 'active' : ''}`}
          onClick={() => onSelectTab('status')}
        >
          System Health
        </button>
      </nav>

      <div className="search-container">
        <svg
          className="search-icon-pos"
          viewBox="0 0 24 24"
          fill="none"
          stroke="currentColor"
          strokeWidth="2"
          strokeLinecap="round"
          strokeLinejoin="round"
        >
          <circle cx="11" cy="11" r="8" />
          <line x1="21" y1="21" x2="16.65" y2="16.65" />
        </svg>
        <input
          type="text"
          className="search-input"
          placeholder="Search events, entities, markets (e.g. BTC, Fed + S&P 500)..."
          value={searchQuery}
          onChange={(e) => onSearchChange(e.target.value)}
          onKeyDown={(e) => {
            if (e.key === 'Enter') {
              onSearchSubmit();
            }
          }}
        />
      </div>
    </header>
  );
};
