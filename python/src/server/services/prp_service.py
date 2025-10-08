"""
PRP Service - Handles PRP document management, embedding, and RAG retrieval.
"""

import logging
import os
from typing import Any

from openai import AsyncOpenAI

logger = logging.getLogger(__name__)


class PRPService:
    """Service for PRP document management and RAG retrieval."""

    def __init__(self, supabase_client, openai_api_key: str | None = None):
        """
        Initialize PRP service.

        Args:
            supabase_client: Supabase client instance
            openai_api_key: OpenAI API key for embeddings
        """
        self.supabase = supabase_client
        self.openai_key = openai_api_key or os.getenv("OPENAI_API_KEY")
        self.embedding_model = os.getenv("PRP_EMBEDDING_MODEL", "text-embedding-3-small")
        self.chat_model = os.getenv("PRP_CHAT_MODEL", "gpt-4o-mini")
        self.top_k = int(os.getenv("PRP_RAG_TOP_K", "6"))
        self.max_context_chars = int(os.getenv("PRP_MAX_CONTEXT_CHARS", "60000"))

        if self.openai_key:
            self.openai_client = AsyncOpenAI(api_key=self.openai_key)
        else:
            self.openai_client = None
            logger.warning("PRP Service initialized without OpenAI API key - embeddings disabled")

    async def create_embedding(self, text: str) -> list[float] | None:
        """
        Create embedding for text using OpenAI.

        Args:
            text: Text to embed

        Returns:
            Embedding vector or None if failed
        """
        if not self.openai_client:
            logger.error("Cannot create embedding - OpenAI client not initialized")
            return None

        try:
            response = await self.openai_client.embeddings.create(model=self.embedding_model, input=text)
            return response.data[0].embedding
        except Exception as e:
            logger.error(f"Failed to create embedding: {e}")
            return None

    async def retrieve_context(self, session_id: str, user_message: str, top_k: int | None = None) -> dict[str, Any]:
        """
        Retrieve relevant context for a user message using RAG.

        Combines:
        1. Recent PRPs (product requirement prompts)
        2. Recent conversation history for this session
        3. Vector similarity search

        Args:
            session_id: Chat session ID
            user_message: User's current message
            top_k: Number of results to retrieve (default from config)

        Returns:
            Dict with 'context' (str) and 'sources' (list)
        """
        if not self.openai_client:
            logger.warning("RAG retrieval disabled - no OpenAI client")
            return {"context": "", "sources": []}

        k = top_k or self.top_k

        try:
            # Create embedding for user message
            embedding = await self.create_embedding(user_message)
            if not embedding:
                return {"context": "", "sources": []}

            context_parts: list[str] = []
            sources: list[dict[str, Any]] = []

            # Vector similarity over PRP docs (most relevant first)
            try:
                prp_sim = self.supabase.rpc(
                    "search_prp_docs",
                    {
                        "query_embedding": embedding,
                        "kind_filter": "prp",
                        "match_count": min(k, 6),
                        "similarity_threshold": 0.6,
                    },
                ).execute()
            except Exception as e:  # noqa: BLE001
                logger.error(f"PRP doc similarity search failed: {e}")
                prp_sim = type("obj", (), {"data": []})()  # empty-like

            if getattr(prp_sim, "data", None):
                prp_context = []
                for row in prp_sim.data:
                    title = row.get("title") or row.get("path", "Unnamed PRP")
                    prp_context.append(f"## {title}\n{row.get('content','')}")
                    sources.append(
                        {
                            "type": "prp",
                            "path": row.get("path"),
                            "title": title,
                            "similarity": row.get("similarity"),
                        }
                    )
                if prp_context:
                    context_parts.append(
                        "=== Relevant Product Requirement Prompts (PRPs) ===\n" + "\n\n".join(prp_context)
                    )

            # Vector similarity over prior messages in this session
            try:
                msg_sim = self.supabase.rpc(
                    "search_prp_messages",
                    {
                        "query_embedding": embedding,
                        "session_filter": session_id,
                        "match_count": min(k * 2, 20),
                        "similarity_threshold": 0.6,
                    },
                ).execute()
            except Exception as e:  # noqa: BLE001
                logger.error(f"PRP message similarity search failed: {e}")
                msg_sim = type("obj", (), {"data": []})()

            if getattr(msg_sim, "data", None):
                conv_context = []
                for row in msg_sim.data:
                    role = (row.get("role") or "").upper()
                    content = row.get("content") or ""
                    conv_context.append(f"{role}: {content}")
                if conv_context:
                    context_parts.append("=== Relevant Conversation (Similar) ===\n" + "\n".join(conv_context))

            # Also include very recent messages for continuity (chrono)
            try:
                message_results = (
                    self.supabase.table("prp_messages")
                    .select("content, role")
                    .eq("session_id", session_id)
                    .order("created_at", desc=True)
                    .limit(min(k * 2, 20))
                    .execute()
                )
            except Exception as e:  # noqa: BLE001
                logger.error(f"Recent message fetch failed: {e}")
                message_results = type("obj", (), {"data": []})()

            if getattr(message_results, "data", None):
                conv_context = []
                for msg in reversed(message_results.data):  # Chronological
                    conv_context.append(f"{msg['role'].upper()}: {msg['content']}")
                if conv_context:
                    context_parts.append("=== Recent Conversation (Latest) ===\n" + "\n".join(conv_context))

            # Combine context
            full_context = "\n\n".join(context_parts)

            # Truncate if too long
            if len(full_context) > self.max_context_chars:
                full_context = full_context[: self.max_context_chars] + "\n\n[Context truncated...]"

            return {"context": full_context, "sources": sources}

        except Exception as e:
            logger.error(f"RAG retrieval failed: {e}")
            return {"context": "", "sources": []}

    async def store_message(
        self, session_id: str, role: str, content: str, agent_type: str | None = None
    ) -> dict[str, Any] | None:
        """
        Store a chat message with embedding.

        Args:
            session_id: Chat session ID
            role: Message role (user, assistant, system)
            content: Message content
            agent_type: Optional agent type identifier

        Returns:
            Stored message data or None if failed
        """
        try:
            # Create embedding
            embedding = await self.create_embedding(content)
            if not embedding:
                logger.warning("Storing message without embedding")

            # Store in database
            data = {
                "session_id": session_id,
                "role": role,
                "content": content,
                "agent_type": agent_type,
                "embedding": embedding,
            }

            result = self.supabase.table("prp_messages").insert(data).execute()
            return result.data[0] if result.data else None

        except Exception as e:
            logger.error(f"Failed to store message: {e}")
            return None

    async def upsert_prp_doc(self, kind: str, path: str, content: str, title: str | None = None) -> dict[str, Any] | None:
        """
        Insert or update a PRP document with embedding.

        Args:
            kind: Document kind ('prp', 'doc', 'persona')
            path: File path
            content: Document content
            title: Optional title

        Returns:
            Stored document data or None if failed
        """
        try:
            # Create embedding
            embedding = await self.create_embedding(content)
            if not embedding:
                logger.error("Cannot store PRP doc without embedding")
                return None

            # Upsert in database
            data = {"kind": kind, "path": path, "content": content, "title": title, "embedding": embedding}

            result = self.supabase.table("prp_docs").upsert(data, on_conflict="kind,path").execute()
            return result.data[0] if result.data else None

        except Exception as e:
            logger.error(f"Failed to upsert PRP doc: {e}")
            return None

    async def get_persona(self, persona_name: str) -> dict[str, Any] | None:
        """
        Get persona configuration by name.

        Args:
            persona_name: Name of persona

        Returns:
            Persona data or None if not found
        """
        try:
            result = (
                self.supabase.table("prp_personas")
                .select("*")
                .eq("name", persona_name)
                .eq("is_active", True)
                .single()
                .execute()
            )
            return result.data if result.data else None
        except Exception as e:
            logger.error(f"Failed to get persona: {e}")
            return None

    async def list_personas(self, active_only: bool = True) -> list[dict[str, Any]]:
        """
        List all personas.

        Args:
            active_only: Only return active personas

        Returns:
            List of persona data
        """
        try:
            query = self.supabase.table("prp_personas").select("*")
            if active_only:
                query = query.eq("is_active", True)

            result = query.execute()
            return result.data or []
        except Exception as e:
            logger.error(f"Failed to list personas: {e}")
            return []
