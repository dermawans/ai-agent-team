"""
LLM Client — Configurable wrapper supporting Gemini, OpenAI, and Ollama.
Includes rate limiting, retry logic, and token tracking.
"""

import asyncio
import json
import time
import logging
from typing import Optional
from config import config

logger = logging.getLogger(__name__)


class LLMResponse:
    """Standardized response from any LLM provider."""

    def __init__(self, content: str, tool_calls: list = None,
                 input_tokens: int = 0, output_tokens: int = 0,
                 model: str = "", provider: str = ""):
        self.content = content
        self.tool_calls = tool_calls or []
        self.input_tokens = input_tokens
        self.output_tokens = output_tokens
        self.total_tokens = input_tokens + output_tokens
        self.model = model
        self.provider = provider


class RateLimiter:
    """Simple token-bucket rate limiter."""

    def __init__(self, max_rpm: int):
        self.max_rpm = max_rpm
        self.timestamps: list[float] = []

    async def wait_if_needed(self):
        """Block until we're under the rate limit."""
        now = time.time()
        # Remove timestamps older than 60 seconds
        self.timestamps = [t for t in self.timestamps if now - t < 60]

        if len(self.timestamps) >= self.max_rpm:
            wait_time = 60 - (now - self.timestamps[0]) + 0.5
            if wait_time > 0:
                logger.info(f"Rate limit reached. Waiting {wait_time:.1f}s...")
                await asyncio.sleep(wait_time)

        self.timestamps.append(time.time())


class LLMClient:
    """
    Configurable LLM client supporting multiple providers.

    Providers:
    - gemini: Google Gemini API (default, free tier)
    - openai: OpenAI API
    - ollama: Local Ollama instance
    """

    def __init__(self, provider: str = None, model: str = None):
        self.provider = provider or config.LLM.PROVIDER
        self.model = model or self._get_default_model()
        self.rate_limiter = RateLimiter(config.LLM.MAX_RPM)
        self._client = None
        self._total_tokens = 0
        self._total_calls = 0

    def _get_default_model(self) -> str:
        if self.provider == "gemini":
            return config.LLM.GEMINI_MODEL
        elif self.provider == "openai":
            return config.LLM.OPENAI_MODEL
        elif self.provider == "ollama":
            return config.LLM.OLLAMA_MODEL
        return "gemini-2.0-flash"

    async def _init_gemini(self):
        """Initialize Google Gemini client."""
        from google import genai
        self._client = genai.Client(api_key=config.LLM.GEMINI_API_KEY)

    async def _init_openai(self):
        """Initialize OpenAI client."""
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(api_key=config.LLM.OPENAI_API_KEY)

    async def _init_ollama(self):
        """Initialize Ollama client (uses OpenAI-compatible API)."""
        from openai import AsyncOpenAI
        self._client = AsyncOpenAI(
            base_url=f"{config.LLM.OLLAMA_BASE_URL}/v1",
            api_key="ollama"  # Ollama doesn't need a real key
        )

    async def _ensure_client(self):
        """Lazy-initialize the LLM client."""
        if self._client is None:
            if self.provider == "gemini":
                await self._init_gemini()
            elif self.provider == "openai":
                await self._init_openai()
            elif self.provider == "ollama":
                await self._init_ollama()
            else:
                raise ValueError(f"Unknown LLM provider: {self.provider}")

    async def chat(
        self,
        system_prompt: str,
        messages: list[dict],
        tools: list[dict] = None,
        temperature: float = 0.7,
        max_tokens: int = 8192,
    ) -> LLMResponse:
        """
        Send a chat completion request to the configured LLM provider.

        Args:
            system_prompt: System instruction for the agent's role
            messages: List of {"role": "user"|"assistant", "content": "..."} dicts
            tools: Optional tool/function definitions for function calling
            temperature: Creativity level (0.0-1.0)
            max_tokens: Maximum response tokens

        Returns:
            LLMResponse with content and optional tool calls
        """
        await self._ensure_client()
        await self.rate_limiter.wait_if_needed()

        max_retries = max(config.LLM.MAX_RETRIES, 5)  # At least 5 retries for rate limits

        for attempt in range(max_retries + 1):
            try:
                if self.provider == "gemini":
                    return await self._chat_gemini(system_prompt, messages, tools, temperature, max_tokens)
                else:
                    return await self._chat_openai_compatible(system_prompt, messages, tools, temperature, max_tokens)
            except Exception as e:
                error_str = str(e)
                is_rate_limit = "429" in error_str or "RESOURCE_EXHAUSTED" in error_str or "quota" in error_str.lower()

                if attempt < max_retries:
                    if is_rate_limit:
                        # Parse retry delay from error message if available
                        wait = self._parse_retry_delay(error_str)
                        if wait <= 0:
                            wait = min(30 * (attempt + 1), 120)  # 30s, 60s, 90s, max 120s
                        logger.warning(f"Rate limit hit (attempt {attempt + 1}). Waiting {wait:.0f}s...")
                    else:
                        wait = config.LLM.RETRY_DELAY * (2 ** attempt)
                        logger.warning(f"LLM call failed (attempt {attempt + 1}): {e}. Retrying in {wait}s...")

                    await asyncio.sleep(wait)
                else:
                    logger.error(f"LLM call failed after {max_retries + 1} attempts: {e}")
                    raise

    def _parse_retry_delay(self, error_str: str) -> float:
        """Extract retry delay from Gemini error message."""
        import re
        # Look for "retry in Xs" or "retryDelay': 'Xs'"
        patterns = [
            r"retry in (\d+\.?\d*)s",
            r"retryDelay.*?(\d+)s",
        ]
        for pattern in patterns:
            match = re.search(pattern, error_str, re.IGNORECASE)
            if match:
                delay = float(match.group(1))
                return delay + 5  # Add 5s buffer
        return -1  # Not found

    async def _chat_gemini(self, system_prompt, messages, tools, temperature, max_tokens) -> LLMResponse:
        """Chat using Google Gemini API."""
        # Build contents for Gemini
        contents = []
        for msg in messages:
            role = "user" if msg["role"] == "user" else "model"
            contents.append({"role": role, "parts": [{"text": msg["content"]}]})

        # Build config — new google-genai SDK uses flat config fields
        from google.genai import types

        # Build tool declarations if provided
        gemini_tools = None
        if tools:
            gemini_tools = self._convert_tools_to_gemini(tools)

        gen_config = types.GenerateContentConfig(
            system_instruction=system_prompt,
            temperature=temperature,
            max_output_tokens=max_tokens,
            tools=gemini_tools,
            thinking_config=types.ThinkingConfig(thinking_budget=0),  # Disable thinking for faster/cleaner output
        )

        response = await asyncio.to_thread(
            self._client.models.generate_content,
            model=self.model,
            contents=contents,
            config=gen_config,
        )

        # Extract response — handle Gemini 2.5's thinking parts
        content = ""
        tool_calls = []

        # Try response.text first (simplest path)
        try:
            if response.text:
                content = response.text
        except (ValueError, AttributeError):
            pass

        # Fallback: manually extract from parts
        if not content and response.candidates and response.candidates[0].content:
            parts = response.candidates[0].content.parts or []
            for part in parts:
                # Skip 'thought' parts (Gemini 2.5 thinking)
                if hasattr(part, "thought") and part.thought:
                    continue
                if hasattr(part, "text") and part.text:
                    content += part.text
                if hasattr(part, "function_call") and part.function_call:
                    tool_calls.append({
                        "name": part.function_call.name,
                        "arguments": dict(part.function_call.args) if part.function_call.args else {}
                    })

        # Token tracking (attributes can be None even when present)
        input_tokens = (getattr(response.usage_metadata, "prompt_token_count", 0) or 0) if hasattr(response, "usage_metadata") and response.usage_metadata else 0
        output_tokens = (getattr(response.usage_metadata, "candidates_token_count", 0) or 0) if hasattr(response, "usage_metadata") and response.usage_metadata else 0

        self._total_tokens += (input_tokens or 0) + (output_tokens or 0)
        self._total_calls += 1

        logger.debug(f"LLM response: {len(content)} chars, {input_tokens}+{output_tokens} tokens")

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self.model,
            provider="gemini"
        )

    async def _chat_openai_compatible(self, system_prompt, messages, tools, temperature, max_tokens) -> LLMResponse:
        """Chat using OpenAI-compatible API (OpenAI, Ollama)."""
        # Build messages with system prompt
        api_messages = [{"role": "system", "content": system_prompt}]
        api_messages.extend(messages)

        kwargs = {
            "model": self.model,
            "messages": api_messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
        }

        if tools:
            kwargs["tools"] = self._convert_tools_to_openai(tools)

        response = await self._client.chat.completions.create(**kwargs)
        choice = response.choices[0]

        content = choice.message.content or ""
        tool_calls = []

        if choice.message.tool_calls:
            for tc in choice.message.tool_calls:
                tool_calls.append({
                    "name": tc.function.name,
                    "arguments": json.loads(tc.function.arguments) if tc.function.arguments else {}
                })

        input_tokens = response.usage.prompt_tokens if response.usage else 0
        output_tokens = response.usage.completion_tokens if response.usage else 0

        self._total_tokens += input_tokens + output_tokens
        self._total_calls += 1

        return LLMResponse(
            content=content,
            tool_calls=tool_calls,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            model=self.model,
            provider=self.provider
        )

    def _convert_tools_to_gemini(self, tools: list[dict]):
        """Convert generic tool definitions to Gemini format."""
        # For now, return tools as-is; actual conversion depends on use case
        return tools

    def _convert_tools_to_openai(self, tools: list[dict]):
        """Convert generic tool definitions to OpenAI function calling format."""
        return tools

    @property
    def total_tokens(self) -> int:
        return self._total_tokens

    @property
    def total_calls(self) -> int:
        return self._total_calls
