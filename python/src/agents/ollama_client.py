"""
Ollama Client - Integration for local LLM calls via Ollama.

Provides a simple interface for:
- Text generation
- JSON-structured output
- Batch processing
- Model listing and management
"""

import asyncio
import json
import logging
from typing import Any

import httpx
from pydantic import BaseModel

logger = logging.getLogger(__name__)


class OllamaGenerateRequest(BaseModel):
    """Request for Ollama text generation."""

    model: str
    prompt: str
    system: str | None = None
    format: str | None = None  # "json" for structured output
    stream: bool = False
    options: dict[str, Any] | None = None


class OllamaGenerateResponse(BaseModel):
    """Response from Ollama generation."""

    model: str
    response: str
    done: bool
    context: list[int] | None = None
    total_duration: int | None = None
    load_duration: int | None = None
    prompt_eval_count: int | None = None
    eval_count: int | None = None


class OllamaModel(BaseModel):
    """Model information from Ollama."""

    name: str
    size: int
    digest: str
    modified_at: str


class OllamaClient:
    """
    Client for interacting with Ollama API.

    Usage:
        client = OllamaClient(base_url="http://localhost:11434")
        response = await client.generate(model="llama3.1", prompt="Hello!")
        models = await client.list_models()
    """

    def __init__(self, base_url: str = "http://localhost:11434", timeout: float = 120.0):
        """
        Initialize Ollama client.

        Args:
            base_url: Base URL for Ollama API
            timeout: Request timeout in seconds
        """
        self.base_url = base_url.rstrip("/")
        self.timeout = timeout
        self.client = httpx.AsyncClient(timeout=timeout)

    async def __aenter__(self):
        """Async context manager entry."""
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        await self.close()

    async def close(self):
        """Close the HTTP client."""
        await self.client.aclose()

    async def health_check(self) -> bool:
        """
        Check if Ollama is running and accessible.

        Returns:
            True if healthy, False otherwise
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except Exception as e:
            logger.warning(f"Ollama health check failed: {e}")
            return False

    async def list_models(self) -> list[OllamaModel]:
        """
        List available models in Ollama.

        Returns:
            List of OllamaModel objects
        """
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            response.raise_for_status()
            data = response.json()
            return [OllamaModel(**model) for model in data.get("models", [])]
        except Exception as e:
            logger.error(f"Failed to list Ollama models: {e}")
            return []

    async def generate(
        self,
        model: str,
        prompt: str,
        system: str | None = None,
        json_schema: type[BaseModel] | None = None,
        options: dict[str, Any] | None = None,
    ) -> str | dict[str, Any]:
        """
        Generate text using Ollama model.

        Args:
            model: Model name (e.g., "llama3.1", "qwen2.5:3b")
            prompt: User prompt
            system: Optional system prompt
            json_schema: Optional Pydantic model for JSON output
            options: Optional model parameters (temperature, top_p, etc.)

        Returns:
            Generated text or parsed JSON dict if json_schema provided
        """
        request_data = {
            "model": model,
            "prompt": prompt,
            "stream": False,
        }

        if system:
            request_data["system"] = system

        if json_schema:
            request_data["format"] = "json"

        if options:
            request_data["options"] = options

        try:
            response = await self.client.post(f"{self.base_url}/api/generate", json=request_data)
            response.raise_for_status()
            result = response.json()
            output = result.get("response", "")

            if json_schema:
                try:
                    parsed = json.loads(output)
                    # Validate against schema
                    validated = json_schema(**parsed)
                    return validated.model_dump()
                except json.JSONDecodeError as e:
                    logger.error(f"Failed to parse JSON from Ollama: {e}")
                    return {}
                except Exception as e:
                    logger.error(f"Failed to validate JSON against schema: {e}")
                    return {}

            return output

        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama API error: {e}")
            raise Exception(f"Ollama generation failed: {e}")
        except Exception as e:
            logger.error(f"Ollama generation error: {e}")
            raise

    async def batch_generate(
        self,
        model: str,
        prompts: list[str],
        system: str | None = None,
        max_concurrent: int = 5,
        progress_callback: Any | None = None,
    ) -> list[str]:
        """
        Generate text for multiple prompts in parallel.

        Args:
            model: Model name
            prompts: List of prompts to process
            system: Optional system prompt
            max_concurrent: Maximum concurrent requests
            progress_callback: Optional callback for progress updates

        Returns:
            List of generated responses in same order as prompts
        """
        semaphore = asyncio.Semaphore(max_concurrent)
        results = [None] * len(prompts)

        async def process_prompt(idx: int, prompt: str):
            async with semaphore:
                try:
                    result = await self.generate(model=model, prompt=prompt, system=system)
                    results[idx] = result

                    if progress_callback:
                        await progress_callback(
                            {"step": "ollama_batch", "progress": idx + 1, "total": len(prompts), "log": f"Processed {idx + 1}/{len(prompts)}"}
                        )

                except Exception as e:
                    logger.error(f"Failed to process prompt {idx}: {e}")
                    results[idx] = f"ERROR: {str(e)}"

        tasks = [process_prompt(i, prompt) for i, prompt in enumerate(prompts)]
        await asyncio.gather(*tasks)

        return results

    async def pull_model(self, model: str) -> bool:
        """
        Pull a model from Ollama registry.

        Args:
            model: Model name to pull

        Returns:
            True if successful, False otherwise
        """
        try:
            response = await self.client.post(f"{self.base_url}/api/pull", json={"name": model, "stream": False})
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to pull Ollama model {model}: {e}")
            return False


# Helper function for quick generation
async def ollama_generate(
    prompt: str,
    model: str = "llama3.1",
    system: str | None = None,
    base_url: str = "http://localhost:11434",
) -> str:
    """
    Quick helper for single Ollama generation.

    Args:
        prompt: User prompt
        model: Model name
        system: Optional system prompt
        base_url: Ollama API base URL

    Returns:
        Generated text
    """
    async with OllamaClient(base_url=base_url) as client:
        return await client.generate(model=model, prompt=prompt, system=system)
