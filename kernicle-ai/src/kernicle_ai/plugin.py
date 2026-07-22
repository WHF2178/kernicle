"""Kernicle plugin integration.

This module provides automatic AI analysis integration with Kernicle.
When kernicle-ai is installed, it automatically enhances export reports
with AI-powered diagnostics.
"""

import asyncio
from pathlib import Path
from typing import Optional, Dict, Any

from .analyzer import LogAnalyzer, AnalysisResult


class AIPlugin:
    """Kernicle AI Plugin.
    
    This plugin automatically enhances Kernicle reports with AI analysis
    when installed. No flags needed - it just works!
    
    Usage:
        1. Install kernicle-ai: pip install kernicle-ai
        2. Set API keys: export GROQ_API_KEY=your_key
        3. Run kernicle export as normal - AI analysis is automatic!
    """
    
    name = "kernicle-ai"
    version = "0.1.0"
    description = "AI-powered log analysis for Kernicle"
    
    def __init__(self):
        """Initialize the AI plugin."""
        self.analyzer = LogAnalyzer()
        self._last_result: Optional[AnalysisResult] = None
    
    def is_available(self) -> bool:
        """Check if AI analysis is available.
        
        Returns True if at least one LLM provider is configured
        or if knowledge base is available (always true).
        """
        return (
            self.analyzer.groq.is_available() or
            self.analyzer.gemini.is_available() or
            self.analyzer.knowledge_base is not None
        )
    
    def get_status(self) -> Dict[str, Any]:
        """Get plugin status and available providers."""
        return {
            "name": self.name,
            "version": self.version,
            "available": self.is_available(),
            "providers": {
                "groq": {
                    "available": self.analyzer.groq.is_available(),
                    "model": "llama-3.1-70b-versatile"
                },
                "gemini": {
                    "available": self.analyzer.gemini.is_available(),
                    "model": "gemini-1.5-flash"
                },
                "knowledge_base": {
                    "available": self.analyzer.knowledge_base is not None,
                    "entries": len(self.analyzer.knowledge_base.entries) if self.analyzer.knowledge_base else 0
                },
                "web_search": {
                    "available": self.analyzer.web_search is not None
                }
            }
        }
    
    def analyze_sync(
        self,
        log_content: str,
        context: Optional[str] = None,
        timeout: float = 60.0
    ) -> AnalysisResult:
        """Synchronous wrapper for async analysis.
        
        Args:
            log_content: Log content to analyze
            context: Optional system context
            timeout: Timeout for LLM requests
            
        Returns:
            AnalysisResult with analysis
        """
        return asyncio.run(self.analyze(log_content, context, timeout))
    
    async def analyze(
        self,
        log_content: str,
        context: Optional[str] = None,
        timeout: float = 60.0
    ) -> AnalysisResult:
        """Analyze log content.
        
        Args:
            log_content: Log content to analyze
            context: Optional system context (e.g., system info)
            timeout: Timeout for LLM requests
            
        Returns:
            AnalysisResult with analysis
        """
        self._last_result = await self.analyzer.analyze(
            log_content, context, timeout
        )
        return self._last_result
    
    def format_analysis(self, result: Optional[AnalysisResult] = None, log_content: str = "") -> str:
        """Format analysis result as markdown.
        
        Args:
            result: Analysis result to format (uses last result if None)
            log_content: Original log content for severity explanation
            
        Returns:
            Formatted markdown string
        """
        if result is None:
            result = self._last_result
        
        if result is None:
            return "No analysis available."
        
        return self.analyzer.format_result(result, log_content)
    
    def enhance_export_data(
        self,
        export_data: Dict[str, Any],
        log_content: str,
        system_info: Optional[str] = None
    ) -> Dict[str, Any]:
        """Enhance export data with AI analysis.
        
        This method is called automatically by Kernicle during export
        when the plugin is installed.
        
        Args:
            export_data: Original export data dict
            log_content: Log content to analyze
            system_info: Optional system info string
            
        Returns:
            Enhanced export data with AI analysis section
        """
        # Run analysis
        result = self.analyze_sync(log_content, system_info)
        
        # Add AI section to export data
        export_data["ai_analysis"] = {
            "summary": result.summary,
            "root_cause": result.root_cause,
            "solutions": result.solutions,
            "severity": result.severity,
            "llm_provider": result.llm_provider if result.used_llm else None,
            "analysis_time_ms": result.analysis_time_ms,
            "sources": {
                "llm": result.used_llm,
                "knowledge_base": result.used_knowledge_base,
                "web_search": result.used_web_search
            },
            "knowledge_base_matches": [
                {
                    "title": entry.title,
                    "severity": entry.severity,
                    "description": entry.description
                }
                for entry in result.kb_matches
            ],
            "web_resources": [
                {
                    "title": r.title,
                    "url": r.url
                }
                for r in result.web_resources
            ]
        }
        
        # Add full formatted analysis
        export_data["ai_analysis"]["formatted"] = self.format_analysis(result)
        
        return export_data
    
    def get_html_section(self, result: Optional[AnalysisResult] = None) -> str:
        """Get AI analysis as HTML section for reports.
        
        Args:
            result: Analysis result (uses last result if None)
            
        Returns:
            HTML string for embedding in reports
        """
        if result is None:
            result = self._last_result
        
        if result is None:
            return ""
        
        severity_colors = {
            "critical": "#dc3545",
            "warning": "#ffc107",
            "info": "#17a2b8",
            "unknown": "#6c757d"
        }
        severity_icons = {
            "critical": "🔴",
            "warning": "🟡",
            "info": "🔵",
            "unknown": "⚪"
        }
        color = severity_colors.get(result.severity, "#6c757d")
        icon = severity_icons.get(result.severity, "⚪")
        
        html_parts = [
            '<div class="card ai-analysis">',
            '<h2>🤖 AI-Powered Verdict</h2>',
            f'<div class="severity-banner" style="background: {color}; color: white; padding: 1rem; border-radius: 8px; margin-bottom: 1rem;">',
            f'<h3 style="margin: 0;">{icon} Severity: {result.severity.upper()}</h3>',
            '</div>',
        ]
        
        # Section 1: What Happened (Summary)
        html_parts.append('<div class="verdict-section">')
        html_parts.append('<h3>📋 What Happened</h3>')
        if result.summary:
            html_parts.append(f'<p>{_escape_html(result.summary)}</p>')
        elif result.kb_matches:
            html_parts.append(f'<p>{_escape_html(result.kb_matches[0].description)}</p>')
        else:
            html_parts.append('<p>No significant issues detected in the logs.</p>')
        html_parts.append('</div>')
        
        # Section 2: How It Happened (Root Cause)
        html_parts.append('<div class="verdict-section">')
        html_parts.append('<h3>🔍 How It Happened (Root Cause)</h3>')
        if result.root_cause:
            html_parts.append(f'<p>{_escape_html(result.root_cause)}</p>')
        elif result.kb_matches and result.kb_matches[0].causes:
            html_parts.append('<ul>')
            for cause in result.kb_matches[0].causes[:5]:
                html_parts.append(f'<li>{_escape_html(cause)}</li>')
            html_parts.append('</ul>')
        else:
            html_parts.append('<p>Root cause analysis not available for this log.</p>')
        html_parts.append('</div>')
        
        # Section 3: How to Solve It (Solutions)
        html_parts.append('<div class="verdict-section">')
        html_parts.append('<h3>🔧 How to Solve It</h3>')
        if result.solutions:
            html_parts.append('<ol class="solutions-list">')
            for solution in result.solutions:
                html_parts.append(f'<li>{_escape_html(solution)}</li>')
            html_parts.append('</ol>')
        elif result.kb_matches and result.kb_matches[0].solutions:
            html_parts.append('<ol class="solutions-list">')
            for solution in result.kb_matches[0].solutions:
                html_parts.append(f'<li>{_escape_html(solution)}</li>')
            html_parts.append('</ol>')
        else:
            html_parts.append('<p>No specific solutions available. System appears healthy.</p>')
        html_parts.append('</div>')
        
        # Section 4: Full AI Analysis (if LLM was used)
        if result.used_llm and result.llm_analysis:
            html_parts.append('<div class="verdict-section">')
            html_parts.append(f'<h3>🧠 Detailed AI Analysis (Powered by {result.llm_provider})</h3>')
            html_parts.append('<div class="llm-analysis" style="background: rgba(0,0,0,0.2); padding: 1rem; border-radius: 8px; white-space: pre-wrap; font-family: monospace; font-size: 0.9rem;">')
            html_parts.append(_escape_html(result.llm_analysis))
            html_parts.append('</div>')
            html_parts.append('</div>')
        
        # Section 5: Knowledge Base Matches
        if result.kb_matches:
            html_parts.append('<div class="verdict-section">')
            html_parts.append('<h3>📚 Knowledge Base Matches</h3>')
            html_parts.append('<div class="kb-matches">')
            for entry in result.kb_matches:
                entry_color = severity_colors.get(entry.severity, "#6c757d")
                html_parts.append(f'<div class="kb-entry" style="border-left: 4px solid {entry_color}; padding-left: 1rem; margin-bottom: 1rem;">')
                html_parts.append(f'<h4 style="margin: 0 0 0.5rem 0;">{_escape_html(entry.title)}</h4>')
                html_parts.append(f'<p style="margin: 0; color: #a0a0a0;">{_escape_html(entry.description)}</p>')
                if entry.resources:
                    html_parts.append('<p style="margin: 0.5rem 0 0 0; font-size: 0.85rem;">')
                    for resource in entry.resources[:2]:
                        html_parts.append(f'<a href="{_escape_html(resource)}" target="_blank" style="color: #3498db; margin-right: 1rem;">📖 {_escape_html(resource[:50])}...</a>')
                    html_parts.append('</p>')
                html_parts.append('</div>')
            html_parts.append('</div>')
            html_parts.append('</div>')
        
        # Section 6: Related Resources (Web Search)
        if result.web_resources:
            html_parts.append('<div class="verdict-section">')
            html_parts.append('<h3>🌐 Related Resources</h3>')
            html_parts.append('<ul class="resources-list">')
            for resource in result.web_resources:
                html_parts.append(
                    f'<li><a href="{_escape_html(resource.url)}" target="_blank" style="color: #3498db;">'
                    f'🔗 {_escape_html(resource.title)}</a>'
                )
                if resource.snippet:
                    html_parts.append(f'<br><small style="color: #808080;">{_escape_html(resource.snippet[:150])}...</small>')
                html_parts.append('</li>')
            html_parts.append('</ul>')
            html_parts.append('</div>')
        
        # Footer with sources
        html_parts.append('<div class="verdict-footer" style="margin-top: 1.5rem; padding-top: 1rem; border-top: 1px solid rgba(255,255,255,0.1);">')
        sources = []
        if result.used_llm:
            sources.append(f"🤖 {result.llm_provider} LLM")
        if result.used_knowledge_base:
            sources.append("📚 Knowledge Base")
        if result.used_web_search:
            sources.append("🌐 Web Search")
        
        html_parts.append(f'<p style="color: #808080; font-size: 0.85rem; margin: 0;">')
        html_parts.append(f'<strong>Analysis Sources:</strong> {", ".join(sources) if sources else "None"}<br>')
        html_parts.append(f'<strong>Analysis Time:</strong> {result.analysis_time_ms}ms')
        html_parts.append('</p>')
        html_parts.append('</div>')
        
        html_parts.append('</div>')
        
        return '\n'.join(html_parts)


def _escape_html(text: str) -> str:
    """Escape HTML special characters."""
    import html
    return html.escape(text)


# Plugin discovery function
def get_plugin() -> AIPlugin:
    """Get plugin instance for Kernicle.
    
    This function is called by Kernicle to discover and load the plugin.
    """
    return AIPlugin()


# Check if plugin is available (for kernicle to import)
def is_plugin_available() -> bool:
    """Check if the AI plugin is available."""
    plugin = AIPlugin()
    return plugin.is_available()
