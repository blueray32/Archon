/**
 * Knowledge Base service for managing documentation sources
 */

// Types
export interface KnowledgeItemMetadata {
  knowledge_type?: 'technical' | 'business'
  tags?: string[]
  source_type?: 'url' | 'file'
  status?: 'active' | 'processing' | 'error'
  description?: string
  last_scraped?: string
  chunks_count?: number
  word_count?: number
  file_name?: string
  file_type?: string
  page_count?: number
  update_frequency?: number
  next_update?: string
  group_name?: string
  original_url?: string
}

export interface KnowledgeItem {
  id: string
  title: string
  url: string
  source_id: string
  metadata: KnowledgeItemMetadata
  created_at: string
  updated_at: string
  code_examples?: unknown[] // Code examples from backend
}

export interface KnowledgeItemsResponse {
  items: KnowledgeItem[]
  total: number
  page: number
  per_page: number
}

export interface KnowledgeItemsFilter {
  knowledge_type?: 'technical' | 'business'
  tags?: string[]
  source_type?: 'url' | 'file'
  search?: string
  page?: number
  per_page?: number
}

export interface CrawlRequest {
  url: string
  knowledge_type?: 'technical' | 'business'
  tags?: string[]
  update_frequency?: number
  max_depth?: number
  crawl_options?: {
    max_concurrent?: number
  }
}

export interface UploadMetadata {
  knowledge_type?: 'technical' | 'business'
  tags?: string[]
}

export interface SearchOptions {
  knowledge_type?: 'technical' | 'business'
  sources?: string[]
  limit?: number
}

// Use relative URL to go through Vite proxy
import { API_BASE_URL } from '../config/api';
import { logger } from '../utils/logger';
// const API_BASE_URL = '/api'; // Now imported from config

// Helper function for API requests with timeout
async function apiRequest<T>(
  endpoint: string,
  options: RequestInit = {}
): Promise<T> {
  const url = `${API_BASE_URL}${endpoint}`;
  logger.info(`🔍 [KnowledgeBase] Starting API request to: ${url}`);
  logger.debug(`🔍 [KnowledgeBase] Request method: ${options.method || 'GET'}`);
  logger.debug(`🔍 [KnowledgeBase] API_BASE_URL: "${API_BASE_URL}"`);
  
  // Create an AbortController for timeout
  const controller = new AbortController();
  const timeoutId = setTimeout(() => {
    logger.error(`⏰ [KnowledgeBase] Request timeout after 60 seconds for: ${url}`);
    controller.abort();
  }, 60000); // 60 second timeout (server may be processing heavy operations)
  
  try {
    logger.debug(`🚀 [KnowledgeBase] Sending fetch request...`);
    const response = await fetch(url, {
      headers: {
        'Content-Type': 'application/json',
        ...options.headers
      },
      ...options,
      signal: controller.signal
    });
    
    clearTimeout(timeoutId);
    logger.debug(`✅ [KnowledgeBase] Response received:`, response.status, response.statusText);
    logger.debug(`✅ [KnowledgeBase] Response headers:`, response.headers);

    if (!response.ok) {
      logger.error(`❌ [KnowledgeBase] Response not OK: ${response.status} ${response.statusText}`);
      let message = `HTTP ${response.status}`;
      try {
        const error = await response.json();
        logger.error(`❌ [KnowledgeBase] API error response:`, error);
        // Try common FastAPI shapes
        message =
          (error && (error.error as string)) ||
          (error && error.detail && (error.detail.error as string)) ||
          (error && (error.detail as string)) ||
          message;
      } catch (e) {
        logger.error('❌ [KnowledgeBase] Failed to parse error JSON');
      }
      throw new Error(message);
    }

    const data = await response.json();
    logger.debug(`✅ [KnowledgeBase] Response data received, type: ${typeof data}`);
    return data;
  } catch (error) {
    clearTimeout(timeoutId);
    logger.error(`❌ [KnowledgeBase] Request failed:`, error);
    logger.error(`❌ [KnowledgeBase] Error name: ${error instanceof Error ? error.name : 'Unknown'}`);
    logger.error(`❌ [KnowledgeBase] Error message: ${error instanceof Error ? error.message : String(error)}`);
    logger.error(`❌ [KnowledgeBase] Error stack:`, error instanceof Error ? error.stack : 'No stack');
    
    // Check if it's a timeout error
    if (error instanceof Error && error.name === 'AbortError') {
      throw new Error('Request timed out after 60 seconds');
    }
    
    throw error;
  }
}

class KnowledgeBaseService {
  /**
   * Get knowledge items with optional filtering
   */
  async getKnowledgeItems(filter: KnowledgeItemsFilter = {}): Promise<KnowledgeItemsResponse> {
    logger.info('📋 [KnowledgeBase] Getting knowledge items with filter:', filter);
    
    const params = new URLSearchParams()
    
    // Add default pagination
    params.append('page', String(filter.page || 1))
    params.append('per_page', String(filter.per_page || 20))
    
    // Add optional filters
    if (filter.knowledge_type) params.append('knowledge_type', filter.knowledge_type)
    if (filter.tags && filter.tags.length > 0) params.append('tags', filter.tags.join(','))
    if (filter.source_type) params.append('source_type', filter.source_type)
    if (filter.search) params.append('search', filter.search)
    
    const queryString = params.toString();
    logger.debug('📋 [KnowledgeBase] Query string:', queryString);
    logger.debug('📋 [KnowledgeBase] Full endpoint:', `/knowledge-items?${queryString}`);
    
    const response = await apiRequest<KnowledgeItemsResponse>(`/knowledge-items?${params}`)
    
    // Debug logging to inspect response
    logger.debug('📋 [KnowledgeBase] Response received:', response);
    logger.debug('📋 [KnowledgeBase] Total items:', response.items?.length);
    
    // Check if any items have code_examples
    const itemsWithCodeExamples = response.items?.filter(item => item.code_examples && item.code_examples.length > 0) || [];
    logger.debug('📋 [KnowledgeBase] Items with code examples:', itemsWithCodeExamples.length);
    
    // Log details for modelcontextprotocol.io
    const mcpItem = response.items?.find(item => item.source_id === 'modelcontextprotocol.io');
    if (mcpItem) {
      logger.debug('📋 [KnowledgeBase] MCP item found:', mcpItem);
      logger.debug('📋 [KnowledgeBase] MCP code_examples:', mcpItem.code_examples);
    }
    
    return response
  }

  /**
   * Delete a knowledge item by source_id
   */
  async deleteKnowledgeItem(sourceId: string) {
    return apiRequest(`/knowledge-items/${sourceId}`, {
      method: 'DELETE'
    })
  }

  /**
   * Update knowledge item metadata
   */
  async updateKnowledgeItem(sourceId: string, updates: Partial<KnowledgeItemMetadata>) {
    // Use POST endpoint with source_id in body to avoid 414 errors with long source_ids
    return apiRequest('/knowledge-items/update', {
      method: 'POST',
      body: JSON.stringify({
        source_id: sourceId,
        updates: updates
      })
    })
  }

  /**
   * Get knowledge items by group name (avoids URL length limits)
   */
  async getKnowledgeItemsByGroup(groupName: string, perPage: number = 1000): Promise<KnowledgeItemsResponse> {
    return apiRequest('/knowledge-items/by-group', {
      method: 'POST',
      body: JSON.stringify({
        group_name: groupName,
        per_page: perPage
      })
    })
  }

  /**
   * Refresh a knowledge item by re-crawling its URL
   */
  async refreshKnowledgeItem(sourceId: string) {
    logger.info('🔄 [KnowledgeBase] Refreshing knowledge item:', sourceId);
    
    return apiRequest(`/knowledge-items/${sourceId}/refresh`, {
      method: 'POST'
    })
  }

  /**
   * Get document chunks for a knowledge item with optional domain filtering
   */
  async getKnowledgeItemChunks(sourceId: string, domainFilter?: string) {
    logger.info('📄 [KnowledgeBase] Getting chunks for:', sourceId, 'domainFilter:', domainFilter);
    
    const params = new URLSearchParams();
    if (domainFilter) {
      params.append('domain_filter', domainFilter);
    }
    
    const queryString = params.toString();
    const endpoint = `/knowledge-items/${sourceId}/chunks${queryString ? `?${queryString}` : ''}`;
    
    return apiRequest<{
      success: boolean;
      source_id: string;
      domain_filter?: string;
      chunks: Array<{
        id: string;
        source_id: string;
        content: string;
        metadata?: Record<string, unknown>;
        url?: string;
      }>;
      count: number;
    }>(endpoint);
  }

  /**
   * Upload a document to the knowledge base with progress tracking
   */
  async uploadDocument(file: File, metadata: UploadMetadata = {}) {
    const formData = new FormData()
    formData.append('file', file)

    // Send fields as expected by backend API
    if (metadata.knowledge_type) {
      formData.append('knowledge_type', metadata.knowledge_type)
    }
    if (metadata.tags && metadata.tags.length > 0) {
      formData.append('tags', JSON.stringify(metadata.tags))
    }

    const response = await fetch(`${API_BASE_URL}/documents/upload`, {
      method: 'POST',
      body: formData
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.error || `HTTP ${response.status}`)
    }

    return response.json()
  }

  /**
   * Upload multiple documents from a folder to the knowledge base with progress tracking
   */
  async uploadFolder(files: File[], metadata: UploadMetadata = {}) {
    const formData = new FormData()

    // Append all files
    for (const file of files) {
      formData.append('files', file)
    }

    // Send fields as expected by backend API
    if (metadata.knowledge_type) {
      formData.append('knowledge_type', metadata.knowledge_type)
    }
    if (metadata.tags && metadata.tags.length > 0) {
      formData.append('tags', JSON.stringify(metadata.tags))
    }

    const response = await fetch(`${API_BASE_URL}/documents/upload-folder`, {
      method: 'POST',
      body: formData
    })

    if (!response.ok) {
      const error = await response.json()
      throw new Error(error.error || `HTTP ${response.status}`)
    }

    return response.json()
  }

  /**
   * Start crawling a URL with metadata
   */
  async crawlUrl(request: CrawlRequest) {
    logger.info('📡 Sending crawl request:', request);
    
    const response = await apiRequest('/knowledge-items/crawl', {
      method: 'POST',
      body: JSON.stringify(request)
    });
    
    logger.debug('📡 Crawl response received:', response);
    logger.debug('📡 Response type:', typeof response);
    {
      const r = response as unknown as Record<string, unknown>;
      logger.debug('📡 Response has progressId?', 'progressId' in r);
    }
    
    return response;
  }

  /**
   * Get detailed information about a knowledge item
   */
  async getKnowledgeItemDetails(sourceId: string) {
    return apiRequest(`/knowledge-items/${sourceId}/details`)
  }

  /**
   * Search across the knowledge base
   */
  async searchKnowledgeBase(query: string, options: SearchOptions = {}) {
    return apiRequest('/knowledge-items/search', {
      method: 'POST',
      body: JSON.stringify({
        query,
        ...options
      })
    })
  }

  /**
   * Stop a running crawl task
   */
  async stopCrawl(progressId: string) {
    logger.warn('🛑 [KnowledgeBase] Stopping crawl:', progressId);
    
    return apiRequest(`/knowledge-items/stop/${progressId}`, {
      method: 'POST'
    });
  }

  /**
   * Get code examples for a specific knowledge item
   */
  async getCodeExamples(sourceId: string) {
    logger.info('📚 [KnowledgeBase] Fetching code examples for:', sourceId);
    
    return apiRequest<{
      success: boolean
      source_id: string
      code_examples: unknown[]
      count: number
    }>(`/knowledge-items/${sourceId}/code-examples`);
  }

  /**
   * Start server-side export of the knowledge base to the local Obsidian vault
   */
  async exportToVault(options?: {
    targetPath?: string;
    sourceIds?: string[];
    tags?: string[];
    knowledgeType?: 'technical' | 'business';
    updatedSince?: string; // ISO 8601
  }): Promise<{ success: boolean; progressId: string; message?: string }>{
    const body: Record<string, unknown> = {};
    if (options?.targetPath) body.target = options.targetPath;
    if (options?.sourceIds && options.sourceIds.length) body.source_ids = options.sourceIds;
    if (options?.tags && options.tags.length) body.tags = options.tags;
    if (options?.knowledgeType) body.knowledge_type = options.knowledgeType;
    if (options?.updatedSince) body.updated_since = options.updatedSince;
    return apiRequest('/knowledge-items/export-to-vault', {
      method: 'POST',
      body: JSON.stringify(body),
    });
  }

  /** Get progress for a running operation (crawl, upload, export) */
  async getProgress(progressId: string): Promise<{
    progressId: string;
    status: string;
    progress: number;
    message?: string;
    error?: string;
  }>{
    return apiRequest(`/crawl-progress/${progressId}`);
  }

  /** Stop a running operation by progressId (crawl or export) */
  async stopOperation(progressId: string): Promise<{ success: boolean; message: string; progressId: string }>{
    return apiRequest(`/knowledge-items/stop/${progressId}`, { method: 'POST' });
  }

  /** Get the server's default export target (OBSIDIAN_VAULT) */
  async getExportDefaultTarget(): Promise<{
    defaultTarget?: string;
    exists: boolean;
    isDir: boolean;
  }>{
    return apiRequest('/knowledge-items/export-default-target');
  }

}

// Export singleton instance
export const knowledgeBaseService = new KnowledgeBaseService() 
