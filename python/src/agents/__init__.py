"""
Agents module for PydanticAI-powered agents in the Archon system.

This module contains various specialized agents for different tasks:
- DocumentAgent: Processes and validates project documentation
- PlanningAgent: Generates feature plans and technical specifications
- ERDAgent: Creates entity relationship diagrams
- TaskAgent: Generates and manages project tasks
- ResearcherAgent: Advanced research and analysis with RAG, web search, and knowledge graphs

All agents are built using PydanticAI for type safety and structured outputs.
"""

from .base_agent import BaseAgent
from .document_agent import DocumentAgent
from .spanish_tutor_agent import SpanishTutorAgent
from .researcher_agent import ResearcherAgent

__all__ = ["BaseAgent", "DocumentAgent", "SpanishTutorAgent", "ResearcherAgent"]
