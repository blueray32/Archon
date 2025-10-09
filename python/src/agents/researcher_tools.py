"""
Researcher Tools - Advanced tool implementations for the Researcher Agent

Comprehensive tool suite including:
- RAG and document retrieval
- Web search (Brave API and SearXNG)
- Image analysis with vision models
- Safe code execution
- Knowledge graph operations
- Entity relationship analysis

Based on the Dynamous AI Agent Mastery implementation.
"""

import base64
import json
import logging
import os
import re
import sys
from io import StringIO
from typing import Any, Dict, List, Optional

from openai import AsyncOpenAI
from httpx import AsyncClient
from typing import TYPE_CHECKING

# Only import these for type hints, not at runtime in agents container
if TYPE_CHECKING:
    from supabase import Client

try:
    from RestrictedPython import compile_restricted
    from RestrictedPython.Guards import safe_globals, safe_builtins
except ImportError:
    # Fallback if RestrictedPython not available
    compile_restricted = None
    safe_globals = {}
    safe_builtins = {}

logger = logging.getLogger(__name__)

# Configuration
EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL_CHOICE', 'text-embedding-3-small')
VISION_MODEL = os.getenv('VISION_LLM_CHOICE', 'gpt-4o-mini')


async def brave_web_search(query: str, http_client: AsyncClient, brave_api_key: str) -> str:
    """
    Search the web using Brave API and return summarized results.

    Args:
        query: Search query
        http_client: HTTP client for requests
        brave_api_key: Brave API key

    Returns:
        Formatted search results
    """
    try:
        headers = {
            'X-Subscription-Token': brave_api_key,
            'Accept': 'application/json',
        }

        response = await http_client.get(
            'https://api.search.brave.com/res/v1/web/search',
            params={
                'q': query,
                'count': 5,
                'text_decorations': True,
                'search_lang': 'en'
            },
            headers=headers
        )
        response.raise_for_status()
        data = response.json()

        results = []
        web_results = data.get('web', {}).get('results', [])

        for item in web_results[:3]:
            title = item.get('title', '')
            description = item.get('description', '')
            url = item.get('url', '')
            if title and description:
                results.append(f"Title: {title}\nSummary: {description}\nSource: {url}\n")

        return "\n".join(results) if results else "No results found for the query."

    except Exception as e:
        logger.error(f"Error in brave_web_search: {e}")
        return f"Error performing Brave search: {str(e)}"


async def searxng_web_search(query: str, http_client: AsyncClient, searxng_base_url: str) -> str:
    """
    Search the web using SearXNG and return results.

    Args:
        query: Search query
        http_client: HTTP client for requests
        searxng_base_url: SearXNG instance URL

    Returns:
        Formatted search results
    """
    try:
        params = {'q': query, 'format': 'json'}

        response = await http_client.get(f"{searxng_base_url}/search", params=params)
        response.raise_for_status()

        data = response.json()
        results = ""

        for i, page in enumerate(data.get('results', []), 1):
            if i > 10:
                break

            results += f"{i}. {page.get('title', 'No title')}\n"
            results += f"   URL: {page.get('url', 'No URL')}\n"
            results += f"   Content: {page.get('content', 'No content')[:300]}...\n\n"

        return results if results else "No results found for the query."

    except Exception as e:
        logger.error(f"Error in searxng_web_search: {e}")
        return f"Error performing SearXNG search: {str(e)}"


async def web_search_tool(
    query: str,
    http_client: AsyncClient,
    brave_api_key: Optional[str] = None,
    searxng_base_url: Optional[str] = None
) -> str:
    """
    Unified web search tool that uses either Brave API or SearXNG.

    Args:
        query: Search query
        http_client: HTTP client for requests
        brave_api_key: Optional Brave API key
        searxng_base_url: Optional SearXNG URL

    Returns:
        Formatted search results
    """
    try:
        if brave_api_key:
            return await brave_web_search(query, http_client, brave_api_key)
        elif searxng_base_url:
            return await searxng_web_search(query, http_client, searxng_base_url)
        else:
            return "No web search service configured. Please set BRAVE_API_KEY or SEARXNG_BASE_URL."

    except Exception as e:
        logger.error(f"Error in web_search_tool: {e}")
        return f"Error performing web search: {str(e)}"


async def retrieve_relevant_documents_tool(
    supabase: "Client",
    embedding_client: AsyncOpenAI,
    user_query: str,
    graph_client: Any = None,
    match_count: int = 4
) -> str:
    """
    Retrieve relevant document chunks using RAG with optional knowledge graph enhancement.

    Args:
        supabase: Supabase client
        embedding_client: OpenAI client for embeddings
        user_query: User's query
        graph_client: Optional knowledge graph client
        match_count: Number of results to return

    Returns:
        Formatted relevant documents
    """
    try:
        # Generate embedding for the query
        response = await embedding_client.embeddings.create(
            model=EMBEDDING_MODEL,
            input=user_query
        )
        query_embedding = response.data[0].embedding

        # Perform vector similarity search
        result = supabase.rpc(
            'match_documents',
            {
                'query_embedding': query_embedding,
                'match_threshold': 0.3,
                'match_count': match_count
            }
        ).execute()

        if not result.data:
            return "No relevant documents found in the knowledge base."

        # Format results
        formatted_results = []
        for i, doc in enumerate(result.data, 1):
            content = doc.get('content', '')
            metadata = doc.get('metadata', {})
            source = metadata.get('source', 'Unknown')
            similarity = doc.get('similarity', 0)

            formatted_results.append(
                f"Document {i} (Similarity: {similarity:.3f}):\n"
                f"Source: {source}\n"
                f"Content: {content[:500]}...\n"
            )

        # TODO: Add knowledge graph enhancement if graph_client is available
        if graph_client:
            # Add entity-based context from knowledge graph
            pass

        return "\n".join(formatted_results)

    except Exception as e:
        logger.error(f"Error in retrieve_relevant_documents_tool: {e}")
        return f"Error retrieving documents: {str(e)}"


async def list_documents_tool(supabase: "Client") -> List[str]:
    """
    List all available documents in the knowledge base.

    Args:
        supabase: Supabase client

    Returns:
        List of document information
    """
    try:
        result = supabase.from_('documents').select(
            'id, metadata, created_at'
        ).limit(50).execute()

        if not result.data:
            return ["No documents found in the knowledge base."]

        documents = []
        for doc in result.data:
            metadata = doc.get('metadata', {})
            source = metadata.get('source', 'Unknown')
            file_type = metadata.get('file_type', 'Unknown')
            created = doc.get('created_at', 'Unknown')

            documents.append(
                f"ID: {doc['id']} | Source: {source} | Type: {file_type} | Created: {created}"
            )

        return documents

    except Exception as e:
        logger.error(f"Error in list_documents_tool: {e}")
        return [f"Error listing documents: {str(e)}"]


async def get_document_content_tool(supabase: "Client", document_id: str) -> str:
    """
    Retrieve the full content of a specific document.

    Args:
        supabase: Supabase client
        document_id: Document ID

    Returns:
        Full document content
    """
    try:
        result = supabase.from_('documents').select(
            'content, metadata'
        ).eq('id', document_id).execute()

        if not result.data:
            return f"Document with ID '{document_id}' not found."

        doc = result.data[0]
        content = doc.get('content', '')
        metadata = doc.get('metadata', {})
        source = metadata.get('source', 'Unknown')

        return f"Document: {source}\n\nContent:\n{content}"

    except Exception as e:
        logger.error(f"Error in get_document_content_tool: {e}")
        return f"Error retrieving document content: {str(e)}"


async def execute_sql_query_tool(supabase: "Client", sql_query: str) -> str:
    """
    Execute a read-only SQL query on the document data.

    Args:
        supabase: Supabase client
        sql_query: SQL query to execute

    Returns:
        Query results in JSON format
    """
    try:
        # Validate that query is read-only (basic check)
        query_lower = sql_query.lower().strip()
        if not query_lower.startswith('select'):
            return "Only SELECT queries are allowed for security reasons."

        # Check for dangerous operations
        dangerous_keywords = ['insert', 'update', 'delete', 'drop', 'create', 'alter']
        if any(keyword in query_lower for keyword in dangerous_keywords):
            return "Query contains potentially dangerous operations. Only SELECT queries are allowed."

        # Execute the query using Supabase RPC
        result = supabase.rpc('execute_sql_rpc', {'sql_query': sql_query}).execute()

        if result.data:
            return json.dumps(result.data, indent=2)
        else:
            return "Query executed successfully but returned no results."

    except Exception as e:
        logger.error(f"Error in execute_sql_query_tool: {e}")
        return f"Error executing SQL query: {str(e)}"


def execute_safe_code_tool(code: str) -> str:
    """
    Execute Python code safely using RestrictedPython.

    Args:
        code: Python code to execute

    Returns:
        Execution output
    """
    try:
        # Compile the code with restrictions
        compiled_code = compile_restricted(code, '<string>', 'exec')

        if compiled_code.errors:
            return f"Compilation errors: {', '.join(compiled_code.errors)}"

        # Set up safe execution environment
        safe_dict = {
            '__builtins__': safe_builtins,
            '__name__': '__main__',
            '__metaclass__': type,
            '_print_': lambda *args: print(*args),
            '_getattr_': getattr,
            '_getitem_': lambda obj, key: obj[key],
            '_getiter_': iter,
            '_write_': lambda x: x,
        }

        # Add safe modules
        import math
        import json
        import datetime
        safe_dict.update({
            'math': math,
            'json': json,
            'datetime': datetime,
        })

        # Capture output
        old_stdout = sys.stdout
        sys.stdout = captured_output = StringIO()

        try:
            # Execute the code
            exec(compiled_code.code, safe_dict)
            output = captured_output.getvalue()
            return output if output else "Code executed successfully (no output)."

        finally:
            sys.stdout = old_stdout

    except Exception as e:
        logger.error(f"Error in execute_safe_code_tool: {e}")
        return f"Error executing code: {str(e)}"


async def image_analysis_tool(
    supabase: "Client",
    document_id: str,
    query: str
) -> str:
    """
    Analyze an image from the knowledge base using vision capabilities.

    Args:
        supabase: Supabase client
        document_id: Image document ID
        query: Analysis query

    Returns:
        Image analysis results
    """
    try:
        # Retrieve image document
        result = supabase.from_('documents').select(
            'content, metadata'
        ).eq('id', document_id).execute()

        if not result.data:
            return f"Image document with ID '{document_id}' not found."

        doc = result.data[0]
        metadata = doc.get('metadata', {})

        # Check if it's an image
        file_type = metadata.get('file_type', '').lower()
        if not any(img_type in file_type for img_type in ['image', 'png', 'jpg', 'jpeg', 'gif']):
            return f"Document '{document_id}' is not an image file."

        # Get binary content (assuming it's stored as base64)
        content = doc.get('content', '')
        if not content:
            return "Image content is empty or not available."

        # Initialize vision model
        api_key = os.getenv('OPENAI_API_KEY')
        if not api_key:
            return "OpenAI API key not configured for image analysis."

        client = AsyncOpenAI(api_key=api_key)

        # Analyze image
        response = await client.chat.completions.create(
            model=VISION_MODEL,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": f"Analyze this image and answer: {query}"
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{content}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=500
        )

        analysis = response.choices[0].message.content
        return f"Image Analysis for '{document_id}':\n\n{analysis}"

    except Exception as e:
        logger.error(f"Error in image_analysis_tool: {e}")
        return f"Error analyzing image: {str(e)}"


# Knowledge Graph Tools (placeholder implementations)

async def graph_search_tool(graph_client: Any, query: str) -> str:
    """
    Search the knowledge graph for entities and relationships.

    Args:
        graph_client: Knowledge graph client
        query: Search query

    Returns:
        Search results from knowledge graph
    """
    try:
        if not graph_client:
            return "Knowledge graph not available."

        # TODO: Implement actual graph search
        return f"Knowledge graph search for '{query}' - Implementation needed."

    except Exception as e:
        logger.error(f"Error in graph_search_tool: {e}")
        return f"Error searching knowledge graph: {str(e)}"


async def entity_relationships_tool(
    graph_client: Any,
    entity_name: str,
    depth: int = 2
) -> str:
    """
    Get relationships for a specific entity from the knowledge graph.

    Args:
        graph_client: Knowledge graph client
        entity_name: Entity name
        depth: Relationship depth

    Returns:
        Entity relationships
    """
    try:
        if not graph_client:
            return "Knowledge graph not available."

        # TODO: Implement actual entity relationship analysis
        return f"Entity relationships for '{entity_name}' (depth {depth}) - Implementation needed."

    except Exception as e:
        logger.error(f"Error in entity_relationships_tool: {e}")
        return f"Error analyzing entity relationships: {str(e)}"


async def entity_timeline_tool(graph_client: Any, entity_name: str) -> str:
    """
    Get temporal timeline for a specific entity.

    Args:
        graph_client: Knowledge graph client
        entity_name: Entity name

    Returns:
        Entity timeline
    """
    try:
        if not graph_client:
            return "Knowledge graph not available."

        # TODO: Implement actual entity timeline analysis
        return f"Entity timeline for '{entity_name}' - Implementation needed."

    except Exception as e:
        logger.error(f"Error in entity_timeline_tool: {e}")
        return f"Error generating entity timeline: {str(e)}"