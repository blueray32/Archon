"""
RAG Agent - Conversational Search and Retrieval with PydanticAI

This agent enables users to search and chat with documents stored in the RAG system.
It uses the perform_rag_query functionality to retrieve relevant content and provide
intelligent responses based on the retrieved information.
"""

import json
import logging
import os
import re
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext

from .base_agent import ArchonDependencies, BaseAgent
from .mcp_client import get_mcp_client

logger = logging.getLogger(__name__)


@dataclass
class RagDependencies(ArchonDependencies):
    """Dependencies for RAG operations."""

    project_id: str | None = None
    source_filter: str | None = None
    match_count: int = 5
    min_similarity_threshold: float = 0.3  # Minimum similarity score for results
    enable_query_expansion: bool = True  # Enable automatic query expansion
    source_prioritization: bool = True  # Enable source quality prioritization
    result_clustering: bool = True  # Enable result deduplication and clustering
    progress_callback: Any | None = None  # Callback for progress updates
    # Enable PRP-style context build and guidance
    prp_mode: bool = False


class SearchResult(BaseModel):
    """Enhanced search result with quality metrics."""

    content: str = Field(description="The content of the search result")
    source: str = Field(description="Source identifier")
    url: str = Field(description="URL or location of the source")
    similarity_score: float = Field(description="Similarity score from vector search")
    relevance_score: float = Field(description="Enhanced relevance score with quality factors")
    source_quality_score: float = Field(description="Quality score of the source")
    content_type: str = Field(description="Type of content (documentation, code, tutorial, etc.)")
    metadata: dict[str, Any] = Field(description="Additional metadata")
    cluster_id: str | None = Field(description="Cluster ID for deduplication")


class RagQueryResult(BaseModel):
    """Structured output for RAG query results."""

    query_type: str = Field(description="Type of query: search, explain, summarize, compare")
    original_query: str = Field(description="The original user query")
    refined_query: str | None = Field(
        description="Refined query used for search if different from original"
    )
    expanded_queries: list[str] = Field(description="List of expanded query variations")
    results_found: int = Field(description="Number of relevant results found")
    results_processed: int = Field(description="Number of results after filtering and clustering")
    sources: list[str] = Field(description="List of unique sources referenced")
    answer: str = Field(description="The synthesized answer based on retrieved content")
    citations: list[dict[str, Any]] = Field(description="Citations with source and relevance info")
    search_results: list[SearchResult] = Field(description="Detailed search results with scores")
    performance_metrics: dict[str, float] = Field(description="Search performance metrics")
    success: bool = Field(description="Whether the query was successful")
    message: str = Field(description="Status message or error description")


class RagAgent(BaseAgent[RagDependencies, str]):
    """
    Conversational agent for RAG-based document search and retrieval.

    Capabilities:
    - Search documents using natural language queries
    - Filter by specific sources
    - Search code examples
    - Provide synthesized answers with citations
    - Explain concepts found in documentation
    """

    def __init__(self, model: str = None, **kwargs):
        # Use provided model or fall back to default
        if model is None:
            model = os.getenv("RAG_AGENT_MODEL", "openai:gpt-4o-mini")

        super().__init__(
            model=model, name="RagAgent", retries=3, enable_rate_limiting=True, **kwargs
        )

    def _create_agent(self, **kwargs) -> Agent:
        """Create the PydanticAI agent with tools and prompts."""

        agent = Agent(
            model=self.model,
            deps_type=RagDependencies,
            system_prompt="""You are an Enhanced RAG (Retrieval-Augmented Generation) Assistant that helps users search and understand documentation through intelligent, multi-layered search capabilities.

**Your Enhanced Capabilities:**
- Advanced semantic search with query expansion and refinement
- Source quality assessment and prioritization
- Result clustering and deduplication for better relevance
- Multi-factor relevance scoring (similarity + quality + content type + recency)
- Performance analysis and search optimization recommendations
- Intelligent content type classification

**Your Approach:**
1. **Understand Intent** - Analyze user query for intent (how-to, what-is, troubleshooting, etc.)
2. **Expand Query** - Generate semantic variations and synonyms for comprehensive coverage
3. **Search Intelligently** - Use enhanced search with quality scoring and filtering
4. **Process Results** - Apply relevance scoring, clustering, and deduplication
5. **Synthesize Answers** - Combine high-quality results with proper attribution
6. **Optimize Performance** - Provide search quality metrics and improvement suggestions

**Enhanced Search Features:**
- Query expansion with technical synonyms and related terms
- Source quality scoring based on authority, content type, and metadata
- Result clustering to eliminate duplicates and near-duplicates
- Content type classification (code, tutorial, API docs, troubleshooting)
- Relevance scoring beyond simple similarity (exact matches, content quality, recency)
- Search performance analysis with actionable recommendations

**Available Tools:**
- `search_documents` - Enhanced search with quality scoring and clustering
- `list_available_sources` - Basic source listing
- `search_code_examples` - Code-specific search
- `refine_search_query` - Advanced query refinement with semantic expansion
- `analyze_search_performance` - Search quality analysis and recommendations
- `get_source_quality_scores` - Source authority and quality assessment

**Response Guidelines:**
- Lead with the most relevant, highest-quality results
- Provide relevance and quality scores for transparency
- Include search performance metrics when helpful
- Suggest query refinements for poor results
- Explain source quality factors when relevant
- Always cite sources with quality indicators""",
            **kwargs,
        )

        # Register dynamic system prompt for context
        @agent.system_prompt
        async def add_search_context(ctx: RunContext[RagDependencies]) -> str:
            source_info = (
                f"Source Filter: {ctx.deps.source_filter}"
                if ctx.deps.source_filter
                else "No source filter"
            )
            return f"""
**Current Search Context:**
- Project ID: {ctx.deps.project_id or "Global search"}
- {source_info}
- Max Results: {ctx.deps.match_count}
- Timestamp: {datetime.now().isoformat()}
"""

        # Optional PRP guidance for specialized agent modes (e.g., Pydantic AI)
        @agent.system_prompt
        async def add_prp_guidance(ctx: RunContext[RagDependencies]) -> str:
            if not getattr(ctx.deps, "prp_mode", False):
                return ""
            return (
                """
PRP Mode Enabled:
- Build a concise, replayable context: prefer prime sources over broad reads
- Use RAG to fetch only what’s necessary; keep answers short and structured
- Avoid heavy I/O inline; if needed, describe steps succinctly
- Cite sources when possible and include brief, actionable follow‑ups
"""
            )

        # Register tools for RAG operations
        @agent.tool
        async def search_documents(
            ctx: RunContext[RagDependencies], query: str, source_filter: str | None = None
        ) -> str:
            """Enhanced search through documents using RAG with improved relevance scoring."""
            try:
                # Use source filter from context if not provided
                if source_filter is None:
                    source_filter = ctx.deps.source_filter

                # Expand query if enabled
                expanded_queries = [query]
                if ctx.deps.enable_query_expansion:
                    expanded_queries = await self.expand_search_query(query)

                # Perform searches with all query variations
                all_results = []
                mcp_client = await get_mcp_client()

                for expanded_query in expanded_queries:
                    try:
                        result_json = await mcp_client.perform_rag_query(
                            query=expanded_query, source=source_filter, match_count=ctx.deps.match_count * 2
                        )
                        result = json.loads(result_json)

                        if result.get("success", False):
                            query_results = result.get("results", [])
                            # Add query variation info to results
                            for res in query_results:
                                res["query_variation"] = expanded_query
                            all_results.extend(query_results)
                    except (ValueError, TypeError, KeyError) as e:
                        logger.warning(f"Search failed for query variation '{expanded_query}': {e}", exc_info=True)
                        continue
                    except Exception as e:
                        # Unexpected error - log with full context for beta debugging
                        logger.error(f"Unexpected error in search for query '{expanded_query}': {e}", exc_info=True)
                        continue

                if not all_results:
                    return await self.generate_no_results_response(query, source_filter)

                # Process and enhance results
                enhanced_results = await self.process_search_results(
                    all_results, query, ctx.deps
                )

                # Filter by similarity threshold
                filtered_results = [
                    res for res in enhanced_results
                    if res.relevance_score >= ctx.deps.min_similarity_threshold
                ]

                if not filtered_results:
                    return f"No results found above similarity threshold ({ctx.deps.min_similarity_threshold:.1%}). Try lowering the threshold or using different search terms."

                # Cluster and deduplicate if enabled
                if ctx.deps.result_clustering:
                    filtered_results = await self.cluster_and_deduplicate_results(filtered_results)

                # Limit to match_count
                final_results = filtered_results[:ctx.deps.match_count]

                return await self.format_enhanced_results(final_results, query, expanded_queries)

            except (ValueError, TypeError, KeyError) as e:
                logger.error(f"Configuration or data error in enhanced search: {e}", exc_info=True)
                return f"Search configuration error: {str(e)}. Please check your search parameters."
            except Exception as e:
                # Unexpected error - provide detailed context for beta debugging
                logger.error(f"Unexpected error in enhanced search for query '{query}': {e}", exc_info=True)
                return f"Unexpected search error: {str(e)}. This has been logged for investigation."

        @agent.tool
        async def list_available_sources(ctx: RunContext[RagDependencies]) -> str:
            """List all available sources that can be searched."""
            try:
                # Use MCP client to get available sources
                mcp_client = await get_mcp_client()
                result_json = await mcp_client.get_available_sources()

                # Parse the JSON response
                import json

                result = json.loads(result_json)

                if not result.get("success", False):
                    return f"Failed to get sources: {result.get('error', 'Unknown error')}"

                sources = result.get("sources", [])
                if not sources:
                    return "No sources are currently available. You may need to crawl some documentation first."

                source_list = []
                for source in sources:
                    source_id = source.get("source_id", "Unknown")
                    title = source.get("title", "Untitled")
                    description = source.get("description", "")
                    created = source.get("created_at", "")

                    # Format the description if available
                    desc_text = f" - {description}" if description else ""

                    source_list.append(
                        f"- **{source_id}**: {title}{desc_text} (added {created[:10]})"
                    )

                return f"Available sources ({len(sources)} total):\n" + "\n".join(source_list)

            except (ValueError, TypeError, KeyError) as e:
                logger.error(f"Data parsing error when listing sources: {e}", exc_info=True)
                return f"Error parsing source data: {str(e)}. The source list may be corrupted."
            except Exception as e:
                logger.error(f"Unexpected error listing sources: {e}", exc_info=True)
                return f"Unexpected error retrieving sources: {str(e)}. This has been logged for investigation."

        @agent.tool
        async def search_code_examples(
            ctx: RunContext[RagDependencies], query: str, source_filter: str | None = None
        ) -> str:
            """Search for code examples related to the query."""
            try:
                # Use source filter from context if not provided
                if source_filter is None:
                    source_filter = ctx.deps.source_filter

                # Use MCP client to search code examples
                mcp_client = await get_mcp_client()
                result_json = await mcp_client.search_code_examples(
                    query=query, source_id=source_filter, match_count=ctx.deps.match_count
                )

                # Parse the JSON response
                import json

                result = json.loads(result_json)

                if not result.get("success", False):
                    return f"Code search failed: {result.get('error', 'Unknown error')}"

                examples = result.get("results", result.get("code_examples", []))
                if not examples:
                    return "No code examples found for your query."

                formatted_examples = []
                for i, example in enumerate(examples, 1):
                    similarity = example.get("similarity", 0)
                    summary = example.get("summary", "No summary")
                    code = example.get("code", example.get("code_block", ""))
                    url = example.get("url", "")

                    # Extract language from code block if available
                    lang = "code"
                    if code.startswith("```"):
                        first_line = code.split("\n")[0]
                        if len(first_line) > 3:
                            lang = first_line[3:].strip()

                    formatted_examples.append(
                        f"**Example {i}** (Relevance: {similarity:.2%})\n"
                        f"Summary: {summary}\n"
                        f"Source: {url}\n"
                        f"```{lang}\n{code}\n```"
                    )

                return f"Found {len(examples)} code examples:\n\n" + "\n---\n".join(
                    formatted_examples
                )

            except (ValueError, TypeError, KeyError) as e:
                logger.error(f"Data error in code search for query '{query}': {e}", exc_info=True)
                return f"Code search data error: {str(e)}. Please check your query format."
            except Exception as e:
                logger.error(f"Unexpected error searching code examples for '{query}': {e}", exc_info=True)
                return f"Unexpected code search error: {str(e)}. This has been logged for investigation."

        @agent.tool
        async def refine_search_query(
            ctx: RunContext[RagDependencies], original_query: str, context: str
        ) -> str:
            """Advanced query refinement with semantic expansion and context awareness."""
            try:
                refined_queries = await self.advanced_query_refinement(original_query, context, ctx.deps)

                return f"Generated {len(refined_queries)} refined query variations:\n" + "\n".join([
                    f"- {query}" for query in refined_queries
                ])

            except Exception as e:
                return f"Could not refine query: {str(e)}"

        @agent.tool
        async def analyze_search_performance(
            ctx: RunContext[RagDependencies], query: str, results_count: int
        ) -> str:
            """Analyze search performance and suggest improvements."""
            try:
                analysis = await self.analyze_search_quality(query, results_count, ctx.deps)

                recommendations = []
                if analysis["avg_relevance"] < 0.5:
                    recommendations.append("Try more specific terms or synonyms")
                if analysis["source_diversity"] < 0.3:
                    recommendations.append("Consider removing source filters to get broader results")
                if results_count == 0:
                    recommendations.append("Try query expansion or reduce similarity threshold")

                return "Search Analysis:\n" + "\n".join([
                    f"- Average Relevance: {analysis['avg_relevance']:.2%}",
                    f"- Source Diversity: {analysis['source_diversity']:.2%}",
                    f"- Query Complexity: {analysis['query_complexity']}",
                    "\nRecommendations:",
                    *[f"- {rec}" for rec in recommendations]
                ])

            except Exception as e:
                return f"Could not analyze search performance: {str(e)}"

        @agent.tool
        async def get_source_quality_scores(ctx: RunContext[RagDependencies]) -> str:
            """Get quality scores for all available sources."""
            try:
                sources = await self.get_enhanced_source_info()

                sorted_sources = sorted(sources, key=lambda x: x["quality_score"], reverse=True)

                source_list = []
                for source in sorted_sources[:10]:  # Top 10
                    quality = source["quality_score"]
                    name = source["name"]
                    content_type = source.get("content_type", "unknown")
                    word_count = source.get("word_count", 0)

                    source_list.append(
                        f"- **{name}** (Quality: {quality:.2f}, Type: {content_type}, Words: {word_count:,})"
                    )

                return "Top Quality Sources:\n" + "\n".join(source_list)

            except Exception as e:
                return f"Could not get source quality scores: {str(e)}"

        return agent

    async def expand_search_query(self, query: str) -> list[str]:
        """Expand a search query with synonyms and related terms."""
        try:
            expanded_queries = [query]
            query_lower = query.lower()

            # Technical term expansions
            expansions = {
                "api": ["API", "endpoint", "service", "interface"],
                "function": ["method", "procedure", "routine", "def"],
                "error": ["exception", "bug", "issue", "problem", "failure"],
                "install": ["setup", "configuration", "deployment", "installation"],
                "tutorial": ["guide", "walkthrough", "example", "how-to"],
                "documentation": ["docs", "reference", "manual", "specification"],
                "configuration": ["config", "settings", "setup", "options"],
                "authentication": ["auth", "login", "security", "credentials"],
                "database": ["db", "storage", "persistence", "data"],
                "frontend": ["UI", "interface", "client", "web"],
                "backend": ["server", "service", "API", "microservice"]
            }

            # Add expansions based on query terms
            for term, synonyms in expansions.items():
                if term in query_lower:
                    for synonym in synonyms:
                        expanded_query = query.replace(term, synonym)
                        if expanded_query != query:
                            expanded_queries.append(expanded_query)

            # Add context-based expansions
            if any(word in query_lower for word in ["how", "tutorial", "guide"]):
                expanded_queries.append(f"{query} example")
                expanded_queries.append(f"{query} step by step")

            if any(word in query_lower for word in ["what", "definition"]):
                expanded_queries.append(f"{query} explanation")
                expanded_queries.append(f"{query} overview")

            # Remove duplicates while preserving order
            seen = set()
            unique_queries = []
            for q in expanded_queries:
                if q.lower() not in seen:
                    seen.add(q.lower())
                    unique_queries.append(q)

            return unique_queries[:5]  # Limit to 5 variations

        except Exception as e:
            logger.error(f"Error expanding query: {e}")
            return [query]

    async def process_search_results(
        self, raw_results: list[dict[str, Any]], query: str, deps: RagDependencies
    ) -> list[SearchResult]:
        """Process and enhance search results with quality scores."""
        try:
            enhanced_results = []

            for result in raw_results:
                # Extract basic info
                content = result.get("content", "")
                metadata = result.get("metadata", {})
                similarity = float(result.get("similarity_score", result.get("similarity", 0)))
                source = metadata.get("source", "Unknown")
                url = metadata.get("url", result.get("url", ""))

                # Calculate enhanced relevance score
                relevance_score = await self.calculate_relevance_score(
                    content, query, similarity, metadata
                )

                # Calculate source quality score
                source_quality = await self.calculate_source_quality_score(metadata)

                # Determine content type
                content_type = await self.classify_content_type(content, metadata)

                enhanced_result = SearchResult(
                    content=content,
                    source=source,
                    url=url,
                    similarity_score=similarity,
                    relevance_score=relevance_score,
                    source_quality_score=source_quality,
                    content_type=content_type,
                    metadata=metadata,
                    cluster_id=None  # Will be set during clustering
                )

                enhanced_results.append(enhanced_result)

            # Sort by relevance score
            enhanced_results.sort(key=lambda x: x.relevance_score, reverse=True)

            return enhanced_results

        except Exception as e:
            logger.error(f"Error processing search results: {e}")
            return []

    async def calculate_relevance_score(
        self, content: str, query: str, similarity: float, metadata: dict[str, Any]
    ) -> float:
        """Calculate enhanced relevance score considering multiple factors."""
        try:
            # Start with similarity score
            score = similarity

            # Boost for exact query matches in content
            query_terms = query.lower().split()
            content_lower = content.lower()

            exact_matches = sum(1 for term in query_terms if term in content_lower)
            exact_match_boost = (exact_matches / len(query_terms)) * 0.2
            score += exact_match_boost

            # Boost for content type relevance
            content_type = metadata.get("knowledge_type", "")
            if content_type == "technical":
                score += 0.1  # Technical content often more relevant for dev queries

            # Boost for recent content
            created_at = metadata.get("created_at", "")
            if created_at and "2025" in created_at:
                score += 0.05  # Recent content boost

            # Penalty for very short content
            if len(content) < 100:
                score -= 0.1

            # Boost for comprehensive content
            if len(content) > 1000:
                score += 0.05

            # Normalize to 0-1 range
            return min(1.0, max(0.0, score))

        except Exception as e:
            logger.error(f"Error calculating relevance score: {e}")
            return similarity

    async def calculate_source_quality_score(self, metadata: dict[str, Any]) -> float:
        """Calculate source quality score based on various factors."""
        try:
            score = 0.5  # Base score

            # Boost for official documentation sources
            url = metadata.get("original_url", "").lower()

            if any(domain in url for domain in ["docs.", "documentation", "api.", "github.com"]):
                score += 0.3

            # Boost for established domains
            if any(domain in url for domain in ["google.com", "microsoft.com", "python.org", "mozilla.org"]):
                score += 0.2

            # Content type scoring
            knowledge_type = metadata.get("knowledge_type", "")
            if knowledge_type == "technical":
                score += 0.1
            elif knowledge_type == "business":
                score += 0.05

            # Word count consideration
            total_words = metadata.get("total_words", 0)
            if isinstance(total_words, int | float):
                if 1000 <= total_words <= 50000:  # Sweet spot for comprehensive docs
                    score += 0.1
                elif total_words > 100000:  # Very large sources might be less focused
                    score -= 0.05

            # Auto-generated content penalty
            if metadata.get("auto_generated", False):
                score -= 0.1

            return min(1.0, max(0.0, score))

        except Exception as e:
            logger.error(f"Error calculating source quality: {e}")
            return 0.5

    async def classify_content_type(self, content: str, metadata: dict[str, Any]) -> str:
        """Classify the type of content for better categorization."""
        try:
            content_lower = content.lower()

            # Check for code patterns
            if any(pattern in content for pattern in ["def ", "class ", "function", "import ", "```"]):
                return "code"

            # Check for tutorial patterns
            if any(word in content_lower for word in ["step", "tutorial", "how to", "example", "guide"]):
                return "tutorial"

            # Check for API documentation
            if any(word in content_lower for word in ["endpoint", "parameter", "response", "method", "api"]):
                return "api_documentation"

            # Check for error/troubleshooting content
            if any(word in content_lower for word in ["error", "troubleshoot", "fix", "solution", "problem"]):
                return "troubleshooting"

            # Check for configuration content
            if any(word in content_lower for word in ["config", "setup", "install", "configure"]):
                return "configuration"

            # Default to documentation
            return "documentation"

        except Exception as e:
            logger.error(f"Error classifying content type: {e}")
            return "unknown"

    async def cluster_and_deduplicate_results(self, results: list[SearchResult]) -> list[SearchResult]:
        """Cluster similar results and remove duplicates."""
        try:
            if len(results) <= 1:
                return results

            # Simple clustering based on content similarity and source
            clusters = {}
            deduplicated = []

            for result in results:
                # Create a clustering key based on source and content similarity
                content_hash = hash(result.content[:200])  # Use first 200 chars for similarity
                cluster_key = f"{result.source}_{content_hash % 1000}"

                if cluster_key not in clusters:
                    clusters[cluster_key] = result
                    result.cluster_id = cluster_key
                    deduplicated.append(result)
                else:
                    # Keep the result with higher relevance score
                    existing = clusters[cluster_key]
                    if result.relevance_score > existing.relevance_score:
                        # Replace the existing result
                        deduplicated.remove(existing)
                        clusters[cluster_key] = result
                        result.cluster_id = cluster_key
                        deduplicated.append(result)

            return deduplicated

        except Exception as e:
            logger.error(f"Error clustering results: {e}")
            return results

    async def format_enhanced_results(
        self, results: list[SearchResult], query: str, expanded_queries: list[str]
    ) -> str:
        """Format enhanced search results with detailed information."""
        try:
            if not results:
                return "No enhanced results found."

            # Calculate summary statistics
            avg_relevance = sum(r.relevance_score for r in results) / len(results)
            unique_sources = len({r.source for r in results})
            content_types = {}
            for r in results:
                content_types[r.content_type] = content_types.get(r.content_type, 0) + 1

            # Format header with search info
            header = f"**Enhanced Search Results** ({len(results)} results)\n"
            header += f"Query: {query}\n"
            if len(expanded_queries) > 1:
                header += f"Expanded to {len(expanded_queries)} variations\n"
            header += f"Average Relevance: {avg_relevance:.2%}\n"
            header += f"Sources: {unique_sources} unique\n"
            header += f"Content Types: {', '.join(f'{k}({v})' for k, v in content_types.items())}\n\n"

            # Format individual results
            formatted_results = []
            for i, result in enumerate(results, 1):
                content = result.content
                if len(content) > 400:
                    content = content[:400] + "..."

                result_text = (
                    f"**Result {i}** [{result.content_type}]\n"
                    f"Relevance: {result.relevance_score:.2%} | "
                    f"Similarity: {result.similarity_score:.2%} | "
                    f"Source Quality: {result.source_quality_score:.2%}\n"
                    f"Source: {result.source}\n"
                    f"URL: {result.url}\n"
                    f"Content: {content}\n"
                )

                formatted_results.append(result_text)

            return header + "\n---\n".join(formatted_results)

        except Exception as e:
            logger.error(f"Error formatting enhanced results: {e}")
            return f"Error formatting results: {str(e)}"

    async def generate_no_results_response(self, query: str, source_filter: str | None) -> str:
        """Generate helpful response when no results are found."""
        suggestions = [
            "Try using more general search terms",
            "Check for typos in your query",
            "Remove source filters to search all available content",
            "Try synonyms or alternative phrasings",
            "Break complex queries into simpler parts"
        ]

        response = f"No results found for query: '{query}'\n\n"
        if source_filter:
            response += f"Source filter applied: {source_filter}\n\n"
        response += "Suggestions to improve your search:\n"
        response += "\n".join(f"- {suggestion}" for suggestion in suggestions)

        return response

    async def advanced_query_refinement(
        self, query: str, context: str, deps: RagDependencies
    ) -> list[str]:
        """Advanced query refinement with semantic understanding."""
        try:
            refined_queries = [query]

            # Intent-based refinement
            query_lower = query.lower()

            # How-to queries
            if any(word in query_lower for word in ["how", "tutorial", "guide"]):
                refined_queries.extend([
                    f"{query} example",
                    f"{query} step by step",
                    f"{query} walkthrough"
                ])

            # What-is queries
            elif any(word in query_lower for word in ["what", "definition", "explain"]):
                refined_queries.extend([
                    f"{query} overview",
                    f"{query} documentation",
                    f"{query} reference"
                ])

            # Error/troubleshooting queries
            elif any(word in query_lower for word in ["error", "issue", "problem", "fix"]):
                refined_queries.extend([
                    f"{query} solution",
                    f"{query} troubleshooting",
                    f"{query} debugging"
                ])

            # API queries
            elif "api" in query_lower:
                refined_queries.extend([
                    f"{query} documentation",
                    f"{query} reference",
                    f"{query} example"
                ])

            # Add context if provided
            if context and context.strip():
                context_query = f"{query} {context}"
                refined_queries.append(context_query)

            return refined_queries[:5]  # Limit to 5 variations

        except Exception as e:
            logger.error(f"Error in advanced query refinement: {e}")
            return [query]

    async def analyze_search_quality(
        self, query: str, results_count: int, deps: RagDependencies
    ) -> dict[str, float]:
        """Analyze search quality and return metrics."""
        try:
            # Simple quality analysis
            query_complexity = len(query.split()) / 10.0  # Normalize to 0-1
            query_specificity = len([w for w in query.split() if len(w) > 4]) / len(query.split())

            return {
                "avg_relevance": 0.7,  # Would calculate from actual results
                "source_diversity": 0.6,  # Would calculate from actual sources
                "query_complexity": query_complexity,
                "query_specificity": query_specificity,
                "results_coverage": min(1.0, results_count / deps.match_count)
            }

        except Exception as e:
            logger.error(f"Error analyzing search quality: {e}")
            return {"avg_relevance": 0.5, "source_diversity": 0.5, "query_complexity": 0.5}

    async def get_enhanced_source_info(self) -> list[dict[str, Any]]:
        """Get enhanced information about available sources."""
        try:
            mcp_client = await get_mcp_client()
            result_json = await mcp_client.get_available_sources()
            result = json.loads(result_json)

            if not result.get("success", False):
                return []

            sources = result.get("sources", [])
            enhanced_sources = []

            for source in sources:
                quality_score = await self.calculate_source_quality_score(source.get("metadata", {}))
                enhanced_source = {
                    "name": source.get("title", "Unknown"),
                    "source_id": source.get("source_id", ""),
                    "quality_score": quality_score,
                    "content_type": source.get("metadata", {}).get("knowledge_type", "unknown"),
                    "word_count": source.get("total_words", 0),
                    "created_at": source.get("created_at", "")
                }
                enhanced_sources.append(enhanced_source)

            return enhanced_sources

        except Exception as e:
            logger.error(f"Error getting enhanced source info: {e}")
            return []

    def get_system_prompt(self) -> str:
        """Get the base system prompt for this agent."""
        try:
            from ..services.prompt_service import prompt_service

            return prompt_service.get_prompt(
                "rag_assistant",
                default="RAG Assistant for intelligent document search and retrieval.",
            )
        except Exception as e:
            logger.warning(f"Could not load prompt from service: {e}")
            return "RAG Assistant for intelligent document search and retrieval."

    async def run_conversation(
        self,
        user_message: str,
        project_id: str | None = None,
        source_filter: str | None = None,
        match_count: int = 5,
        user_id: str = None,
        progress_callback: Any = None,
    ) -> RagQueryResult:
        """
        Run the agent for conversational RAG queries.

        Args:
            user_message: The user's search query or question
            project_id: Optional project ID for context
            source_filter: Optional source domain to filter results
            match_count: Maximum number of results to return
            user_id: ID of the user making the request
            progress_callback: Optional callback for progress updates

        Returns:
            Structured RagQueryResult
        """
        deps = RagDependencies(
            project_id=project_id,
            source_filter=source_filter,
            match_count=match_count,
            user_id=user_id,
            progress_callback=progress_callback,
        )

        try:
            # Run the enhanced agent and get the string response
            response_text = await self.run(user_message, deps)
            self.logger.info("Enhanced RAG query completed successfully")

            # Enhanced analysis of the response to gather detailed metadata
            query_type = await self.classify_query_type(user_message)
            results_found = 0
            results_processed = 0
            sources = []
            expanded_queries = []
            search_results = []
            performance_metrics = {}

            # Extract metrics from response
            if "Enhanced Search Results" in response_text:
                # Extract number of results
                match = re.search(r"\((\d+) results\)", response_text)
                if match:
                    results_found = int(match.group(1))
                    results_processed = results_found

                # Extract expanded queries info
                if "Expanded to" in response_text:
                    exp_match = re.search(r"Expanded to (\d+) variations", response_text)
                    if exp_match:
                        expanded_queries = [f"Query variation {i+1}" for i in range(int(exp_match.group(1)))]

                # Extract source information
                sources_match = re.search(r"Sources: (\d+) unique", response_text)
                if sources_match:
                    unique_sources_count = int(sources_match.group(1))
                    sources = [f"Source {i+1}" for i in range(unique_sources_count)]

                # Extract average relevance
                relevance_match = re.search(r"Average Relevance: ([\d.]+)%", response_text)
                if relevance_match:
                    performance_metrics["avg_relevance"] = float(relevance_match.group(1)) / 100

            elif "no results" in response_text.lower():
                results_found = 0
                query_type = "no_results"

            elif "available sources" in response_text.lower():
                query_type = "list_sources"
                # Count sources listed
                source_lines = [line for line in response_text.split("\n") if line.strip().startswith("-")]
                results_found = len(source_lines)

            elif "code example" in response_text.lower():
                query_type = "code_search"

            return RagQueryResult(
                query_type=query_type,
                original_query=user_message,
                refined_query=None,
                expanded_queries=expanded_queries,
                results_found=results_found,
                results_processed=results_processed,
                sources=sources,
                answer=response_text,
                citations=[],  # Could be enhanced to extract structured citations
                search_results=search_results,  # Could be populated with structured results
                performance_metrics=performance_metrics,
                success=True,
                message="Enhanced query completed successfully",
            )

        except (ValueError, TypeError, KeyError) as e:
            self.logger.error(f"Data/configuration error in RAG query '{user_message}': {str(e)}", exc_info=True)
            # Return error result with specific context
        except Exception as e:
            self.logger.error(f"Unexpected error in RAG query '{user_message}': {str(e)}", exc_info=True)
            # Return error result with full context for beta debugging
            return RagQueryResult(
                query_type="error",
                original_query=user_message,
                refined_query=None,
                expanded_queries=[],
                results_found=0,
                results_processed=0,
                sources=[],
                answer=f"I encountered an error while searching: {str(e)}",
                citations=[],
                search_results=[],
                performance_metrics={},
                success=False,
                message=f"Failed to process enhanced query: {str(e)}",
            )


    async def classify_query_type(self, query: str) -> str:
        """Classify the type of user query for better handling."""
        query_lower = query.lower()

        if any(word in query_lower for word in ["how", "tutorial", "guide", "step"]):
            return "how_to"
        elif any(word in query_lower for word in ["what", "definition", "explain"]):
            return "what_is"
        elif any(word in query_lower for word in ["error", "issue", "problem", "fix", "troubleshoot"]):
            return "troubleshooting"
        elif any(word in query_lower for word in ["example", "code", "sample"]):
            return "code_search"
        elif any(word in query_lower for word in ["sources", "available", "list"]):
            return "list_sources"
        elif any(word in query_lower for word in ["api", "endpoint", "method"]):
            return "api_documentation"
        elif any(word in query_lower for word in ["compare", "difference", "vs"]):
            return "comparison"
        else:
            return "general_search"


# Note: RagAgent instances should be created on-demand in API endpoints
# to avoid initialization issues during module import
