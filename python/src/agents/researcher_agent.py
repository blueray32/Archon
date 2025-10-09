"""
ResearcherAgent - Advanced Research and Analysis Agent

A comprehensive research agent with advanced capabilities including:
- Agentic RAG with knowledge graph integration
- Long-term memory integration
- Web search capabilities
- Image analysis
- Code execution
- Multi-modal document processing
- Entity relationship analysis

Based on the Dynamous AI Agent Mastery implementation patterns.
"""

import json
import logging
import os
from dataclasses import dataclass
from typing import Any, List, Optional
from datetime import datetime

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from openai import AsyncOpenAI
from httpx import AsyncClient

from .base_agent import ArchonDependencies, BaseAgent
from .mcp_client import get_mcp_client
from .researcher_tools import (
    web_search_tool,
    retrieve_relevant_documents_tool,
    list_documents_tool,
    get_document_content_tool,
    execute_sql_query_tool,
    execute_safe_code_tool,
    image_analysis_tool,
    graph_search_tool,
    entity_relationships_tool,
    entity_timeline_tool,
    compile_restricted
)

logger = logging.getLogger(__name__)


@dataclass
class ResearcherDependencies(ArchonDependencies):
    """Dependencies for Researcher agent operations."""

    # Core RAG settings
    project_id: str | None = None
    source_filter: str | None = None
    match_count: int = 5
    min_similarity_threshold: float = 0.3

    # Research capabilities
    enable_web_search: bool = True
    enable_image_analysis: bool = True
    enable_code_execution: bool = True
    enable_knowledge_graph: bool = True

    # Memory and personalization
    user_memories: str = ""
    enable_memory_retrieval: bool = True

    # External service clients (for legacy compatibility)
    embedding_client: AsyncOpenAI | None = None
    http_client: AsyncClient | None = None
    brave_api_key: str | None = None
    searxng_base_url: str | None = None
    graph_client: Any | None = None  # Optional GraphitiClient


class ResearchContext(BaseModel):
    """Context for research operations."""

    query: str = Field(description="The research query")
    search_depth: str = Field(default="standard", description="Search depth: shallow, standard, deep")
    focus_areas: List[str] = Field(default_factory=list, description="Specific areas to focus on")
    exclude_sources: List[str] = Field(default_factory=list, description="Sources to exclude")
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class ResearcherAgent(BaseAgent):
    """
    Advanced research agent with comprehensive analysis capabilities.

    This agent excels at:
    - Retrieving and synthesizing information from diverse sources
    - Conducting web research when local knowledge is insufficient
    - Analyzing images and visual content
    - Executing code for data analysis
    - Tracking entity relationships over time
    - Providing personalized responses based on user memory
    """

    def get_system_prompt(self) -> str:
        """Get the system prompt for the researcher agent."""
        return self._get_system_prompt()

    def _create_agent(self, **kwargs) -> Agent:
        """Create the PydanticAI agent with research capabilities."""

        # Get model configuration from environment
        llm_model = os.getenv('LLM_CHOICE', 'gpt-4o-mini')

        agent = Agent(
            model=f"openai:{llm_model}",
            deps_type=ResearcherDependencies,
            retries=2,
            system_prompt=self._get_system_prompt(),
            **kwargs
        )

        # Add memory integration
        @agent.system_prompt
        async def add_user_memories(ctx: RunContext[ResearcherDependencies]) -> str:
            """Include user memories in system context."""
            if ctx.deps.user_memories and ctx.deps.enable_memory_retrieval:
                return f"\nUser Memories:\n{ctx.deps.user_memories}"
            return ""

        # Core research tools
        self._add_rag_tools(agent)
        self._add_web_search_tools(agent)
        self._add_analysis_tools(agent)
        self._add_knowledge_graph_tools(agent)

        return agent

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the researcher agent."""
        return """
You are an intelligent AI research assistant with advanced analysis capabilities. You excel at retrieving, processing, and synthesizing information from diverse sources to provide accurate, comprehensive answers. You are intuitive, friendly, and proactive, always aiming to deliver the most relevant information while maintaining clarity and precision.

CRITICAL: You must SYNTHESIZE and ANALYZE information, not just return raw search results. Always provide intelligent, well-structured responses that demonstrate understanding of the content.

Goal:
Your goal is to provide accurate, relevant, and well-sourced information by utilizing your comprehensive suite of tools. You streamline the user's research process, offer insightful analysis, and ensure they receive reliable answers to their queries. You help users by delivering thoughtful, well-researched responses that save them time and enhance their understanding of complex topics.

Tool Usage Strategy:
1. **Memory First**: Always begin by checking user memories to personalize responses
2. **Document Retrieval Strategy**:
   - For general queries: Use RAG first, then analyze individual documents if needed
   - For numerical/data queries: Use SQL on tabular data
   - For visual content: Use image analysis tools
3. **Web Search**: Use when local knowledge is insufficient or outdated
4. **Knowledge Graph**: Leverage entity relationships and temporal analysis when available
5. **Code Execution**: Use for complex calculations or data analysis

RESPONSE FORMAT - ALWAYS FOLLOW THIS STRUCTURE:

## Direct Answer
Start with a clear, direct answer to the user's question.

## Key Insights
Synthesize 2-3 key insights from the retrieved information, showing connections and patterns.

## Detailed Analysis
Provide deeper analysis of the most relevant findings, explaining implications and context.

## Sources & Evidence
List the specific sources that support your analysis, with brief descriptions of what each contributes.

## Next Steps / Recommendations
When appropriate, suggest follow-up questions or areas for further exploration.

Research Best Practices:
- NEVER just list raw search results - always synthesize and analyze
- Start with the answer, then provide supporting evidence
- Show connections between different sources and concepts
- Explain the significance and implications of findings
- Use clear section headers to organize your response
- Cite specific sources with their relevance explained
- Request clarification for ambiguous queries (after checking memories)
- Present numerical findings with context and units
- Prioritize recent and authoritative sources
- Clearly state when information appears outdated or incomplete
- Acknowledge when web search might provide more current information

Remember: You are a research analyst, not a search engine. Provide intelligent synthesis, not raw data dumps.
"""

    def _add_rag_tools(self, agent: Agent) -> None:
        """Add RAG and document retrieval tools."""

        @agent.tool
        async def retrieve_relevant_documents(
            ctx: RunContext[ResearcherDependencies], user_query: str
        ) -> str:
            """
            Retrieve relevant document chunks based on the query with RAG.
            Enhanced with knowledge graph search when available.

            Args:
                user_query: The user's question or query

            Returns:
                Formatted string containing the most relevant document chunks
            """
            try:
                # Use MCP client first for Archon integration
                mcp_client = await get_mcp_client()
                result = await mcp_client.call_tool(
                    "perform_rag_query",
                    query=user_query,
                    match_count=ctx.deps.match_count,
                    source_domain=ctx.deps.source_filter
                )

                if result.get("success"):
                    documents = result.get("results", [])
                    if documents:
                        formatted_results = []
                        formatted_results.append("=== RETRIEVED DOCUMENTS FOR SYNTHESIS ===")
                        formatted_results.append("Instructions: ANALYZE and SYNTHESIZE this information. Do NOT just list it.")
                        formatted_results.append("")

                        for i, doc in enumerate(documents[:ctx.deps.match_count], 1):
                            content = doc.get("content", "")
                            metadata = doc.get("metadata", {})
                            source = metadata.get("source", "Unknown")
                            url = metadata.get("url", "")

                            # Clean and truncate content for better processing
                            clean_content = content.replace('\n', ' ').strip()
                            if len(clean_content) > 500:
                                clean_content = clean_content[:500] + "..."

                            formatted_results.append(f"SOURCE {i}: {source}")
                            formatted_results.append(f"URL: {url}")
                            formatted_results.append(f"CONTENT: {clean_content}")
                            formatted_results.append("---")

                        formatted_results.append("")
                        formatted_results.append("TASK: Synthesize this information into a well-structured response following the required format. Do NOT just repeat the raw content above.")

                        return "\n".join(formatted_results)

                # Fallback message if MCP is not available
                return "No relevant documents found. MCP service may be unavailable."

                return "No relevant documents found in the knowledge base."

            except Exception as e:
                logger.error(f"Error in retrieve_relevant_documents: {e}")
                return f"Error retrieving documents: {str(e)}"

        @agent.tool
        async def list_available_documents(ctx: RunContext[ResearcherDependencies]) -> str:
            """
            Retrieve a list of all available documents in the knowledge base.

            Returns:
                List of documents with their metadata
            """
            try:
                mcp_client = await get_mcp_client()
                result = await mcp_client.call_tool("get_available_sources")

                if result.get("success"):
                    sources = result.get("sources", [])
                    if sources:
                        formatted_sources = []
                        for source in sources:
                            name = source.get("name", "Unknown")
                            domain = source.get("domain", "")
                            doc_count = source.get("document_count", 0)
                            formatted_sources.append(f"- {name} ({domain}) - {doc_count} documents")
                        return "Available sources:\n" + "\n".join(formatted_sources)
                    else:
                        return "No sources available in the knowledge base."
                else:
                    return f"Error listing sources: {result.get('error', 'Unknown error')}"

            except Exception as e:
                logger.error(f"Error in list_available_documents: {e}")
                return f"Error listing documents: {str(e)}"

    def _add_web_search_tools(self, agent: Agent) -> None:
        """Add web search capabilities."""

        @agent.tool
        async def web_search(ctx: RunContext[ResearcherDependencies], query: str) -> str:
            """
            Search the web for current information when local knowledge is insufficient.

            Args:
                query: The search query

            Returns:
                Summary of web search results
            """
            if not ctx.deps.enable_web_search:
                return "Web search is disabled for this session."

            try:
                return await web_search_tool(
                    query,
                    ctx.deps.http_client,
                    ctx.deps.brave_api_key,
                    ctx.deps.searxng_base_url
                )

            except Exception as e:
                logger.error(f"Error in web_search: {e}")
                return f"Error performing web search: {str(e)}"

    def _add_analysis_tools(self, agent: Agent) -> None:
        """Add analysis and computation tools."""

        @agent.tool
        async def analyze_image(
            ctx: RunContext[ResearcherDependencies],
            document_id: str,
            analysis_query: str
        ) -> str:
            """
            Analyze an image from the knowledge base using vision capabilities.

            Args:
                document_id: ID of the image document
                analysis_query: What to analyze in the image

            Returns:
                Analysis results
            """
            if not ctx.deps.enable_image_analysis:
                return "Image analysis is disabled for this session."

            try:
                # Image analysis not yet available without direct Supabase access
                return f"Image analysis for document '{document_id}' - Feature requires database access setup."

            except Exception as e:
                logger.error(f"Error in analyze_image: {e}")
                return f"Error analyzing image: {str(e)}"

        @agent.tool
        async def execute_code(
            ctx: RunContext[ResearcherDependencies],
            code: str,
            language: str = "python"
        ) -> str:
            """
            Execute code safely for data analysis and calculations.

            Args:
                code: The code to execute
                language: Programming language (currently supports python)

            Returns:
                Execution results
            """
            if not ctx.deps.enable_code_execution:
                return "Code execution is disabled for this session."

            try:
                if language.lower() != "python":
                    return f"Language '{language}' not supported. Only Python is currently available."

                # Check if RestrictedPython is available
                if compile_restricted is None:
                    return "Code execution requires RestrictedPython library. Feature not available in this container."

                return execute_safe_code_tool(code)

            except Exception as e:
                logger.error(f"Error in execute_code: {e}")
                return f"Error executing code: {str(e)}"

    def _add_knowledge_graph_tools(self, agent: Agent) -> None:
        """Add knowledge graph and entity analysis tools."""

        @agent.tool
        async def search_entities(
            ctx: RunContext[ResearcherDependencies],
            entity_name: str
        ) -> str:
            """
            Search for information about a specific entity in the knowledge graph.

            Args:
                entity_name: Name of the entity to search for

            Returns:
                Entity information and relationships
            """
            if not ctx.deps.enable_knowledge_graph:
                return "Knowledge graph features are disabled for this session."

            try:
                return await graph_search_tool(ctx.deps.graph_client, entity_name)

            except Exception as e:
                logger.error(f"Error in search_entities: {e}")
                return f"Error searching entities: {str(e)}"

        @agent.tool
        async def analyze_entity_relationships(
            ctx: RunContext[ResearcherDependencies],
            entity_name: str,
            depth: int = 2
        ) -> str:
            """
            Analyze relationships and connections for a specific entity.

            Args:
                entity_name: Name of the entity
                depth: Relationship depth to analyze

            Returns:
                Entity relationship analysis
            """
            if not ctx.deps.enable_knowledge_graph:
                return "Knowledge graph features are disabled for this session."

            try:
                return await entity_relationships_tool(ctx.deps.graph_client, entity_name, depth)

            except Exception as e:
                logger.error(f"Error in analyze_entity_relationships: {e}")
                return f"Error analyzing relationships: {str(e)}"

        @agent.tool
        async def entity_timeline(
            ctx: RunContext[ResearcherDependencies],
            entity_name: str
        ) -> str:
            """
            Get temporal timeline for a specific entity.

            Args:
                entity_name: Name of the entity

            Returns:
                Entity timeline analysis
            """
            if not ctx.deps.enable_knowledge_graph:
                return "Knowledge graph features are disabled for this session."

            try:
                return await entity_timeline_tool(ctx.deps.graph_client, entity_name)

            except Exception as e:
                logger.error(f"Error in entity_timeline: {e}")
                return f"Error generating entity timeline: {str(e)}"

    async def run(
        self,
        message: str,
        dependencies: ResearcherDependencies,
        **kwargs
    ) -> Any:
        """
        Run the researcher agent with the given message and dependencies.

        Args:
            message: User's research query
            dependencies: Research agent dependencies
            **kwargs: Additional arguments

        Returns:
            Research response
        """
        try:
            # Update dependencies with any runtime configuration
            if not dependencies.embedding_client:
                # Initialize OpenAI client for embeddings if needed
                api_key = os.getenv('OPENAI_API_KEY')
                if api_key:
                    dependencies.embedding_client = AsyncOpenAI(api_key=api_key)

            if not dependencies.http_client:
                # Initialize HTTP client for web requests
                dependencies.http_client = AsyncClient()

            # Load additional configuration from environment
            dependencies.brave_api_key = os.getenv('BRAVE_API_KEY')
            dependencies.searxng_base_url = os.getenv('SEARXNG_BASE_URL')

            # Run the agent
            agent = self._create_agent()
            result = await agent.run(message, deps=dependencies, **kwargs)

            return result

        except Exception as e:
            logger.error(f"Error running researcher agent: {e}")
            raise
        finally:
            # Cleanup HTTP client if we created it
            if dependencies.http_client:
                await dependencies.http_client.aclose()