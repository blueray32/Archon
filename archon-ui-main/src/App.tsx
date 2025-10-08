import { useState, useEffect, lazy, Suspense } from 'react';
import { BrowserRouter as Router, Routes, Route, Navigate } from 'react-router-dom';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
const ReactQueryDevtoolsLazy = lazy(() =>
  import('@tanstack/react-query-devtools').then((m) => ({ default: m.ReactQueryDevtools })),
);
const KnowledgeBasePage = lazy(() =>
  import('./pages/KnowledgeBasePage').then((m) => ({ default: m.KnowledgeBasePage })),
);
const SettingsPage = lazy(() =>
  import('./pages/SettingsPage').then((m) => ({ default: m.SettingsPage })),
);
const MCPPage = lazy(() => import('./pages/MCPPage').then((m) => ({ default: m.MCPPage })));
const EmbeddingsPage = lazy(() =>
  import('./pages/EmbeddingsPage').then((m) => ({ default: m.EmbeddingsPage })),
);
const EvalPage = lazy(() => import('./pages/EvalPage').then((m) => ({ default: m.EvalPage })));
const ObsidianSyncPage = lazy(() =>
  import('./pages/ObsidianSyncPage').then((m) => ({ default: m.ObsidianSyncPage })),
);
const TagsPage = lazy(() =>
  import('./pages/TagsPage').then((m) => ({ default: m.TagsPage })),
);
const OnboardingPage = lazy(() =>
  import('./pages/OnboardingPage').then((m) => ({ default: m.OnboardingPage })),
);
import { MainLayout } from './components/layout/MainLayout';
import { ThemeProvider } from './contexts/ThemeContext';
import { ToastProvider } from './contexts/ToastContext';
import { ToastProvider as FeaturesToastProvider } from './features/ui/components/ToastProvider';
import { SettingsProvider, useSettings } from './contexts/SettingsContext';
import { TooltipProvider } from './features/ui/primitives/tooltip';
const ProjectPage = lazy(() =>
  import('./pages/ProjectPage').then((m) => ({ default: m.ProjectPage })),
);
import { DisconnectScreenOverlay } from './components/DisconnectScreenOverlay';
import { ErrorBoundaryWithBugReport } from './components/bug-report/ErrorBoundaryWithBugReport';
import { MigrationBanner } from './components/ui/MigrationBanner';
import { serverHealthService } from './services/serverHealthService';
import { useMigrationStatus } from './hooks/useMigrationStatus';

const CONFIGCAT_DEFAULT_EMAIL =
  import.meta.env.VITE_CONFIGCAT_DEFAULT_EMAIL?.trim() || 'beta-user@archon.local';
const CONFIGCAT_IDENTIFIER =
  import.meta.env.VITE_CONFIGCAT_IDENTIFIER?.trim() || 'archon-beta-instance';

const resolveConfigCatEmail = (): string => {
  if (typeof window === 'undefined') {
    return CONFIGCAT_DEFAULT_EMAIL;
  }

  const candidates = [
    window.localStorage?.getItem('archonUserEmail'),
    window.localStorage?.getItem('archon:userEmail'),
    window.sessionStorage?.getItem('archonUserEmail'),
    window.sessionStorage?.getItem('archon:userEmail'),
  ];

  const emailCandidate = candidates.find((value) => value && value.includes('@'));
  return (emailCandidate || CONFIGCAT_DEFAULT_EMAIL).trim();
};

const useConfigCatUser = (): void => {
  useEffect(() => {
    if (typeof window === 'undefined') {
      return;
    }

    const assignUser = (): boolean => {
      const globalWindow = window as typeof window & {
        configcatClient?: { setUser?: (user: { identifier: string; email?: string }) => void; getUser?: () => unknown };
      };

      const client = globalWindow.configcatClient;
      if (!client || typeof client.setUser !== 'function') {
        return false;
      }

      const email = resolveConfigCatEmail();

      try {
        client.setUser({
          identifier: CONFIGCAT_IDENTIFIER,
          email,
        });
      } catch (error) {
        console.warn('[Archon] Failed to set ConfigCat user', error);
        return false;
      }

      return true;
    };

    if (assignUser()) {
      return;
    }

    const maxAttempts = 12;
    let attempts = 0;
    const intervalId = window.setInterval(() => {
      attempts += 1;
      if (assignUser() || attempts >= maxAttempts) {
        window.clearInterval(intervalId);
      }
    }, 500);

    return () => window.clearInterval(intervalId);
  }, []);
};

// Create a client with optimized settings for our polling use case
const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      // Keep data fresh for 2 seconds by default
      staleTime: 2000,
      // Cache data for 5 minutes
      gcTime: 5 * 60 * 1000,
      // Retry failed requests 3 times
      retry: 3,
      // Refetch on window focus
      refetchOnWindowFocus: true,
      // Don't refetch on reconnect by default (we handle this manually)
      refetchOnReconnect: false,
    },
    mutations: {
      // Retry mutations once on failure
      retry: 1,
    },
  },
});

const AppRoutes = (): JSX.Element => {
  const { projectsEnabled } = useSettings();
  
  return (
    <Routes>
      <Route path="/" element={<KnowledgeBasePage />} />
      <Route path="/onboarding" element={<OnboardingPage />} />
      <Route path="/settings" element={<SettingsPage />} />
      <Route path="/mcp" element={<MCPPage />} />
      <Route path="/embeddings" element={<EmbeddingsPage />} />
      <Route path="/obsidian" element={<ObsidianSyncPage />} />
      <Route path="/tags" element={<TagsPage />} />
      <Route path="/eval" element={<EvalPage />} />
      {projectsEnabled ? (
        <>
          <Route path="/projects" element={<ProjectPage />} />
          <Route path="/projects/:projectId" element={<ProjectPage />} />
        </>
      ) : (
        <Route path="/projects" element={<Navigate to="/" replace />} />
      )}
    </Routes>
  );
};

const AppContent = (): JSX.Element => {
  const [disconnectScreenActive, setDisconnectScreenActive] = useState(false);
  const [disconnectScreenDismissed, setDisconnectScreenDismissed] = useState(false);
  const [disconnectScreenSettings, setDisconnectScreenSettings] = useState({
    enabled: true,
    delay: 10000
  });
  const [migrationBannerDismissed, setMigrationBannerDismissed] = useState(false);
  const migrationStatus = useMigrationStatus();

  useEffect(() => {
    // Load initial settings
    const settings = serverHealthService.getSettings();
    setDisconnectScreenSettings(settings);

    // Stop any existing monitoring before starting new one to prevent multiple intervals
    serverHealthService.stopMonitoring();

    // Start health monitoring
    serverHealthService.startMonitoring({
      onDisconnected: () => {
        if (!disconnectScreenDismissed) {
          setDisconnectScreenActive(true);
        }
      },
      onReconnected: () => {
        setDisconnectScreenActive(false);
        setDisconnectScreenDismissed(false);
        // Refresh the page to ensure all data is fresh
        window.location.reload();
      }
    });

    return () => {
      serverHealthService.stopMonitoring();
    };
  }, [disconnectScreenDismissed]);

  const handleDismissDisconnectScreen = (): void => {
    setDisconnectScreenActive(false);
    setDisconnectScreenDismissed(true);
  };

  return (
    <>
      <Router>
        <ErrorBoundaryWithBugReport>
          <MainLayout>
            {/* Migration Banner - shows when backend is up but DB schema needs work */}
            {migrationStatus.migrationRequired && !migrationBannerDismissed && (
              <MigrationBanner
                message={migrationStatus.message || "Database migration required"}
                onDismiss={() => setMigrationBannerDismissed(true)}
              />
            )}
            <Suspense fallback={<div className="p-4 text-sm text-zinc-500">Loading…</div>}>
              <AppRoutes />
            </Suspense>
          </MainLayout>
        </ErrorBoundaryWithBugReport>
      </Router>
      <DisconnectScreenOverlay
        isActive={disconnectScreenActive && disconnectScreenSettings.enabled}
        onDismiss={handleDismissDisconnectScreen}
      />
    </>
  );
};

export function App(): JSX.Element {
  useConfigCatUser();

  return (
    <QueryClientProvider client={queryClient}>
      <ThemeProvider>
        <ToastProvider>
          <FeaturesToastProvider>
            <TooltipProvider>
              <SettingsProvider>
                <AppContent />
              </SettingsProvider>
            </TooltipProvider>
          </FeaturesToastProvider>
        </ToastProvider>
      </ThemeProvider>
      {import.meta.env.VITE_SHOW_DEVTOOLS === 'true' && (
        <Suspense fallback={null}>
          <ReactQueryDevtoolsLazy initialIsOpen={false} />
        </Suspense>
      )}
    </QueryClientProvider>
  );
}
