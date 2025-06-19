import aiohttp
import asyncio
from typing import AsyncIterator, Any
from types import TracebackType

from livekit.agents.llm import LLM, ChatContext, ChatChunk, LLMStream, ToolChoice
from livekit.agents.llm.tool_context import FunctionTool
from livekit.agents.types import DEFAULT_API_CONNECT_OPTIONS, APIConnectOptions, NOT_GIVEN, NotGivenOr


class GuardrailsLLM(LLM):
    def __init__(self, llm: LLM):
        super().__init__()
        self.llm = llm
        self._validation_cache = {}  # Simple cache to avoid repeated API calls
        self._cache_max_size = 100

    def chat(
        self,
        *,
        chat_ctx: ChatContext,
        tools: list[FunctionTool] | None = None,
        conn_options: APIConnectOptions = DEFAULT_API_CONNECT_OPTIONS,
        parallel_tool_calls: NotGivenOr[bool] = NOT_GIVEN,
        tool_choice: NotGivenOr[ToolChoice] = NOT_GIVEN,
        extra_kwargs: NotGivenOr[dict[str, Any]] = NOT_GIVEN,
        **kwargs
    ) -> LLMStream:
        """Override the chat method to add guardrails validation"""
        
        # Get the last user message for validation
        last_user_message = self._get_last_user_message(chat_ctx)

        # Create the underlying stream first
        underlying_stream = self.llm.chat(
            chat_ctx=chat_ctx,
            tools=tools,
            conn_options=conn_options,
            parallel_tool_calls=parallel_tool_calls,
            tool_choice=tool_choice,
            extra_kwargs=extra_kwargs,
            **kwargs
        )

        # Return our wrapped stream that will handle validation
        return GuardrailsValidationStream(
            underlying_stream=underlying_stream,
            validation_func=self._is_valid,
            last_user_message=last_user_message
        )

    def _get_last_user_message(self, chat_ctx: ChatContext) -> str | None:
        """Get the last user message from ChatContext, handling different API versions"""
        try:
            # Try the newer v1.0+ API with items
            if hasattr(chat_ctx, 'items'):
                for item in reversed(chat_ctx.items):
                    if hasattr(item, 'role') and item.role == "user":
                        # Handle both ChatMessage and other item types
                        if hasattr(item, 'content'):
                            if isinstance(item.content, list):
                                # Extract text from content list
                                text_content = ""
                                for content_item in item.content:
                                    if hasattr(content_item, 'text'):
                                        text_content += content_item.text
                                    elif isinstance(content_item, str):
                                        text_content += content_item
                                return text_content if text_content else None
                            elif isinstance(item.content, str):
                                return item.content
                        elif hasattr(item, 'text'):
                            return item.text
                return None
            
            # Fallback to older API with messages
            elif hasattr(chat_ctx, 'messages'):
                for message in reversed(chat_ctx.messages):
                    if hasattr(message, 'role') and message.role == "user":
                        if hasattr(message, 'content'):
                            if isinstance(message.content, list):
                                # Extract text from content list
                                text_content = ""
                                for content_item in message.content:
                                    if hasattr(content_item, 'text'):
                                        text_content += content_item.text
                                    elif isinstance(content_item, str):
                                        text_content += content_item
                                return text_content if text_content else None
                            elif isinstance(message.content, str):
                                return message.content
                        elif hasattr(message, 'text'):
                            return message.text
                return None
                
        except Exception as e:
            print(f"[Guardrails] Error extracting user message: {e}")
            return None
        
        return None

    async def __aenter__(self):
        """Required for async context manager support"""
        await self.llm.__aenter__()
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc: BaseException | None,
        exc_tb: TracebackType | None,
    ):
        """Required for async context manager support"""
        return await self.llm.__aexit__(exc_type, exc, exc_tb)

    async def aclose(self):
        """Required cleanup method"""
        await self.llm.aclose()

    async def _is_valid(self, user_input: str) -> bool:
        """Validate user input against guardrails API with caching"""
        # Simple cache key (hash of input)
        cache_key = hash(user_input.lower().strip())
        
        # Check cache first
        if cache_key in self._validation_cache:
            print(f"[Guardrails] Using cached validation result")
            return self._validation_cache[cache_key]
        
        try:
            timeout = aiohttp.ClientTimeout(total=3)  # Shorter timeout
            async with aiohttp.ClientSession(timeout=timeout) as session:
                async with session.post(
                    "http://sbi.vaaniresearch.com:8000/validate_input",
                    json={"input": user_input},
                ) as resp:
                    if resp.status == 200:
                        result = await resp.json()
                        is_valid = result.get("valid", True)
                        
                        # Cache the result
                        if len(self._validation_cache) >= self._cache_max_size:
                            # Simple cache eviction - remove oldest entries
                            oldest_keys = list(self._validation_cache.keys())[:10]
                            for key in oldest_keys:
                                del self._validation_cache[key]
                        
                        self._validation_cache[cache_key] = is_valid
                        return is_valid
                    else:
                        print(f"[Guardrails] API returned status {resp.status}, allowing by default")
                        return True
        except asyncio.CancelledError:
            print(f"[Guardrails] Validation cancelled, allowing by default")
            return True  # Allow if cancelled
        except asyncio.TimeoutError:
            print(f"[Guardrails] Validation timeout, allowing by default")
            return True  # Allow on timeout
        except Exception as e:
            print(f"[Guardrails] Validation error: {e}, allowing by default")
            return True  # Default to allowing if validation fails


class GuardrailsValidationStream(LLMStream):
    def __init__(self, underlying_stream: LLMStream, validation_func, last_user_message: str = None):
        # Get required parameters from the underlying stream
        chat_ctx = underlying_stream._chat_ctx
        tools = getattr(underlying_stream, '_tools', [])
        conn_options = getattr(underlying_stream, '_conn_options', DEFAULT_API_CONNECT_OPTIONS)
        
        # Initialize the base LLMStream properly
        super().__init__(
            underlying_stream._llm,
            chat_ctx=chat_ctx,
            tools=tools,
            conn_options=conn_options
        )
        
        self._underlying_stream = underlying_stream
        self._validation_func = validation_func
        self._last_user_message = last_user_message
        self._validation_complete = False
        self._is_blocked = False

    async def _run(self):
        """Override _run to perform validation before forwarding to underlying stream"""
        try:
            # Perform validation if we have a user message
            if self._last_user_message:
                is_valid = await self._validation_func(self._last_user_message)
                if not is_valid:
                    print(f"[Guardrails] Blocked message: {self._last_user_message[:50]}...")
                    
                    # Send blocked response as a proper chat chunk
                    blocked_chunk = ChatChunk(
                        request_id="guardrails_blocked",
                        choices=[{
                            "delta": {
                                "role": "assistant",
                                "content": "Sorry, I can't respond to that."
                            }
                        }]
                    )
                    self._event_ch.send_nowait(blocked_chunk)
                    
                    # Send a final chunk to properly close the stream
                    final_chunk = ChatChunk(
                        request_id="guardrails_blocked_final",
                        choices=[{
                            "delta": {
                                "role": "assistant",
                                "content": ""
                            }
                        }]
                    )
                    self._event_ch.send_nowait(final_chunk)
                    return

            # If validation passed, forward to underlying stream
            async for chunk in self._underlying_stream:
                self._event_ch.send_nowait(chunk)
                
        except Exception as e:
            # Forward any errors
            raise e

    async def aclose(self):
        """Cleanup both streams"""
        try:
            await super().aclose()
        except Exception as e:
            # Ignore cancellation errors during cleanup
            print(f"[Guardrails] Cleanup warning: {e}")
        
        try:
            if hasattr(self._underlying_stream, 'aclose'):
                await self._underlying_stream.aclose()
        except Exception as e:
            # Ignore cancellation errors during cleanup
            print(f"[Guardrails] Underlying stream cleanup warning: {e}")