import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { BookOpen, RefreshCw, Play, Square, Database, FileText, Clock, CheckCircle2, XCircle } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { useToast } from '../contexts/ToastContext';
import { API_BASE_URL } from '../config/api';

interface VaultStatus {
  configured: boolean;
  vault_path: string | null;
  exists: boolean;
  watching: boolean;
  synced_files: number;
}

interface VaultInfo {
  vault_path: string;
  total_markdown_files: number;
  total_size_mb: number;
  exists: boolean;
}

interface IndexStats {
  total: number;
  success: number;
  failed: number;
}

export const ObsidianSyncPage = () => {
  const [vaultStatus, setVaultStatus] = useState<VaultStatus | null>(null);
  const [vaultInfo, setVaultInfo] = useState<VaultInfo | null>(null);
  const [isIndexing, setIsIndexing] = useState(false);
  const [indexStats, setIndexStats] = useState<IndexStats | null>(null);
  const [loading, setLoading] = useState(true);
  const { showToast } = useToast();

  // Load vault status and info
  const loadVaultData = async () => {
    try {
      setLoading(true);

      // Get status
      const statusRes = await fetch(`${API_BASE_URL}/obsidian/status`);
      const status = await statusRes.json();
      setVaultStatus(status);

      // Get info if vault exists
      if (status.exists) {
        const infoRes = await fetch(`${API_BASE_URL}/obsidian/vault/info`);
        const info = await infoRes.json();
        setVaultInfo(info);
      }
    } catch (error) {
      console.error('Failed to load vault data:', error);
      showToast('Failed to load vault information', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadVaultData();
  }, []);

  const handleIndexVault = async (maxFiles?: number) => {
    try {
      setIsIndexing(true);
      setIndexStats(null);

      const requestBody = {
        knowledge_type: 'technical',
        max_files: maxFiles || null,
      };

      const response = await fetch(`${API_BASE_URL}/obsidian/index`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(requestBody),
      });

      const result = await response.json();

      if (result.success) {
        setIndexStats(result.stats);
        showToast(
          `Successfully indexed ${result.stats.success} files${result.stats.failed > 0 ? `, ${result.stats.failed} failed` : ''}`,
          result.stats.failed > 0 ? 'warning' : 'success'
        );
        loadVaultData(); // Refresh status
      } else {
        throw new Error(result.message || 'Indexing failed');
      }
    } catch (error) {
      console.error('Failed to index vault:', error);
      showToast(`Failed to index vault: ${error}`, 'error');
    } finally {
      setIsIndexing(false);
    }
  };

  const handleStartWatching = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/obsidian/watch/start`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ knowledge_type: 'technical' }),
      });

      const result = await response.json();

      if (result.success) {
        showToast('Started watching vault for changes', 'success');
        loadVaultData();
      } else {
        throw new Error(result.error || 'Failed to start watching');
      }
    } catch (error) {
      console.error('Failed to start watching:', error);
      showToast(`Failed to start watching: ${error}`, 'error');
    }
  };

  const handleStopWatching = async () => {
    try {
      const response = await fetch(`${API_BASE_URL}/obsidian/watch/stop`, {
        method: 'POST',
      });

      const result = await response.json();

      if (result.success) {
        showToast('Stopped watching vault', 'success');
        loadVaultData();
      }
    } catch (error) {
      console.error('Failed to stop watching:', error);
      showToast(`Failed to stop watching: ${error}`, 'error');
    }
  };

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-zinc-900 dark:to-black p-6">
        <div className="max-w-6xl mx-auto">
          <div className="flex items-center justify-center h-64">
            <RefreshCw className="w-8 h-8 animate-spin text-purple-500" />
          </div>
        </div>
      </div>
    );
  }

  if (!vaultStatus?.configured) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-zinc-900 dark:to-black p-6">
        <div className="max-w-6xl mx-auto">
          <Card className="p-8 text-center">
            <BookOpen className="w-16 h-16 mx-auto mb-4 text-gray-400" />
            <h2 className="text-2xl font-bold mb-2 text-gray-800 dark:text-white">
              Obsidian Vault Not Configured
            </h2>
            <p className="text-gray-600 dark:text-gray-400 mb-4">
              Set the OBSIDIAN_VAULT environment variable to enable sync
            </p>
            <code className="block bg-gray-100 dark:bg-zinc-800 p-3 rounded text-sm">
              OBSIDIAN_VAULT=/path/to/your/vault
            </code>
          </Card>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-zinc-900 dark:to-black p-6">
      <div className="max-w-6xl mx-auto space-y-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative"
        >
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-purple-500 to-pink-500 shadow-[0_0_20px_5px_rgba(168,85,247,0.5)]"></div>
          <Card className="relative overflow-hidden">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="p-3 bg-purple-100 dark:bg-purple-900/20 rounded-lg">
                  <BookOpen className="w-8 h-8 text-purple-600 dark:text-purple-400" />
                </div>
                <div>
                  <h1 className="text-3xl font-bold text-gray-800 dark:text-white">
                    Obsidian Vault Sync
                  </h1>
                  <p className="text-gray-600 dark:text-gray-400">
                    Sync your Obsidian vault with Archon's knowledge base
                  </p>
                </div>
              </div>
              <Button
                onClick={loadVaultData}
                variant="outline"
                className="flex items-center gap-2"
              >
                <RefreshCw className="w-4 h-4" />
                Refresh
              </Button>
            </div>
          </Card>
        </motion.div>

        {/* Vault Info Grid */}
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          <Card className="p-6">
            <div className="flex items-center gap-3 mb-2">
              <Database className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              <h3 className="font-semibold text-gray-800 dark:text-white">Total Files</h3>
            </div>
            <p className="text-3xl font-bold text-gray-900 dark:text-white">
              {vaultInfo?.total_markdown_files.toLocaleString() || '0'}
            </p>
            <p className="text-sm text-gray-600 dark:text-gray-400">markdown files</p>
          </Card>

          <Card className="p-6">
            <div className="flex items-center gap-3 mb-2">
              <FileText className="w-5 h-5 text-green-600 dark:text-green-400" />
              <h3 className="font-semibold text-gray-800 dark:text-white">Vault Size</h3>
            </div>
            <p className="text-3xl font-bold text-gray-900 dark:text-white">
              {vaultInfo?.total_size_mb.toFixed(1) || '0'}
            </p>
            <p className="text-sm text-gray-600 dark:text-gray-400">MB</p>
          </Card>

          <Card className="p-6">
            <div className="flex items-center gap-3 mb-2">
              <Clock className="w-5 h-5 text-purple-600 dark:text-purple-400" />
              <h3 className="font-semibold text-gray-800 dark:text-white">Synced Files</h3>
            </div>
            <p className="text-3xl font-bold text-gray-900 dark:text-white">
              {vaultStatus?.synced_files.toLocaleString() || '0'}
            </p>
            <p className="text-sm text-gray-600 dark:text-gray-400">indexed</p>
          </Card>
        </div>

        {/* Index Stats */}
        {indexStats && (
          <motion.div
            initial={{ opacity: 0, scale: 0.95 }}
            animate={{ opacity: 1, scale: 1 }}
          >
            <Card className="p-6">
              <h3 className="font-semibold text-gray-800 dark:text-white mb-4">
                Last Index Results
              </h3>
              <div className="grid grid-cols-3 gap-4">
                <div className="flex items-center gap-3">
                  <Database className="w-5 h-5 text-gray-600" />
                  <div>
                    <p className="text-2xl font-bold text-gray-900 dark:text-white">
                      {indexStats.total}
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-400">Total</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <CheckCircle2 className="w-5 h-5 text-green-600" />
                  <div>
                    <p className="text-2xl font-bold text-green-600 dark:text-green-400">
                      {indexStats.success}
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-400">Success</p>
                  </div>
                </div>
                <div className="flex items-center gap-3">
                  <XCircle className="w-5 h-5 text-red-600" />
                  <div>
                    <p className="text-2xl font-bold text-red-600 dark:text-red-400">
                      {indexStats.failed}
                    </p>
                    <p className="text-sm text-gray-600 dark:text-gray-400">Failed</p>
                  </div>
                </div>
              </div>
            </Card>
          </motion.div>
        )}

        {/* Actions */}
        <Card className="p-6">
          <h3 className="font-semibold text-gray-800 dark:text-white mb-4">Actions</h3>

          <div className="space-y-4">
            {/* Index Actions */}
            <div>
              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                Index Vault
              </h4>
              <div className="flex gap-3 flex-wrap">
                <Button
                  onClick={() => handleIndexVault(10)}
                  disabled={isIndexing}
                  variant="outline"
                  className="flex items-center gap-2"
                >
                  {isIndexing ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <Play className="w-4 h-4" />
                  )}
                  Test (10 files)
                </Button>

                <Button
                  onClick={() => handleIndexVault()}
                  disabled={isIndexing}
                  accentColor="purple"
                  className="flex items-center gap-2"
                >
                  {isIndexing ? (
                    <RefreshCw className="w-4 h-4 animate-spin" />
                  ) : (
                    <Database className="w-4 h-4" />
                  )}
                  Index All Files ({vaultInfo?.total_markdown_files.toLocaleString()})
                </Button>
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
                Index your Obsidian vault into Archon's knowledge base for AI search
              </p>
            </div>

            {/* File Watcher */}
            <div className="pt-4 border-t border-gray-200 dark:border-zinc-800">
              <h4 className="text-sm font-medium text-gray-700 dark:text-gray-300 mb-3">
                Auto-Sync (File Watcher)
              </h4>
              <div className="flex items-center gap-3">
                {vaultStatus?.watching ? (
                  <Button
                    onClick={handleStopWatching}
                    variant="outline"
                    className="flex items-center gap-2 text-red-600 border-red-300 hover:bg-red-50 dark:border-red-800 dark:hover:bg-red-900/20"
                  >
                    <Square className="w-4 h-4" />
                    Stop Watching
                  </Button>
                ) : (
                  <Button
                    onClick={handleStartWatching}
                    variant="outline"
                    className="flex items-center gap-2"
                  >
                    <Play className="w-4 h-4" />
                    Start Watching
                  </Button>
                )}
                <span className={`text-sm ${vaultStatus?.watching ? 'text-green-600' : 'text-gray-500'}`}>
                  {vaultStatus?.watching ? '● Active' : '○ Inactive'}
                </span>
              </div>
              <p className="text-sm text-gray-600 dark:text-gray-400 mt-2">
                Automatically sync changes when you edit files in Obsidian (requires watchdog)
              </p>
            </div>
          </div>
        </Card>

        {/* Vault Path Info */}
        <Card className="p-6">
          <h3 className="font-semibold text-gray-800 dark:text-white mb-2">Vault Location</h3>
          <code className="block bg-gray-100 dark:bg-zinc-800 p-3 rounded text-sm text-gray-800 dark:text-gray-200">
            {vaultStatus?.vault_path}
          </code>
        </Card>
      </div>
    </div>
  );
};
