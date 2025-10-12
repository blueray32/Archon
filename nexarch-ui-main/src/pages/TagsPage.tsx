import { useState, useEffect } from 'react';
import { motion } from 'framer-motion';
import { Tags, RefreshCw, Zap, BarChart3, Search, Filter } from 'lucide-react';
import { Card } from '../components/ui/Card';
import { Button } from '../components/ui/Button';
import { useToast } from '../contexts/ToastContext';
import { API_BASE_URL } from '../config/api';

interface TagStats {
  total_items: number;
  tagged_items: number;
  untagged_items: number;
  auto_tagged_items: number;
  manually_tagged_items: number;
  tagging_percentage: number;
  unique_tags: number;
  average_tags_per_item: number;
}

interface TagCounts {
  [key: string]: number;
}

export const TagsPage = () => {
  const [stats, setStats] = useState<TagStats | null>(null);
  const [allTags, setAllTags] = useState<TagCounts>({});
  const [topTags, setTopTags] = useState<TagCounts>({});
  const [loading, setLoading] = useState(true);
  const [batchTagging, setBatchTagging] = useState(false);
  const [searchFilter, setSearchFilter] = useState('');
  const { showToast } = useToast();

  const loadData = async () => {
    try {
      setLoading(true);

      // Load stats
      const statsRes = await fetch(`${API_BASE_URL}/tags/stats`);
      const statsData = await statsRes.json();
      setStats(statsData);

      // Load all tags
      const tagsRes = await fetch(`${API_BASE_URL}/tags/all`);
      const tagsData = await tagsRes.json();
      setAllTags(tagsData.tags || {});
      setTopTags(tagsData.top_tags || {});
    } catch (error) {
      console.error('Failed to load tags data:', error);
      showToast('Failed to load tags information', 'error');
    } finally {
      setLoading(false);
    }
  };

  useEffect(() => {
    loadData();
  }, []);

  const handleBatchTag = async (maxItems?: number) => {
    try {
      setBatchTagging(true);

      const response = await fetch(`${API_BASE_URL}/tags/batch`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          force: true,
          max_items: maxItems || null,
        }),
      });

      const result = await response.json();

      if (result.success) {
        showToast(
          `Tagged ${result.stats.success} items with ${result.stats.tags_generated} tags`,
          'success'
        );
        loadData(); // Refresh data
      } else {
        throw new Error(result.message || 'Batch tagging failed');
      }
    } catch (error) {
      console.error('Failed to batch tag:', error);
      showToast(`Failed to batch tag: ${error}`, 'error');
    } finally {
      setBatchTagging(false);
    }
  };

  const filteredTags = Object.entries(allTags).filter(([tag]) =>
    tag.toLowerCase().includes(searchFilter.toLowerCase())
  );

  if (loading) {
    return (
      <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-zinc-900 dark:to-black p-6">
        <div className="max-w-7xl mx-auto">
          <div className="flex items-center justify-center h-64">
            <RefreshCw className="w-8 h-8 animate-spin text-blue-500" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-50 to-gray-100 dark:from-zinc-900 dark:to-black p-6">
      <div className="max-w-7xl mx-auto space-y-6">
        {/* Header */}
        <motion.div
          initial={{ opacity: 0, y: -20 }}
          animate={{ opacity: 1, y: 0 }}
          className="relative"
        >
          <div className="absolute top-0 left-0 right-0 h-[2px] bg-gradient-to-r from-blue-500 to-purple-500 shadow-[0_0_20px_5px_rgba(59,130,246,0.5)]" />
          <Card className="relative overflow-hidden">
            <div className="flex items-center justify-between">
              <div className="flex items-center gap-4">
                <div className="p-3 bg-blue-100 dark:bg-blue-900/20 rounded-lg">
                  <Tags className="w-8 h-8 text-blue-600 dark:text-blue-400" />
                </div>
                <div>
                  <h1 className="text-3xl font-bold text-gray-800 dark:text-white">
                    Auto-Tagging System
                  </h1>
                  <p className="text-gray-600 dark:text-gray-400">
                    AI-powered automatic tag generation and management
                  </p>
                </div>
              </div>
              <Button onClick={loadData} variant="outline" className="flex items-center gap-2">
                <RefreshCw className="w-4 h-4" />
                Refresh
              </Button>
            </div>
          </Card>
        </motion.div>

        {/* Stats Grid */}
        <div className="grid grid-cols-1 md:grid-cols-4 gap-4">
          <Card className="p-6">
            <div className="flex items-center gap-3 mb-2">
              <BarChart3 className="w-5 h-5 text-blue-600 dark:text-blue-400" />
              <h3 className="font-semibold text-gray-800 dark:text-white">Total Items</h3>
            </div>
            <p className="text-3xl font-bold text-gray-900 dark:text-white">
              {stats?.total_items.toLocaleString() || '0'}
            </p>
            <p className="text-sm text-gray-600 dark:text-gray-400">in knowledge base</p>
          </Card>

          <Card className="p-6">
            <div className="flex items-center gap-3 mb-2">
              <Zap className="w-5 h-5 text-green-600 dark:text-green-400" />
              <h3 className="font-semibold text-gray-800 dark:text-white">Auto-Tagged</h3>
            </div>
            <p className="text-3xl font-bold text-gray-900 dark:text-white">
              {stats?.auto_tagged_items.toLocaleString() || '0'}
            </p>
            <p className="text-sm text-gray-600 dark:text-gray-400">by AI</p>
          </Card>

          <Card className="p-6">
            <div className="flex items-center gap-3 mb-2">
              <Tags className="w-5 h-5 text-purple-600 dark:text-purple-400" />
              <h3 className="font-semibold text-gray-800 dark:text-white">Unique Tags</h3>
            </div>
            <p className="text-3xl font-bold text-gray-900 dark:text-white">
              {stats?.unique_tags || '0'}
            </p>
            <p className="text-sm text-gray-600 dark:text-gray-400">categories</p>
          </Card>

          <Card className="p-6">
            <div className="flex items-center gap-3 mb-2">
              <BarChart3 className="w-5 h-5 text-orange-600 dark:text-orange-400" />
              <h3 className="font-semibold text-gray-800 dark:text-white">Coverage</h3>
            </div>
            <p className="text-3xl font-bold text-gray-900 dark:text-white">
              {stats?.tagging_percentage.toFixed(1) || '0'}%
            </p>
            <p className="text-sm text-gray-600 dark:text-gray-400">items tagged</p>
          </Card>
        </div>

        {/* Actions */}
        <Card className="p-6">
          <h3 className="font-semibold text-gray-800 dark:text-white mb-4">Batch Tagging</h3>
          <div className="flex gap-3 flex-wrap">
            <Button
              onClick={() => handleBatchTag(50)}
              disabled={batchTagging}
              variant="outline"
              className="flex items-center gap-2"
            >
              {batchTagging ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Zap className="w-4 h-4" />
              )}
              Tag 50 Items
            </Button>

            <Button
              onClick={() => handleBatchTag(200)}
              disabled={batchTagging}
              variant="outline"
              className="flex items-center gap-2"
            >
              {batchTagging ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Zap className="w-4 h-4" />
              )}
              Tag 200 Items
            </Button>

            <Button
              onClick={() => handleBatchTag(1000)}
              disabled={batchTagging}
              accentColor="blue"
              className="flex items-center gap-2"
            >
              {batchTagging ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Tags className="w-4 h-4" />
              )}
              Tag 1,000 Items
            </Button>

            <Button
              onClick={() => handleBatchTag()}
              disabled={batchTagging}
              accentColor="purple"
              className="flex items-center gap-2"
            >
              {batchTagging ? (
                <RefreshCw className="w-4 h-4 animate-spin" />
              ) : (
                <Zap className="w-4 h-4" />
              )}
              Tag All Items ({stats?.total_items.toLocaleString()})
            </Button>
          </div>
          <p className="text-sm text-gray-600 dark:text-gray-400 mt-3">
            AI will analyze content and automatically generate relevant tags for each item
          </p>
        </Card>

        {/* Tags Browser */}
        <Card className="p-6">
          <div className="flex items-center justify-between mb-4">
            <h3 className="font-semibold text-gray-800 dark:text-white">All Tags</h3>
            <div className="relative">
              <Search className="absolute left-3 top-1/2 transform -translate-y-1/2 w-4 h-4 text-gray-400" />
              <input
                type="text"
                placeholder="Search tags..."
                value={searchFilter}
                onChange={(e) => setSearchFilter(e.target.value)}
                className="pl-10 pr-4 py-2 bg-white dark:bg-zinc-800 border border-gray-300 dark:border-zinc-700 rounded-lg text-sm focus:outline-none focus:ring-2 focus:ring-blue-500"
              />
            </div>
          </div>

          <div className="flex flex-wrap gap-2">
            {filteredTags.length > 0 ? (
              filteredTags.map(([tag, count]) => (
                <div
                  key={tag}
                  className="px-3 py-2 bg-gradient-to-r from-blue-50 to-purple-50 dark:from-blue-900/20 dark:to-purple-900/20 border border-blue-200 dark:border-blue-800 rounded-lg flex items-center gap-2"
                >
                  <span className="text-sm font-medium text-gray-800 dark:text-white">
                    {tag}
                  </span>
                  <span className="px-2 py-0.5 bg-blue-600 dark:bg-blue-500 text-white text-xs rounded-full">
                    {count}
                  </span>
                </div>
              ))
            ) : (
              <p className="text-gray-500 dark:text-gray-400">No tags found</p>
            )}
          </div>
        </Card>
      </div>
    </div>
  );
};
