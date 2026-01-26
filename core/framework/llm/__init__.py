"""LLM provider abstraction."""

from framework.llm.provider import LLMProvider, LLMResponse

__all__ = ["LLMProvider", "LLMResponse"]

try:
    import importlib.util
    if importlib.util.find_spec("framework.llm.anthropic") is not None:
        from framework.llm.anthropic import AnthropicProvider  # noqa: F401
        __all__.append("AnthropicProvider")
except ImportError:
    pass

try:
    import importlib.util
    if importlib.util.find_spec("framework.llm.litellm") is not None:
        from framework.llm.litellm import LiteLLMProvider  # noqa: F401
        __all__.append("LiteLLMProvider")
except ImportError:
    pass
