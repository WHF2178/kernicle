"""Kernicle AI Plugin - AI-powered log analysis.

This plugin provides AI-powered diagnostics for Kernicle crash reports.
When installed, it automatically enhances export reports with:

- LLM-powered analysis (Groq primary, Gemini fallback)
- Built-in knowledge base for common Linux errors
- DuckDuckGo web search for related resources

Usage:
    1. Install: pip install kernicle-ai
    2. Set API key: export GROQ_API_KEY=your_key (or GEMINI_API_KEY)
    3. Run kernicle export - AI analysis is automatic!

No --ai flag needed. When this plugin is installed, AI analysis
is automatically included in all exports.

API Keys (FREE):
    - Groq: https://console.groq.com (14,400 tokens/min free)
    - Gemini: https://aistudio.google.com/app/apikey (60 req/min free)
"""

__version__ = "0.1.0"

from .plugin import AIPlugin, get_plugin, is_plugin_available
from .analyzer import LogAnalyzer, AnalysisResult, analyze_logs
from .knowledge import KnowledgeBase, KnowledgeEntry, get_knowledge_base
from .search import DuckDuckGoSearch, SearchResult, search_for_error
from .providers import GroqProvider, GeminiProvider, LLMResponse

__all__ = [
    # Plugin
    "AIPlugin",
    "get_plugin",
    "is_plugin_available",
    # Analyzer
    "LogAnalyzer",
    "AnalysisResult",
    "analyze_logs",
    # Knowledge Base
    "KnowledgeBase",
    "KnowledgeEntry",
    "get_knowledge_base",
    # Search
    "DuckDuckGoSearch",
    "SearchResult",
    "search_for_error",
    # Providers
    "GroqProvider",
    "GeminiProvider",
    "LLMResponse",
]
