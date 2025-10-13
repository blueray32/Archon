import { BookOpen, Settings, Database, BarChart2, FileText, Tags, Bot } from "lucide-react";
import type React from "react";
import { useEffect, useState } from "react";
import { Link, useLocation } from "react-router-dom";
// TEMPORARY: Use old SettingsContext until settings are migrated
import { useSettings } from "../../contexts/SettingsContext";
import { glassmorphism } from "../../features/ui/primitives/styles";
import { Tooltip, TooltipContent, TooltipTrigger } from "../../features/ui/primitives/tooltip";
import { cn } from "../../lib/utils";
import { NEXARCH_ENABLE_CHATKIT } from "../../config/flags";

interface NavigationItem {
  path: string;
  icon: React.ReactNode;
  label: string;
  enabled?: boolean;
}

interface NavigationProps {
  className?: string;
}

/**
 * Modern navigation component using Radix UI patterns
 * No fixed positioning - parent controls layout
 */
export function Navigation({ className }: NavigationProps) {
  const location = useLocation();
  const { projectsEnabled } = useSettings();
  const [missingEmbeddings, setMissingEmbeddings] = useState<number>(0);

  // Fetch embeddings health periodically to surface missing count as a badge
  useEffect(() => {
    let active = true;
    // Periodic refresh timer

    const fetchHealth = async () => {
      try {
        const res = await fetch("/api/embeddings/health", { signal: AbortSignal.timeout(2500) });
        if (!res.ok) return;
        const data = await res.json();
        if (!active) return;
        const missing = Number(data?.summary?.missing ?? 0);
        setMissingEmbeddings(Number.isFinite(missing) ? missing : 0);
      } catch {
        // ignore
      }
    };

    fetchHealth();
    // Refresh every 60s
    const timer = window.setInterval(fetchHealth, 60000);

    return () => {
      active = false;
      window.clearInterval(timer);
    };
  }, []);

  // Navigation items configuration
  const navigationItems: NavigationItem[] = [
    {
      path: "/",
      icon: <BookOpen className="h-5 w-5" />,
      label: "Knowledge Base",
      enabled: true,
    },
    {
      path: "/mcp",
      icon: (
        <svg
          fill="currentColor"
          fillRule="evenodd"
          height="20"
          width="20"
          viewBox="0 0 24 24"
          xmlns="http://www.w3.org/2000/svg"
          role="img"
          aria-label="MCP Server Icon"
        >
          <path d="M15.688 2.343a2.588 2.588 0 00-3.61 0l-9.626 9.44a.863.863 0 01-1.203 0 .823.823 0 010-1.18l9.626-9.44a4.313 4.313 0 016.016 0 4.116 4.116 0 011.204 3.54 4.3 4.3 0 013.609 1.18l.05.05a4.115 4.115 0 010 5.9l-8.706 8.537a.274.274 0 000 .393l1.788 1.754a.823.823 0 010 1.18.863.863 0 01-1.203 0l-1.788-1.753a1.92 1.92 0 010-2.754l8.706-8.538a2.47 2.47 0 000-3.54l-.05-.049a2.588 2.588 0 00-3.607-.003l-7.172 7.034-.002.002-.098.097a.863.863 0 01-1.204 0 .823.823 0 010-1.18l7.273-7.133a2.47 2.47 0 00-.003-3.537z" />
          <path d="M14.485 4.703a.823.823 0 000-1.18.863.863 0 00-1.204 0l-7.119 6.982a4.115 4.115 0 000 5.9 4.314 4.314 0 006.016 0l7.12-6.982a.823.823 0 000-1.18.863.863 0 00-1.204 0l-7.119 6.982a2.588 2.588 0 01-3.61 0 2.47 2.47 0 010-3.54l7.12-6.982z" />
        </svg>
      ),
      label: "MCP Server",
      enabled: true,
    },
    {
      path: "/embeddings",
      icon: <Database className="h-5 w-5" />,
      label: "Embeddings",
      enabled: true,
    },
    {
      path: "/obsidian",
      icon: <FileText className="h-5 w-5" />,
      label: "Obsidian",
      enabled: true,
    },
    {
      path: "/tags",
      icon: <Tags className="h-5 w-5" />,
      label: "Tags",
      enabled: true,
    },
    {
      path: "/eval",
      icon: <BarChart2 className="h-5 w-5" />,
      label: "Eval",
      enabled: true,
    },
    {
      path: "/settings",
      icon: <Settings className="h-5 w-5" />,
      label: "Settings",
      enabled: true,
    },
  ];

  if (NEXARCH_ENABLE_CHATKIT) {
    navigationItems.splice(1, 0, {
      path: "/assistant",
      icon: <Bot className="h-5 w-5" />,
      label: "Assistant (Beta)",
      enabled: true,
    });
  }

  const isProjectsActive = location.pathname.startsWith("/projects");

  return (
    <nav
      className={cn(
        "flex flex-col items-center gap-6 py-6 px-3",
        "rounded-2xl w-[72px]",
        // Nexarch glassmorphism
        "nexarch-glass",
        "shadow-[0_10px_30px_-15px_rgba(0,212,255,0.3)] dark:shadow-[0_10px_30px_-15px_rgba(0,212,255,0.5)]",
        className,
      )}
    >
      {/* Logo - Always visible, conditionally clickable for Projects */}
      <Tooltip>
        <TooltipTrigger asChild>
          {projectsEnabled ? (
            <Link
              to="/projects"
              className={cn(
                "relative p-2 rounded-xl transition-all duration-300",
                "flex items-center justify-center",
                "border border-transparent",
                "hover:bg-gradient-to-br hover:from-cyan-500/10 hover:to-purple-500/10",
                "hover:border-cyan-400/20",
                isProjectsActive && [
                  "bg-gradient-to-br from-cyan-500/20 to-purple-500/20",
                  "border-cyan-400/40",
                  "shadow-[0_0_15px_rgba(0,212,255,0.4),0_0_30px_rgba(255,0,255,0.2)]",
                  "transform scale-110",
                ],
              )}
            >
              <img
                src="/logo-neon.svg"
                alt="Nexarch"
                className={cn(
                  "w-8 h-8 transition-all duration-300",
                  isProjectsActive && "filter drop-shadow-[0_0_12px_rgba(0,212,255,0.8)]",
                )}
              />
              {/* Hexagonal corner accents */}
              {isProjectsActive && (
                <>
                  <div className="absolute top-1 left-1 w-2 h-2 hexagon-sm bg-cyan-400/50" />
                  <div className="absolute top-1 right-1 w-2 h-2 hexagon-sm bg-purple-400/50" />
                  <div className="absolute bottom-1 left-1 w-2 h-2 hexagon-sm bg-pink-400/50" />
                  <div className="absolute bottom-1 right-1 w-2 h-2 hexagon-sm bg-cyan-400/50" />
                  <span className="absolute bottom-0 left-[15%] right-[15%] w-[70%] mx-auto h-[3px] bg-gradient-to-r from-cyan-400 via-purple-400 to-pink-400 shadow-[0_0_15px_rgba(0,212,255,0.8)]" />
                </>
              )}
            </Link>
          ) : (
            <div className="p-2 rounded-xl opacity-50 cursor-not-allowed border border-gray-300/20">
              <img src="/logo-neon.svg" alt="Nexarch" className="w-8 h-8 grayscale" />
            </div>
          )}
        </TooltipTrigger>
        <TooltipContent>
          <p>{projectsEnabled ? "Project Management" : "Projects Disabled"}</p>
        </TooltipContent>
      </Tooltip>

      {/* Separator */}
      <div className="w-8 h-px bg-gradient-to-r from-transparent via-cyan-400/40 to-transparent" />

      {/* Navigation Items */}
      <nav className="flex flex-col gap-4">
        {navigationItems.map((item) => {
          const isActive = location.pathname === item.path;
          const isEnabled = item.enabled !== false;

          return (
            <Tooltip key={item.path}>
              <TooltipTrigger asChild>
                <Link
                  to={isEnabled ? item.path : "#"}
                  className={cn(
                    "relative p-3 rounded-xl transition-all duration-300",
                    "flex items-center justify-center",
                    "border border-transparent",
                    isActive
                      ? [
                          "bg-gradient-to-br from-cyan-500/20 to-purple-500/20",
                          "text-cyan-400 dark:text-cyan-300",
                          "border-cyan-400/40",
                          "shadow-[0_0_15px_rgba(0,212,255,0.4),0_0_30px_rgba(255,0,255,0.2)]",
                        ]
                      : [
                          "text-gray-500 dark:text-zinc-500",
                          "hover:text-cyan-400 dark:hover:text-cyan-300",
                          "hover:bg-gradient-to-br hover:from-cyan-500/10 hover:to-purple-500/10",
                          "hover:border-cyan-400/20",
                        ],
                    !isEnabled && "opacity-50 cursor-not-allowed pointer-events-none",
                  )}
                  onClick={(e) => {
                    if (!isEnabled) {
                      e.preventDefault();
                    }
                  }}
                >
                  {/* Hexagonal corner accents */}
                  {isActive && (
                    <>
                      <div className="absolute top-1 left-1 w-2 h-2 hexagon-sm bg-cyan-400/50" />
                      <div className="absolute top-1 right-1 w-2 h-2 hexagon-sm bg-purple-400/50" />
                      <div className="absolute bottom-1 left-1 w-2 h-2 hexagon-sm bg-pink-400/50" />
                      <div className="absolute bottom-1 right-1 w-2 h-2 hexagon-sm bg-cyan-400/50" />
                    </>
                  )}

                  <div className="relative">
                    {item.icon}
                    {item.path === "/embeddings" && missingEmbeddings > 0 && (
                      <span
                        title={`${missingEmbeddings} missing embeddings (auto-refreshes every 60s)`}
                        className="absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 rounded-full text-[10px] leading-[18px] text-white bg-gradient-to-br from-cyan-500 to-purple-500 text-center shadow-[0_0_10px_rgba(0,212,255,0.6)]"
                      >
                        {missingEmbeddings > 99 ? "99+" : missingEmbeddings}
                      </span>
                    )}
                  </div>
                  {/* Active state decorations with hexagonal glow */}
                  {isActive && (
                    <span className="absolute bottom-0 left-[15%] right-[15%] w-[70%] mx-auto h-[3px] bg-gradient-to-r from-cyan-400 via-purple-400 to-pink-400 shadow-[0_0_15px_rgba(0,212,255,0.8)]" />
                  )}
                </Link>
              </TooltipTrigger>
              <TooltipContent>
                <p>{item.label}</p>
              </TooltipContent>
            </Tooltip>
          );
        })}
      </nav>
    </nav>
  );
}
