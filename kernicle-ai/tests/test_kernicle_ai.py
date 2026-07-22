"""Tests for kernicle-ai plugin."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
import asyncio


class TestKnowledgeBase:
    """Tests for the built-in knowledge base."""
    
    def test_import(self):
        """Test that knowledge module can be imported."""
        from kernicle_ai.knowledge import KnowledgeBase, KnowledgeEntry, get_knowledge_base
    
    def test_knowledge_base_singleton(self):
        """Test knowledge base singleton pattern."""
        from kernicle_ai.knowledge import get_knowledge_base
        
        kb1 = get_knowledge_base()
        kb2 = get_knowledge_base()
        assert kb1 is kb2
    
    def test_knowledge_base_has_entries(self):
        """Test that knowledge base has entries."""
        from kernicle_ai.knowledge import get_knowledge_base
        
        kb = get_knowledge_base()
        assert len(kb.entries) > 0
    
    def test_search_oom(self):
        """Test searching for OOM errors."""
        from kernicle_ai.knowledge import get_knowledge_base
        
        kb = get_knowledge_base()
        results = kb.search("Out of memory: Killed process 1234")
        
        assert len(results) > 0
        assert any("OOM" in entry.title or "Memory" in entry.title for entry in results)
    
    def test_search_kernel_panic(self):
        """Test searching for kernel panic."""
        from kernicle_ai.knowledge import get_knowledge_base
        
        kb = get_knowledge_base()
        results = kb.search("Kernel panic - not syncing: VFS: Unable to mount root fs")
        
        assert len(results) > 0
        assert any("panic" in entry.title.lower() for entry in results)
    
    def test_search_io_error(self):
        """Test searching for I/O errors."""
        from kernicle_ai.knowledge import get_knowledge_base
        
        kb = get_knowledge_base()
        results = kb.search("Buffer I/O error on dev sda1, sector 12345")
        
        assert len(results) > 0
        assert any("I/O" in entry.title or "Disk" in entry.title for entry in results)
    
    def test_search_no_results(self):
        """Test search with no matching entries."""
        from kernicle_ai.knowledge import get_knowledge_base
        
        kb = get_knowledge_base()
        results = kb.search("completely normal log message with no errors")
        
        # May still match some keywords, but score should be low
        assert isinstance(results, list)
    
    def test_format_entry(self):
        """Test formatting a single entry."""
        from kernicle_ai.knowledge import get_knowledge_base
        
        kb = get_knowledge_base()
        entry = kb.entries[0]
        
        formatted = kb.format_entry(entry)
        
        assert entry.title in formatted
        assert entry.description in formatted
        assert "Possible Causes" in formatted
        assert "Recommended Solutions" in formatted
    
    def test_format_results(self):
        """Test formatting multiple results."""
        from kernicle_ai.knowledge import get_knowledge_base
        
        kb = get_knowledge_base()
        results = kb.search("kernel panic")
        
        formatted = kb.format_results(results)
        
        assert isinstance(formatted, str)
        if results:
            assert results[0].title in formatted
    
    def test_get_critical_entries(self):
        """Test getting critical severity entries."""
        from kernicle_ai.knowledge import get_knowledge_base
        
        kb = get_knowledge_base()
        critical = kb.get_critical()
        
        assert len(critical) > 0
        assert all(e.severity == "critical" for e in critical)


class TestProviders:
    """Tests for LLM providers."""
    
    def test_groq_import(self):
        """Test Groq provider import."""
        from kernicle_ai.providers import GroqProvider
    
    def test_gemini_import(self):
        """Test Gemini provider import."""
        from kernicle_ai.providers import GeminiProvider
    
    def test_groq_has_is_available(self):
        """Test Groq has is_available method."""
        from kernicle_ai.providers import GroqProvider
        
        provider = GroqProvider()
        assert hasattr(provider, 'is_available')
    
    def test_gemini_has_is_available(self):
        """Test Gemini has is_available method."""
        from kernicle_ai.providers import GeminiProvider
        
        provider = GeminiProvider()
        assert hasattr(provider, 'is_available')
    
    def test_groq_has_generate(self):
        """Test Groq has generate method."""
        from kernicle_ai.providers import GroqProvider
        
        provider = GroqProvider()
        assert hasattr(provider, 'generate')
    
    def test_gemini_has_generate(self):
        """Test Gemini has generate method."""
        from kernicle_ai.providers import GeminiProvider
        
        provider = GeminiProvider()
        assert hasattr(provider, 'generate')
    
    def test_llm_response_dataclass(self):
        """Test LLMResponse dataclass."""
        from kernicle_ai.providers import LLMResponse
        
        response = LLMResponse(
            content="Test content",
            provider="test",
            model="test-model",
            success=True
        )
        
        assert response.success is True
        assert response.content == "Test content"
        assert response.model == "test-model"


class TestSearch:
    """Tests for DuckDuckGo search."""
    
    def test_search_import(self):
        """Test search module import."""
        from kernicle_ai.search import DuckDuckGoSearch, SearchResult
    
    def test_search_result_dataclass(self):
        """Test SearchResult dataclass."""
        from kernicle_ai.search import SearchResult
        
        result = SearchResult(
            title="Test Title",
            url="https://example.com",
            snippet="Test snippet"
        )
        
        assert result.title == "Test Title"
        assert result.url == "https://example.com"
        assert result.snippet == "Test snippet"
    
    def test_format_search_results_empty(self):
        """Test formatting empty results."""
        from kernicle_ai.search import format_search_results
        
        formatted = format_search_results([])
        assert "No relevant resources found" in formatted
    
    def test_format_search_results(self):
        """Test formatting search results."""
        from kernicle_ai.search import format_search_results, SearchResult
        
        results = [
            SearchResult(
                title="Linux Kernel OOM Guide",
                url="https://example.com/oom",
                snippet="How to handle OOM killer"
            )
        ]
        
        formatted = format_search_results(results)
        
        assert "Linux Kernel OOM Guide" in formatted
        assert "https://example.com/oom" in formatted
        assert "Related Resources" in formatted


class TestAnalyzer:
    """Tests for the main analyzer."""
    
    def test_analyzer_import(self):
        """Test analyzer import."""
        from kernicle_ai.analyzer import LogAnalyzer, AnalysisResult
    
    def test_analysis_result_dataclass(self):
        """Test AnalysisResult dataclass."""
        from kernicle_ai.analyzer import AnalysisResult
        
        result = AnalysisResult()
        
        assert result.summary == ""
        assert result.solutions == []
        assert result.severity == "unknown"
        assert result.used_llm is False
        assert result.used_knowledge_base is False
    
    def test_analyzer_initialization(self):
        """Test analyzer initialization."""
        from kernicle_ai.analyzer import LogAnalyzer
        
        analyzer = LogAnalyzer()
        
        assert analyzer.groq is not None
        assert analyzer.gemini is not None
        assert analyzer.knowledge_base is not None
        assert analyzer.web_search is not None
    
    def test_analyzer_without_web_search(self):
        """Test analyzer without web search."""
        from kernicle_ai.analyzer import LogAnalyzer
        
        analyzer = LogAnalyzer(enable_web_search=False)
        
        assert analyzer.web_search is None
    
    def test_analyzer_without_knowledge_base(self):
        """Test analyzer without knowledge base."""
        from kernicle_ai.analyzer import LogAnalyzer
        
        analyzer = LogAnalyzer(enable_knowledge_base=False)
        
        assert analyzer.knowledge_base is None
    
    @pytest.mark.asyncio
    async def test_analyze_with_knowledge_base_only(self):
        """Test analysis using only knowledge base."""
        from kernicle_ai.analyzer import LogAnalyzer
        
        # Create analyzer without web search (to speed up test)
        analyzer = LogAnalyzer(enable_web_search=False)
        
        log_content = "Out of memory: Killed process 1234 (mysqld)"
        
        result = await analyzer.analyze(log_content)
        
        # Should get results from knowledge base at minimum
        assert result.used_knowledge_base is True
        assert len(result.kb_matches) > 0
    
    def test_format_result(self):
        """Test formatting analysis result."""
        from kernicle_ai.analyzer import LogAnalyzer, AnalysisResult
        from kernicle_ai.knowledge import get_knowledge_base
        
        analyzer = LogAnalyzer()
        kb = get_knowledge_base()
        
        result = AnalysisResult(
            summary="Test summary",
            root_cause="Test root cause",
            solutions=["Solution 1", "Solution 2"],
            severity="warning",
            used_knowledge_base=True,
            kb_matches=kb.entries[:1]
        )
        
        formatted = analyzer.format_result(result)
        
        assert "AI-Powered Verdict" in formatted
        assert "Test summary" in formatted
        assert "WARNING" in formatted
        assert "Solution 1" in formatted
        assert "What Happened" in formatted
        assert "How It Happened" in formatted
        assert "How to Solve It" in formatted


class TestPlugin:
    """Tests for the plugin integration."""
    
    def test_plugin_import(self):
        """Test plugin import."""
        from kernicle_ai.plugin import AIPlugin, get_plugin
    
    def test_plugin_creation(self):
        """Test plugin creation."""
        from kernicle_ai.plugin import AIPlugin
        
        plugin = AIPlugin()
        
        assert plugin.name == "kernicle-ai"
        assert plugin.version == "0.1.0"
    
    def test_plugin_is_available(self):
        """Test plugin availability check."""
        from kernicle_ai.plugin import AIPlugin
        
        plugin = AIPlugin()
        
        # Always available because knowledge base is always available
        assert plugin.is_available() is True
    
    def test_plugin_status(self):
        """Test plugin status."""
        from kernicle_ai.plugin import AIPlugin
        
        plugin = AIPlugin()
        status = plugin.get_status()
        
        assert "name" in status
        assert "version" in status
        assert "available" in status
        assert "providers" in status
        assert "knowledge_base" in status["providers"]
    
    def test_get_plugin(self):
        """Test get_plugin function."""
        from kernicle_ai.plugin import get_plugin
        
        plugin = get_plugin()
        
        assert plugin is not None
        assert plugin.name == "kernicle-ai"
    
    def test_is_plugin_available(self):
        """Test is_plugin_available function."""
        from kernicle_ai.plugin import is_plugin_available
        
        # Should always be True because KB is always available
        assert is_plugin_available() is True


class TestIntegration:
    """Integration tests."""
    
    @pytest.mark.asyncio
    async def test_full_analysis_flow(self):
        """Test the full analysis flow."""
        from kernicle_ai import AIPlugin
        
        plugin = AIPlugin()
        
        log_content = """
        Jan 15 10:30:45 server1 kernel: Out of memory: Killed process 1234 (mysqld)
        Jan 15 10:30:45 server1 kernel: oom-killer: constraint=CONSTRAINT_NONE
        Jan 15 10:30:46 server1 systemd: mysqld.service: Main process exited, code=killed
        """
        
        result = await plugin.analyze(log_content)
        
        # Should get results from knowledge base at minimum
        assert result.used_knowledge_base is True
        assert len(result.kb_matches) > 0
        assert result.analysis_time_ms >= 0
    
    def test_sync_analysis(self):
        """Test synchronous analysis wrapper."""
        from kernicle_ai import AIPlugin
        
        plugin = AIPlugin()
        
        log_content = "Kernel panic - not syncing: Fatal exception"
        
        result = plugin.analyze_sync(log_content)
        
        assert result is not None
        assert result.used_knowledge_base is True
    
    def test_enhance_export_data(self):
        """Test enhancing export data."""
        from kernicle_ai import AIPlugin
        
        plugin = AIPlugin()
        
        export_data = {
            "session_id": "test-session",
            "findings": []
        }
        
        log_content = "Buffer I/O error on dev sda1"
        
        enhanced = plugin.enhance_export_data(export_data, log_content)
        
        assert "ai_analysis" in enhanced
        assert "summary" in enhanced["ai_analysis"]
        assert "sources" in enhanced["ai_analysis"]
    
    def test_html_section_generation(self):
        """Test HTML section generation."""
        from kernicle_ai import AIPlugin
        
        plugin = AIPlugin()
        
        # Run analysis first
        log_content = "segfault at 0000000000000000 ip 00007f"
        result = plugin.analyze_sync(log_content)
        
        html_section = plugin.get_html_section(result)
        
        assert "ai-analysis" in html_section
        assert "AI Analysis" in html_section
