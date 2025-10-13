import { AlertCircle, WifiOff } from "lucide-react";
import type React from "react";
import { useEffect, useState, useCallback } from "react";
import { useLocation, useNavigate } from "react-router-dom";
import { useToast } from "../../features/ui/hooks/useToast";
import { cn } from "../../lib/utils";
import { credentialsService } from "../../services/credentialsService";
import { isLmConfigured } from "../../utils/onboarding";
import { VoiceEnabledChatPanel } from "../agent-chat/VoiceEnabledChatPanel";
// TEMPORARY: Import from old components until they're migrated to features
import { BackendStartupError } from "../BackendStartupError";
import { useBackendHealth } from "./hooks/useBackendHealth";
import { Navigation } from "./Navigation";
import { NeuralBackground } from "./NeuralBackground";
import { useAgentState } from "../../agents/AgentContext";

interface MainLayoutProps {
  children: React.ReactNode;
  className?: string;
}

interface BackendStatusProps {
  isHealthLoading: boolean;
  isBackendError: boolean;
  healthData: { ready: boolean } | undefined;
}

/**
 * Backend health indicator component
 */
function BackendStatus({ isHealthLoading, isBackendError, healthData }: BackendStatusProps) {
  if (isHealthLoading) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl nexarch-glass border border-yellow-400/30 text-yellow-300 dark:text-yellow-400 text-sm shadow-[0_0_15px_rgba(234,179,8,0.2)]">
        <div className="w-2 h-2 bg-yellow-400 rounded-full animate-pulse shadow-[0_0_8px_rgba(234,179,8,0.6)]" />
        <span className="font-medium">Connecting...</span>
      </div>
    );
  }

  if (isBackendError) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl nexarch-glass border border-red-400/30 text-red-300 dark:text-red-400 text-sm shadow-[0_0_15px_rgba(239,68,68,0.2)]">
        <WifiOff className="w-4 h-4" />
        <span className="font-medium">Backend Offline</span>
      </div>
    );
  }

  if (healthData?.ready === false) {
    return (
      <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl nexarch-glass border border-yellow-400/30 text-yellow-300 dark:text-yellow-400 text-sm shadow-[0_0_15px_rgba(234,179,8,0.2)]">
        <AlertCircle className="w-4 h-4" />
        <span className="font-medium">Backend Starting...</span>
      </div>
    );
  }

  return null;
}

/**
 * Modern main layout using TanStack Query and Radix UI patterns
 * Uses CSS Grid for layout instead of fixed positioning
 */
export function MainLayout({ children, className }: MainLayoutProps) {
  const { selectedAgent } = useAgentState();
  const navigate = useNavigate();
  const location = useLocation();
  const { showToast } = useToast();
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [agentsOnline, setAgentsOnline] = useState<null | boolean>(null);

  // Backend health monitoring with TanStack Query
  const {
    data: healthData,
    isError: isBackendError,
    error: backendError,
    isLoading: isHealthLoading,
    failureCount,
  } = useBackendHealth();

  // Track if backend has completely failed (for showing BackendStartupError)
  const backendStartupFailed = isBackendError && failureCount >= 5;

  // TEMPORARY: Handle onboarding redirect using old logic until migrated
  useEffect(() => {
    const checkOnboarding = async () => {
      // Skip if backend failed to start
      if (backendStartupFailed) {
        return;
      }

      // Skip if not ready, already on onboarding, or already dismissed
      if (!healthData?.ready || location.pathname === "/onboarding") {
        return;
      }

      // Check if onboarding was already dismissed
      if (localStorage.getItem("onboardingDismissed") === "true") {
        return;
      }

      try {
        // Fetch credentials in parallel (using old service temporarily)
        const [ragCreds, apiKeyCreds] = await Promise.all([
          credentialsService.getCredentialsByCategory("rag_strategy"),
          credentialsService.getCredentialsByCategory("api_keys"),
        ]);

        // Check if LM is configured (using old utility temporarily)
        const configured = isLmConfigured(ragCreds, apiKeyCreds);

        if (!configured) {
          // Redirect to onboarding
          navigate("/onboarding", { replace: true });
        }
      } catch (error) {
        // Log error but don't block app
        console.error("ONBOARDING_CHECK_FAILED:", error);
        showToast(`Configuration check failed. You can manually configure in Settings.`, "warning");
      }
    };

    checkOnboarding();
  }, [healthData?.ready, backendStartupFailed, location.pathname, navigate, showToast]);

  // Show backend error toast (once)
  useEffect(() => {
    if (isBackendError && backendError) {
      const errorMessage = backendError instanceof Error ? backendError.message : "Backend connection failed";
      showToast(`Backend unavailable: ${errorMessage}. Some features may not work.`, "error");
    }
  }, [isBackendError, backendError, showToast]);

  // Lightweight Agents service health polling for a simple header pill
  const pollAgentsStatus = useCallback(async () => {
    try {
      const res = await fetch('/api/agent-chat/status', { method: 'GET' });
      if (!res.ok) {
        setAgentsOnline(false);
        return;
      }
      const data = await res.json();
      setAgentsOnline(Boolean(data?.online));
    } catch {
      setAgentsOnline(false);
    }
  }, []);

  useEffect(() => {
    let timer: number | null = null;
    pollAgentsStatus();
    timer = window.setInterval(pollAgentsStatus, 20000);
    return () => {
      if (timer) window.clearInterval(timer);
    };
  }, [pollAgentsStatus]);

  return (
    <div className={cn("relative min-h-screen bg-white dark:bg-black overflow-hidden", className)}>
      {/* TEMPORARY: Show backend startup error using old component */}
      {backendStartupFailed && <BackendStartupError />}

      {/* Fixed full-page background grid that doesn't scroll */}
      <div className="fixed inset-0 neon-grid pointer-events-none z-0" />

      {/* Animated Neural Network Background */}
      <NeuralBackground />

      {/* Floating Navigation */}
      <div className="fixed left-6 top-1/2 -translate-y-1/2 z-50 flex flex-col gap-4">
        <Navigation />
        <BackendStatus isHealthLoading={isHealthLoading} isBackendError={isBackendError} healthData={healthData} />
        {agentsOnline === null ? (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl nexarch-glass border border-gray-400/30 text-gray-400 dark:text-gray-300 text-sm">
            <div className="w-2 h-2 bg-gray-400 rounded-full animate-pulse shadow-[0_0_8px_rgba(156,163,175,0.6)]" />
            <span className="font-medium">Agents Checking…</span>
          </div>
        ) : agentsOnline ? (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl nexarch-glass border border-cyan-400/40 text-cyan-300 dark:text-cyan-400 text-sm shadow-[0_0_15px_rgba(0,212,255,0.3)]">
            <div className="w-2 h-2 bg-cyan-400 rounded-full shadow-[0_0_10px_rgba(0,212,255,0.8)]" />
            <span className="font-medium">Agents Online</span>
          </div>
        ) : (
          <div className="flex items-center gap-2 px-3 py-1.5 rounded-xl nexarch-glass border border-red-400/30 text-red-300 dark:text-red-400 text-sm shadow-[0_0_15px_rgba(239,68,68,0.2)]">
            <div className="w-2 h-2 bg-red-400 rounded-full shadow-[0_0_8px_rgba(239,68,68,0.6)]" />
            <span className="font-medium">Agents Offline</span>
          </div>
        )}
      </div>

      {/* Main Content Area - matches old layout exactly */}
      <div className="relative flex-1 pl-[100px] z-10">
        <div className="container mx-auto px-8 relative">
          <div className="min-h-screen pt-8 pb-16">{children}</div>
        </div>
      </div>

      {/* Floating Chat Button (hidden when chat open) */}
      {!isChatOpen && (
        <div className="fixed bottom-6 right-6 z-50 group">
          <button
            type="button"
            onClick={() => setIsChatOpen(true)}
            className="relative w-16 h-16 flex items-center justify-center backdrop-blur-md bg-gradient-to-br from-cyan-500/20 to-purple-500/20 dark:from-cyan-500/30 dark:to-purple-500/30 shadow-[0_0_20px_rgba(0,212,255,0.5),0_0_40px_rgba(255,0,255,0.3)] hover:shadow-[0_0_30px_rgba(0,212,255,0.8),0_0_60px_rgba(255,0,255,0.5)] transition-all duration-300 overflow-hidden border-2 border-cyan-400/50 hover:border-cyan-300 animate-glow-cyan"
            style={{
              clipPath: "polygon(30% 0%, 70% 0%, 100% 50%, 70% 100%, 30% 100%, 0% 50%)",
            }}
            aria-label={`Open ${selectedAgent?.label || 'Agent'} Chat`}
          >
            {/* Hexagonal corner accents */}
            <div className="absolute top-1 left-1 w-2 h-2 hexagon-sm bg-cyan-400/60" />
            <div className="absolute top-1 right-1 w-2 h-2 hexagon-sm bg-purple-400/60" />
            <div className="absolute bottom-1 left-1 w-2 h-2 hexagon-sm bg-pink-400/60" />
            <div className="absolute bottom-1 right-1 w-2 h-2 hexagon-sm bg-cyan-400/60" />

            <img
              src="/logo-neon.svg"
              alt="Nexarch"
              className="w-8 h-8 relative z-10"
            />
          </button>
          {/* Tooltip */}
          <div className="absolute bottom-full right-0 mb-3 px-4 py-2 nexarch-glass rounded-xl shadow-[0_0_20px_rgba(0,212,255,0.3)] opacity-0 group-hover:opacity-100 transition-opacity duration-200 pointer-events-none whitespace-nowrap">
            <div className="font-medium text-cyan-300">{selectedAgent?.label || 'Agent Chat'}</div>
            <div className="text-xs text-gray-400">{selectedAgent?.description || 'Chat with your selected agent'}</div>
          </div>
        </div>
      )}

      {/* Chat Panel */}
      {isChatOpen && (
        <div className="fixed inset-y-0 right-0 z-50 max-w-[500px] w-full">
          <VoiceEnabledChatPanel onClose={() => setIsChatOpen(false)} />
        </div>
      )}
    </div>
  );
}

/**
 * Layout variant without navigation for special pages
 */
export function MinimalLayout({ children, className }: MainLayoutProps) {
  return (
    <div className={cn("min-h-screen bg-white dark:bg-black overflow-hidden", "flex items-center justify-center", className)}>
      {/* Nexarch Hexagonal Grid Background */}
      <div className="fixed inset-0 neon-grid pointer-events-none z-0" />

      {/* Animated Neural Network Background */}
      <NeuralBackground />

      {/* Centered Content */}
      <div className="relative w-full max-w-4xl px-6 z-10">{children}</div>
    </div>
  );
}
