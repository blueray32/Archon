import { useState, useEffect, lazy, Suspense, useCallback } from "react";
import {
  Loader,
  Settings,
  ChevronDown,
  Palette,
  Key,
  Brain,
  Code,
  FileCode,
  Bug,
} from "lucide-react";
import { motion, AnimatePresence } from "framer-motion";
import { useToast } from "../contexts/ToastContext";
import { useSettings } from "../contexts/SettingsContext";
import { useStaggeredEntrance } from "../hooks/useStaggeredEntrance";
const FeaturesSection = lazy(() =>
  import("../components/settings/FeaturesSection").then((m) => ({ default: m.FeaturesSection })),
);
const APIKeysSection = lazy(() =>
  import("../components/settings/APIKeysSection").then((m) => ({ default: m.APIKeysSection })),
);
const RAGSettings = lazy(() =>
  import("../components/settings/RAGSettings").then((m) => ({ default: m.RAGSettings })),
);
const CodeExtractionSettings = lazy(() =>
  import("../components/settings/CodeExtractionSettings").then((m) => ({ default: m.CodeExtractionSettings })),
);
const IDEGlobalRules = lazy(() =>
  import("../components/settings/IDEGlobalRules").then((m) => ({ default: m.IDEGlobalRules })),
);
const ButtonPlayground = lazy(() =>
  import("../components/settings/ButtonPlayground").then((m) => ({ default: m.ButtonPlayground })),
);
import { CollapsibleSettingsCard } from "../components/ui/CollapsibleSettingsCard";
const BugReportButton = lazy(() =>
  import("../components/bug-report/BugReportButton").then((m) => ({ default: m.BugReportButton })),
);
import {
  credentialsService,
  RagSettings,
  CodeExtractionSettings as CodeExtractionSettingsType,
} from "../services/credentialsService";
import { knowledgeBaseService } from "../services/knowledgeBaseService";

export const SettingsPage = () => {
  const [ragSettings, setRagSettings] = useState<RagSettings>({
    USE_CONTEXTUAL_EMBEDDINGS: false,
    CONTEXTUAL_EMBEDDINGS_MAX_WORKERS: 3,
    USE_HYBRID_SEARCH: true,
    USE_AGENTIC_RAG: true,
    USE_RERANKING: true,
    MODEL_CHOICE: "gpt-4.1-nano",
  });
  const [codeExtractionSettings, setCodeExtractionSettings] =
    useState<CodeExtractionSettingsType>({
      MIN_CODE_BLOCK_LENGTH: 250,
      MAX_CODE_BLOCK_LENGTH: 5000,
      ENABLE_COMPLETE_BLOCK_DETECTION: true,
      ENABLE_LANGUAGE_SPECIFIC_PATTERNS: true,
      ENABLE_PROSE_FILTERING: true,
      MAX_PROSE_RATIO: 0.15,
      MIN_CODE_INDICATORS: 3,
      ENABLE_DIAGRAM_FILTERING: true,
      ENABLE_CONTEXTUAL_LENGTH: true,
      CODE_EXTRACTION_MAX_WORKERS: 3,
      CONTEXT_WINDOW_SIZE: 1000,
      ENABLE_CODE_SUMMARIES: true,
    });
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [showButtonPlayground, setShowButtonPlayground] = useState(false);
  const [exportPath, setExportPath] = useState<string>(() => {
    try {
      return localStorage.getItem('archonExportVaultPath') || "";
    } catch {
      return "";
    }
  });
  const [exportSourceIds, setExportSourceIds] = useState<string>("");
  const [exportTags, setExportTags] = useState<string>("");
  const [exportKnowledgeType, setExportKnowledgeType] = useState<string>("");
  const [exportUpdatedSince, setExportUpdatedSince] = useState<string>("");
  const [exportProgressId, setExportProgressId] = useState<string | null>(null);
  const [exportProgress, setExportProgress] = useState<number>(0);
  const [exportStatus, setExportStatus] = useState<string>("");
  const [exportError, setExportError] = useState<string | null>(null);
  const [serverDefaultExport, setServerDefaultExport] = useState<{ defaultTarget?: string; exists?: boolean; isDir?: boolean } | null>(null);

  const { showToast } = useToast();
  const { projectsEnabled } = useSettings();

  // Use staggered entrance animation
  const { isVisible, containerVariants, itemVariants, titleVariants } =
    useStaggeredEntrance([1, 2, 3, 4], 0.15);

  const loadSettings = useCallback(async (): Promise<void> => {
    try {
      setLoading(true);
      setError(null);

      // Load RAG settings
      const ragSettingsData = await credentialsService.getRagSettings();
      setRagSettings(ragSettingsData);

      // Load Code Extraction settings
      const codeExtractionSettingsData =
        await credentialsService.getCodeExtractionSettings();
      setCodeExtractionSettings(codeExtractionSettingsData);
    } catch (err) {
      setError("Failed to load settings");
      console.error(err);
      showToast("Failed to load settings", "error");
    } finally {
      setLoading(false);
    }
  }, [showToast]);

  // Load settings on mount
  useEffect((): void => {
    loadSettings();
  }, [loadSettings]);

  // Load server default export target for hinting
  useEffect(() => {
    (async () => {
      try {
        const info = await knowledgeBaseService.getExportDefaultTarget();
        setServerDefaultExport(info);
      } catch {
        // optional hint; ignore errors
      }
    })();
  }, []);

  const refreshAgents = async (): Promise<void> => {
    try {
      const res = await fetch('/api/agents/refresh', { method: 'POST' });
      if (!res.ok) {
        let msg = `HTTP ${res.status}`;
        try { const data = await res.json(); msg = data?.error || msg; }
        catch (e) { console.warn('Failed to parse agents refresh response JSON', e); }
        throw new Error(msg);
      }
      showToast('Agents credentials refreshed', 'success');
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      showToast(`Failed to refresh agents: ${msg}`, 'error');
    }
  };

  const handleExport = async (): Promise<void> => {
    try {
      // Build options
      const sourceIds = exportSourceIds
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
      const tags = exportTags
        .split(',')
        .map((s) => s.trim())
        .filter(Boolean);
      let updatedSinceISO: string | undefined = undefined;
      if (exportUpdatedSince) {
        // Convert date input (YYYY-MM-DD) to ISO string at midnight
        const d = new Date(exportUpdatedSince);
        if (!isNaN(d.getTime())) updatedSinceISO = d.toISOString();
      }

      const res = await knowledgeBaseService.exportToVault({
        targetPath: exportPath || undefined,
        sourceIds: sourceIds.length ? sourceIds : undefined,
        tags: tags.length ? tags : undefined,
        knowledgeType: (exportKnowledgeType === 'technical' || exportKnowledgeType === 'business') ? exportKnowledgeType : undefined,
        updatedSince: updatedSinceISO,
      });
      setExportProgressId(res.progressId);
      setExportProgress(0);
      setExportStatus("starting");
      setExportError(null);
      showToast(`Export started (progressId: ${res.progressId})`, "success");
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : String(e);
      showToast(`Failed to start export: ${msg}`, "error");
    }
  };

  // Poll export progress
  useEffect(() => {
    if (!exportProgressId) return;
    let cancelled = false;
    const handle = setInterval(async () => {
      try {
        const data = await knowledgeBaseService.getProgress(exportProgressId);
        if (cancelled) return;
        setExportProgress(typeof data.progress === 'number' ? data.progress : 0);
        setExportStatus(data.status || '');
        if (data.error) setExportError(data.error);
        // Stop polling when terminal state reached
        if (data.status === 'completed' || data.status === 'failed' || data.status === 'error' || (typeof data.progress === 'number' && data.progress >= 100)) {
          clearInterval(handle);
        }
      } catch (e) {
        if (cancelled) return;
        // On error, stop polling and surface error once
        clearInterval(handle);
        setExportError(e instanceof Error ? e.message : String(e));
      }
    }, 1000);
    return () => { cancelled = true; clearInterval(handle); };
  }, [exportProgressId]);

  if (loading) {
    return (
      <div className="flex items-center justify-center min-h-[400px]">
        <Loader className="animate-spin text-gray-500" size={32} />
      </div>
    );
  }

  return (
    <motion.div
      initial="hidden"
      animate={isVisible ? "visible" : "hidden"}
      variants={containerVariants}
      className="w-full"
    >
      {/* Header */}
      <motion.div
        className="flex justify-between items-center mb-8"
        variants={itemVariants}
      >
        <motion.h1
          className="text-3xl font-bold text-gray-800 dark:text-white flex items-center gap-3"
          variants={titleVariants}
        >
          <Settings className="w-7 h-7 text-blue-500 filter drop-shadow-[0_0_8px_rgba(59,130,246,0.8)]" />
          Settings
        </motion.h1>
      </motion.div>


      {/* Main content with two-column layout */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
        {/* Left Column */}
        <div className="space-y-6">
          <motion.div variants={itemVariants}>
            <CollapsibleSettingsCard
              title="Features"
              icon={Palette}
              accentColor="purple"
              storageKey="features"
              defaultExpanded={true}
            >
              <Suspense fallback={<div className="p-2 text-sm text-zinc-500">Loading…</div>}>
                <FeaturesSection />
              </Suspense>
            </CollapsibleSettingsCard>
          </motion.div>
          {projectsEnabled && (
            <motion.div variants={itemVariants}>
              <CollapsibleSettingsCard
                title="IDE Global Rules"
                icon={FileCode}
                accentColor="pink"
                storageKey="ide-rules"
                defaultExpanded={true}
              >
                <Suspense fallback={<div className="p-2 text-sm text-zinc-500">Loading…</div>}>
                  <IDEGlobalRules />
                </Suspense>
              </CollapsibleSettingsCard>
            </motion.div>
          )}
        </div>

        {/* Right Column */}
        <div className="space-y-6">
          <motion.div variants={itemVariants}>
            <CollapsibleSettingsCard
              title="API Keys"
              icon={Key}
              accentColor="pink"
              storageKey="api-keys"
              defaultExpanded={true}
            >
              <Suspense fallback={<div className="p-2 text-sm text-zinc-500">Loading…</div>}>
                <APIKeysSection />
              </Suspense>
              <div className="mt-4 flex items-center gap-2">
                <button
                  className="px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100/50 dark:hover:bg-zinc-800/30 text-sm"
                  onClick={refreshAgents}
                  title="Refresh agents credentials without restart"
                >
                  Refresh Agents Credentials
                </button>
                <span className="text-xs text-zinc-500">Use after updating API keys to apply changes immediately.</span>
              </div>
            </CollapsibleSettingsCard>
          </motion.div>
          <motion.div variants={itemVariants}>
            <CollapsibleSettingsCard
              title="RAG Settings"
              icon={Brain}
              accentColor="green"
              storageKey="rag-settings"
              defaultExpanded={true}
            >
              <Suspense fallback={<div className="p-2 text-sm text-zinc-500">Loading…</div>}>
                <RAGSettings
                  ragSettings={ragSettings}
                  setRagSettings={setRagSettings}
                />
              </Suspense>
            </CollapsibleSettingsCard>
          </motion.div>
          <motion.div variants={itemVariants}>
            <CollapsibleSettingsCard
              title="Code Extraction"
              icon={Code}
              accentColor="orange"
              storageKey="code-extraction"
              defaultExpanded={true}
            >
              <Suspense fallback={<div className="p-2 text-sm text-zinc-500">Loading…</div>}>
                <CodeExtractionSettings
                  codeExtractionSettings={codeExtractionSettings}
                  setCodeExtractionSettings={setCodeExtractionSettings}
                />
              </Suspense>
            </CollapsibleSettingsCard>
          </motion.div>

          {/* Knowledge Export */}
          <motion.div variants={itemVariants}>
            <CollapsibleSettingsCard
              title="Knowledge Export"
              icon={FileCode}
              accentColor="blue"
              storageKey="knowledge-export"
              defaultExpanded={true}
            >
              <div className="space-y-3">
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Export the knowledge base to your local Obsidian vault.
                  Leave the path empty to use the server's OBSIDIAN_VAULT.
                </p>
                <div className="flex items-center gap-2">
                  <input
                    type="text"
                    placeholder={serverDefaultExport?.defaultTarget ? `Optional path (server default: ${serverDefaultExport.defaultTarget})` : "Optional target path (overrides server default)"}
                    value={exportPath}
                    onChange={(e) => {
                      const v = e.target.value;
                      setExportPath(v);
                      try { localStorage.setItem('archonExportVaultPath', v); } catch { /* ignore */ }
                    }}
                    className="flex-1 px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white/70 dark:bg-zinc-900/40 focus:outline-none text-sm"
                  />
                  <button
                    onClick={handleExport}
                    className="px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100/50 dark:hover:bg-zinc-800/30 text-sm"
                  >
                    Export Now
                  </button>
                </div>
                {serverDefaultExport && (
                  <div className="text-[11px] mt-1">
                    {serverDefaultExport.defaultTarget ? (
                      serverDefaultExport.isDir ? (
                        <span className="text-zinc-500">Server default path detected: <code>{serverDefaultExport.defaultTarget}</code></span>
                      ) : (
                        <span className="text-red-500">Server default path invalid: <code>{serverDefaultExport.defaultTarget}</code> (not a directory)</span>
                      )
                    ) : (
                      <span className="text-red-500">No server default export path set (OBSIDIAN_VAULT not configured). Specify a path above.</span>
                    )}
                  </div>
                )}
                <div className="grid grid-cols-1 md:grid-cols-2 gap-2">
                  <input
                    type="text"
                    placeholder="Source IDs (comma-separated)"
                    value={exportSourceIds}
                    onChange={(e) => setExportSourceIds(e.target.value)}
                    className="px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white/70 dark:bg-zinc-900/40 focus:outline-none text-sm"
                  />
                  <input
                    type="text"
                    placeholder="Tags (comma-separated)"
                    value={exportTags}
                    onChange={(e) => setExportTags(e.target.value)}
                    className="px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white/70 dark:bg-zinc-900/40 focus:outline-none text-sm"
                  />
                  <select
                    value={exportKnowledgeType}
                    onChange={(e) => setExportKnowledgeType(e.target.value)}
                    className="px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white/70 dark:bg-zinc-900/40 focus:outline-none text-sm"
                  >
                    <option value="">Knowledge Type (any)</option>
                    <option value="technical">technical</option>
                    <option value="business">business</option>
                  </select>
                  <input
                    type="date"
                    value={exportUpdatedSince}
                    onChange={(e) => setExportUpdatedSince(e.target.value)}
                    className="px-3 py-2 rounded-lg border border-zinc-300 dark:border-zinc-700 bg-white/70 dark:bg-zinc-900/40 focus:outline-none text-sm"
                  />
                </div>
                {exportProgressId && (
                  <div className="space-y-2">
                    <div className="text-xs text-zinc-500">
                      Progress ID: <code>{exportProgressId}</code>
                    </div>
                    <div className="w-full h-2 rounded-full bg-zinc-200 dark:bg-zinc-800 overflow-hidden">
                      <div
                        className="h-2 bg-blue-500"
                        style={{ width: `${Math.min(100, Math.max(0, exportProgress))}%` }}
                      />
                    </div>
                    <div className="text-xs text-zinc-600 dark:text-zinc-400">
                      Status: {exportStatus || 'waiting'} • {Math.round(exportProgress)}%
                    </div>
                    <div className="flex items-center gap-2">
                      <button
                        onClick={async () => {
                          if (!exportProgressId) return;
                          try {
                            await knowledgeBaseService.stopOperation(exportProgressId);
                            showToast('Export cancelled', 'success');
                          } catch (e) {
                            showToast('Failed to cancel export', 'error');
                          }
                        }}
                        className="px-2 py-1 rounded-md border border-zinc-300 dark:border-zinc-700 hover:bg-zinc-100/50 dark:hover:bg-zinc-800/30 text-xs"
                      >
                        Cancel Export
                      </button>
                    </div>
                    {exportError && (
                      <div className="text-xs text-red-500">Error: {exportError}</div>
                    )}
                  </div>
                )}
              </div>
            </CollapsibleSettingsCard>
          </motion.div>

          {/* Bug Report Section */}
          <motion.div variants={itemVariants}>
            <CollapsibleSettingsCard
              title="Bug Reporting"
              icon={Bug}
              iconColor="text-red-500"
              borderColor="border-red-200 dark:border-red-800"
              defaultExpanded={false}
            >
              <div className="space-y-4">
                <p className="text-sm text-gray-600 dark:text-gray-400">
                  Found a bug or issue? Report it to help improve Nexarch Beta.
                </p>
                <div className="flex justify-start">
                  <Suspense fallback={<div className="text-sm text-zinc-500">Loading…</div>}>
                    <BugReportButton variant="secondary" size="md">
                      Report Bug
                    </BugReportButton>
                  </Suspense>
                </div>
                <div className="text-xs text-gray-500 dark:text-gray-400 space-y-1">
                  <p>• Bug reports are sent directly to GitHub Issues</p>
                  <p>• System context is automatically collected</p>
                  <p>• Your privacy is protected - no personal data is sent</p>
                </div>
              </div>
            </CollapsibleSettingsCard>
          </motion.div>
        </div>
      </div>

      {/* Button Playground Toggle - Subtle blue circle */}
      <motion.div variants={itemVariants} className="mt-12 flex justify-center">
        <button
          onClick={() => setShowButtonPlayground(!showButtonPlayground)}
          className="relative w-8 h-8 rounded-full border border-blue-400/30 bg-blue-500/5 hover:bg-blue-500/10 transition-all duration-200 flex items-center justify-center group"
          title="Toggle Button Playground"
        >
          <div className="absolute inset-0 rounded-full bg-blue-500/20 blur-sm opacity-0 group-hover:opacity-100 transition-opacity" />
          <motion.div
            animate={{ rotate: showButtonPlayground ? 180 : 0 }}
            transition={{ duration: 0.2 }}
          >
            <ChevronDown className="w-4 h-4 text-blue-400/50" />
          </motion.div>
        </button>
      </motion.div>

      {/* Button Playground - Collapsible */}
      <AnimatePresence>
        {showButtonPlayground && (
          <motion.div
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: "auto" }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.3 }}
            className="overflow-hidden"
          >
            <motion.div variants={itemVariants} className="mt-4">
              <Suspense fallback={<div className="p-2 text-sm text-zinc-500">Loading…</div>}>
                <ButtonPlayground />
              </Suspense>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>

      {/* Error Display */}
      {error && (
        <motion.div
          variants={itemVariants}
          className="mt-6 p-4 bg-red-50 dark:bg-red-900/20 border border-red-200 dark:border-red-800 rounded-lg"
        >
          <p className="text-red-600 dark:text-red-400">{error}</p>
        </motion.div>
      )}
    </motion.div>
  );
};
