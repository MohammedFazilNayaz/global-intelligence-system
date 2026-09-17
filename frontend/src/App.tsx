import { useState, useEffect, useCallback } from 'react';
import { Navbar, type NavTab } from './components/Navbar';
import { DashboardView } from './views/DashboardView';
import { EconomicView } from './views/EconomicView';
import { MarketView } from './views/MarketView';
import { MarketAssetDetailView } from './views/MarketAssetDetailView';
import { EventsView } from './views/EventsView';
import { EventDetailView } from './views/EventDetailView';
import { EntitiesView } from './views/EntitiesView';
import { EntityDetailView } from './views/EntityDetailView';
import { SearchResultsView } from './views/SearchResultsView';
import { GeoMapView } from './views/GeoMapView';
import { SystemStatusView } from './views/SystemStatusView';
import { KnowledgeGraphView } from './views/KnowledgeGraphView';
import { RealTimeIntelligenceView } from './views/RealTimeIntelligenceView';

export function App() {
  const [activeTab, setActiveTab] = useState<NavTab>('dashboard');
  const [selectedClusterId, setSelectedClusterId] = useState<string | null>(null);
  const [selectedEntityId, setSelectedEntityId] = useState<string | null>(null);
  const [selectedMarketAssetId, setSelectedMarketAssetId] = useState<string | null>(null);
  const [selectedCategoryFilter, setSelectedCategoryFilter] = useState<string | undefined>(undefined);
  const [searchQuery, setSearchQuery] = useState<string>('');
  const [activeSearchTerm, setActiveSearchTerm] = useState<string | null>(null);

  // Sync hash routing so views can be reloaded and shared
  const parseHash = useCallback(() => {
    const rawHash = window.location.hash.replace(/^#/, '');
    if (!rawHash) {
      setActiveTab('dashboard');
      setSelectedClusterId(null);
      setSelectedEntityId(null);
      setSelectedMarketAssetId(null);
      setActiveSearchTerm(null);
      return;
    }

    const [pathPart, queryPart] = rawHash.split('?');
    const queryParams = new URLSearchParams(queryPart || '');

    if (pathPart.startsWith('events/')) {
      const clusterId = pathPart.replace('events/', '');
      setSelectedClusterId(clusterId);
      setActiveTab('events');
      setSelectedEntityId(null);
      setSelectedMarketAssetId(null);
      setActiveSearchTerm(null);
    } else if (pathPart.startsWith('entities/')) {
      const entityId = pathPart.replace('entities/', '');
      setSelectedEntityId(entityId);
      setActiveTab('entities');
      setSelectedClusterId(null);
      setSelectedMarketAssetId(null);
      setActiveSearchTerm(null);
    } else if (pathPart.startsWith('market/')) {
      const assetId = pathPart.replace('market/', '');
      setSelectedMarketAssetId(assetId);
      setActiveTab('market');
      setSelectedClusterId(null);
      setSelectedEntityId(null);
      setActiveSearchTerm(null);
    } else if (pathPart === 'market') {
      setActiveTab('market');
      setSelectedMarketAssetId(null);
      setSelectedClusterId(null);
      setSelectedEntityId(null);
      setActiveSearchTerm(null);
    } else if (pathPart === 'search') {
      const q = queryParams.get('q') || '';
      setActiveSearchTerm(q);
      setSearchQuery(q);
      setSelectedClusterId(null);
      setSelectedEntityId(null);
      setSelectedMarketAssetId(null);
    } else if (pathPart === 'economic') {
      setActiveTab('economic');
      setSelectedClusterId(null);
      setSelectedEntityId(null);
      setSelectedMarketAssetId(null);
      setActiveSearchTerm(null);
    } else if (pathPart === 'events') {
      setActiveTab('events');
      setSelectedClusterId(null);
      setSelectedEntityId(null);
      setSelectedMarketAssetId(null);
      setActiveSearchTerm(null);
    } else if (pathPart === 'entities') {
      setActiveTab('entities');
      setSelectedClusterId(null);
      setSelectedEntityId(null);
      setSelectedMarketAssetId(null);
      setActiveSearchTerm(null);
    } else if (pathPart === 'graph') {
      setActiveTab('graph');
      setSelectedClusterId(null);
      setSelectedEntityId(null);
      setSelectedMarketAssetId(null);
      setActiveSearchTerm(null);
    } else if (pathPart === 'map') {
      setActiveTab('map');
      setSelectedClusterId(null);
      setSelectedEntityId(null);
      setSelectedMarketAssetId(null);
      setActiveSearchTerm(null);
    } else if (pathPart === 'live') {
      setActiveTab('live');
      setSelectedClusterId(null);
      setSelectedEntityId(null);
      setSelectedMarketAssetId(null);
      setActiveSearchTerm(null);
    } else if (pathPart === 'status') {
      setActiveTab('status');
      setSelectedClusterId(null);
      setSelectedEntityId(null);
      setSelectedMarketAssetId(null);
      setActiveSearchTerm(null);
    } else {
      setActiveTab('dashboard');
      setSelectedClusterId(null);
      setSelectedEntityId(null);
      setSelectedMarketAssetId(null);
      setActiveSearchTerm(null);
    }
  }, []);

  useEffect(() => {
    parseHash();
    window.addEventListener('hashchange', parseHash);
    return () => window.removeEventListener('hashchange', parseHash);
  }, [parseHash]);

  const handleSelectTab = (tab: NavTab) => {
    setActiveTab(tab);
    setSelectedClusterId(null);
    setSelectedEntityId(null);
    setSelectedMarketAssetId(null);
    setActiveSearchTerm(null);
    window.location.hash = tab === 'dashboard' ? '' : tab;
  };

  const handleSelectCluster = (clusterId: string) => {
    setSelectedClusterId(clusterId);
    setSelectedEntityId(null);
    setSelectedMarketAssetId(null);
    window.location.hash = `events/${clusterId}`;
  };

  const handleSelectEntity = (entityId: string) => {
    setSelectedEntityId(entityId);
    setSelectedClusterId(null);
    setSelectedMarketAssetId(null);
    window.location.hash = `entities/${entityId}`;
  };

  const handleSelectMarketAsset = (assetId: string) => {
    setSelectedMarketAssetId(assetId);
    setSelectedClusterId(null);
    setSelectedEntityId(null);
    setActiveSearchTerm(null);
    window.location.hash = `market/${assetId}`;
  };

  const handleNavigateToEvents = (category?: string) => {
    setSelectedCategoryFilter(category);
    setActiveTab('events');
    setSelectedClusterId(null);
    setSelectedEntityId(null);
    setSelectedMarketAssetId(null);
    setActiveSearchTerm(null);
    window.location.hash = category ? `events?event_type=${encodeURIComponent(category)}` : 'events';
  };

  const handleSearchSubmit = () => {
    if (!searchQuery.trim()) return;
    setActiveSearchTerm(searchQuery.trim());
    setSelectedClusterId(null);
    setSelectedEntityId(null);
    setSelectedMarketAssetId(null);
    window.location.hash = `search?q=${encodeURIComponent(searchQuery.trim())}`;
  };

  return (
    <div className="app-container">
      <Navbar
        activeTab={activeTab}
        onSelectTab={handleSelectTab}
        searchQuery={searchQuery}
        onSearchChange={setSearchQuery}
        onSearchSubmit={handleSearchSubmit}
      />

      <main className="main-viewport">
        {/* If searching */}
        {activeSearchTerm ? (
          <SearchResultsView
            query={activeSearchTerm}
            onSelectCluster={handleSelectCluster}
            onSelectEntity={handleSelectEntity}
            onSelectMarketAsset={handleSelectMarketAsset}
          />
        ) : selectedClusterId ? (
          /* Cluster Detail View */
          <EventDetailView
            clusterId={selectedClusterId}
            onBack={() => {
              setSelectedClusterId(null);
              window.location.hash = 'events';
            }}
            onSelectEntity={handleSelectEntity}
            onSelectMarketAsset={handleSelectMarketAsset}
          />
        ) : selectedEntityId ? (
          /* Entity Detail View */
          <EntityDetailView
            entityId={selectedEntityId}
            onBack={() => {
              setSelectedEntityId(null);
              window.location.hash = 'entities';
            }}
            onSelectCluster={handleSelectCluster}
          />
        ) : selectedMarketAssetId ? (
          /* Market Asset Detail View */
          <MarketAssetDetailView
            assetId={selectedMarketAssetId}
            onBack={() => {
              setSelectedMarketAssetId(null);
              window.location.hash = 'market';
            }}
            onNavigateToEvent={handleSelectCluster}
          />
        ) : activeTab === 'live' ? (
          /* Real-Time Live Intelligence Feed */
          <RealTimeIntelligenceView />
        ) : activeTab === 'dashboard' ? (
          /* Dashboard Overview View */
          <DashboardView
            onSelectCluster={handleSelectCluster}
            onNavigateToEvents={handleNavigateToEvents}
            onSelectMarketAsset={handleSelectMarketAsset}
          />
        ) : activeTab === 'economic' ? (
          /* Economic Intelligence View */
          <EconomicView
            onSelectEntity={handleSelectEntity}
            onSelectCluster={handleSelectCluster}
          />
        ) : activeTab === 'market' ? (
          /* Market Intelligence View */
          <MarketView
            onNavigateToAsset={handleSelectMarketAsset}
            onNavigateToEvent={handleSelectCluster}
          />
        ) : activeTab === 'events' ? (
          /* Events Feed View */
          <EventsView
            onSelectCluster={handleSelectCluster}
            initialEventType={selectedCategoryFilter}
          />
        ) : activeTab === 'entities' ? (
          /* Entities List View */
          <EntitiesView onSelectEntity={handleSelectEntity} />
        ) : activeTab === 'graph' ? (
          /* Knowledge Graph Explorer View */
          <KnowledgeGraphView onSelectEntity={handleSelectEntity} />
        ) : activeTab === 'map' ? (
          /* Geo View */
          <GeoMapView onSelectCluster={handleSelectCluster} />
        ) : activeTab === 'status' ? (
          /* System Status View */
          <SystemStatusView />
        ) : null}
      </main>
    </div>
  );
}

export default App;
