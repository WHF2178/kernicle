"""Main analyzer module for kernicle-ai.

Orchestrates LLM providers, knowledge base, and web search
to provide comprehensive AI-powered log analysis.
"""

import asyncio
from dataclasses import dataclass, field
from datetime import datetime
from typing import List, Optional, Dict, Any

from .providers import GroqProvider, GeminiProvider, LLMResponse
from .knowledge import KnowledgeBase, KnowledgeEntry, get_knowledge_base
from .search import DuckDuckGoSearch, SearchResult, format_search_results


@dataclass
class AnalysisResult:
    """Result of AI analysis."""
    
    # Core analysis
    summary: str = ""
    root_cause: str = ""
    solutions: List[str] = field(default_factory=list)
    severity: str = "unknown"  # critical, warning, info, unknown
    
    # Knowledge base matches
    kb_matches: List[KnowledgeEntry] = field(default_factory=list)
    
    # Web search results
    web_resources: List[SearchResult] = field(default_factory=list)
    
    # LLM response (if available)
    llm_analysis: str = ""
    llm_provider: str = ""
    llm_tokens_used: Optional[int] = None
    
    # Metadata
    analyzed_at: datetime = field(default_factory=datetime.now)
    analysis_time_ms: int = 0
    errors: List[str] = field(default_factory=list)
    
    # Status flags
    used_llm: bool = False
    used_knowledge_base: bool = False
    used_web_search: bool = False


class LogAnalyzer:
    """AI-powered log analyzer.
    
    Uses multiple sources for analysis:
    1. LLM (Groq primary, Gemini fallback)
    2. Built-in knowledge base
    3. DuckDuckGo web search
    """
    
    def __init__(
        self,
        enable_web_search: bool = True,
        enable_knowledge_base: bool = True
    ):
        """Initialize analyzer with providers.
        
        Args:
            enable_web_search: Enable DuckDuckGo search
            enable_knowledge_base: Enable built-in knowledge base
        """
        self.groq = GroqProvider()
        self.gemini = GeminiProvider()
        self.knowledge_base = get_knowledge_base() if enable_knowledge_base else None
        self.web_search = DuckDuckGoSearch() if enable_web_search else None
    
    async def analyze(
        self,
        log_content: str,
        context: Optional[str] = None,
        timeout: float = 60.0
    ) -> AnalysisResult:
        """Analyze log content using all available sources.
        
        Args:
            log_content: The log content to analyze
            context: Additional context (e.g., system info)
            timeout: Timeout for LLM requests
            
        Returns:
            AnalysisResult with comprehensive analysis
        """
        start_time = datetime.now()
        result = AnalysisResult()
        
        # FIRST: Determine severity from log patterns (deterministic)
        log_severity = self._determine_severity_from_logs(log_content)
        result.severity = log_severity
        
        # Build full prompt with context
        prompt = self._build_prompt(log_content, context)
        
        # Run all analysis sources in parallel
        tasks = []
        
        # LLM analysis task
        tasks.append(self._analyze_with_llm(prompt, timeout))
        
        # Knowledge base analysis (instant, but wrap in async)
        tasks.append(self._analyze_with_knowledge_base(log_content))
        
        # Web search for additional resources
        if self.web_search:
            tasks.append(self._search_web_resources(log_content))
        
        # Gather all results
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # Process LLM result
        llm_result = results[0]
        if isinstance(llm_result, tuple) and llm_result[0]:
            response, provider_name = llm_result
            result.llm_analysis = response.content or ""
            result.llm_provider = provider_name
            result.llm_tokens_used = response.tokens_used
            result.used_llm = True
            
            # Parse LLM response for structured data
            self._parse_llm_response(response.content or "", result, log_severity)
        elif isinstance(llm_result, tuple):
            _, error = llm_result
            if error:
                result.errors.append(f"LLM: {error}")
        
        # Process knowledge base result
        kb_result = results[1]
        if isinstance(kb_result, list) and kb_result:
            result.kb_matches = kb_result
            result.used_knowledge_base = True
            
            # If no LLM, use KB for summary
            if not result.used_llm and kb_result:
                self._summarize_from_kb(kb_result, result)
        
        # Process web search result
        if len(results) > 2:
            web_result = results[2]
            if isinstance(web_result, list) and web_result:
                result.web_resources = web_result
                result.used_web_search = True
        
        # Calculate analysis time
        end_time = datetime.now()
        result.analysis_time_ms = int((end_time - start_time).total_seconds() * 1000)
        
        return result
    
    def _build_prompt(self, log_content: str, context: Optional[str]) -> str:
        """Build the full prompt for LLM analysis."""
        parts = []
        
        if context:
            parts.append(f"## System Context\n{context}")
        
        parts.append(f"## Log Content\n```\n{log_content}\n```")
        
        return "\n\n".join(parts)
    
    async def _analyze_with_llm(
        self,
        prompt: str,
        timeout: float
    ) -> tuple[Optional[LLMResponse], Optional[str]]:
        """Try LLM analysis with fallback.
        
        Returns:
            Tuple of (response, provider_name) or (None, error_message)
        """
        # Try Groq first (faster)
        if self.groq.is_available():
            response = await self.groq.generate(prompt)
            if response.success:
                return (response, "Groq")
        
        # Fallback to Gemini
        if self.gemini.is_available():
            response = await self.gemini.generate(prompt)
            if response.success:
                return (response, "Gemini")
            return (None, response.error)
        
        # Neither available
        return (None, "No LLM API keys configured")
    
    async def _analyze_with_knowledge_base(
        self,
        log_content: str
    ) -> List[KnowledgeEntry]:
        """Search knowledge base for matches."""
        if not self.knowledge_base:
            return []
        
        return self.knowledge_base.search(log_content, max_results=3)
    
    async def _search_web_resources(
        self,
        log_content: str
    ) -> List[SearchResult]:
        """Search web for relevant resources."""
        if not self.web_search:
            return []
        
        # Extract key error message for search
        error_keywords = self._extract_error_keywords(log_content)
        if not error_keywords:
            return []
        
        query = f"linux {error_keywords} solution"
        return await self.web_search.search(query, max_results=3)
    
    def _extract_error_keywords(self, log_content: str, max_length: int = 100) -> str:
        """Extract key error keywords for web search."""
        import re
        
        # Look for common error patterns
        patterns = [
            r"error[:\s]+([^\n]+)",
            r"failed[:\s]+([^\n]+)",
            r"panic[:\s]+([^\n]+)",
            r"OOPS[:\s]+([^\n]+)",
            r"BUG[:\s]+([^\n]+)",
            r"segfault[:\s]+([^\n]+)",
        ]
        
        for pattern in patterns:
            match = re.search(pattern, log_content, re.IGNORECASE)
            if match:
                keyword = match.group(1).strip()[:max_length]
                # Clean up
                keyword = re.sub(r'\s+', ' ', keyword)
                return keyword
        
        # Fallback: first line of content
        first_line = log_content.split('\n')[0][:max_length]
        return first_line
    
    def _parse_llm_response(self, content: str, result: AnalysisResult, log_severity: str = "unknown") -> None:
        """Parse structured data from LLM response.
        
        Args:
            content: LLM response content
            result: AnalysisResult to populate
            log_severity: Severity determined from log patterns (for comparison)
        """
        import re
        
        # Severity priority (higher index = more severe)
        severity_priority = {"unknown": 0, "info": 1, "warning": 2, "critical": 3}
        
        # Try to extract summary section
        summary_match = re.search(
            r'(?:summary|overview|diagnosis)[:\s]*\n?(.*?)(?=\n\n|\n#|\nSEVERITY|\nROOT|\Z)',
            content,
            re.IGNORECASE | re.DOTALL
        )
        if summary_match:
            result.summary = summary_match.group(1).strip()[:500]
        else:
            # Use first paragraph as summary
            paragraphs = content.split('\n\n')
            if paragraphs:
                result.summary = paragraphs[0].strip()[:500]
        
        # Try to extract root cause
        cause_match = re.search(
            r'(?:root.?cause|cause|reason)[:\s]*\n?(.*?)(?=\n\n|\n#|\nFIXES|\Z)',
            content,
            re.IGNORECASE | re.DOTALL
        )
        if cause_match:
            result.root_cause = cause_match.group(1).strip()[:500]
        
        # Try to extract solutions
        solutions_match = re.search(
            r'(?:solution|recommendation|fix|action|fixes)[s]?[:\s]*\n?(.*?)(?=\n\n#|\nPREVENTION|\Z)',
            content,
            re.IGNORECASE | re.DOTALL
        )
        if solutions_match:
            solutions_text = solutions_match.group(1)
            # Parse bullet points
            bullets = re.findall(r'[-*•]\s*(.+)', solutions_text)
            if bullets:
                result.solutions = [b.strip() for b in bullets[:10]]
            else:
                # Numbered list
                numbered = re.findall(r'\d+[.)]\s*(.+)', solutions_text)
                if numbered:
                    result.solutions = [n.strip() for n in numbered[:10]]
        
        # Determine severity from LLM response keywords
        content_lower = content.lower()
        llm_severity = "unknown"
        if any(w in content_lower for w in ['critical', 'severe', 'urgent', 'immediately', 'panic', 'crash']):
            llm_severity = "critical"
        elif any(w in content_lower for w in ['warning', 'attention', 'should', 'recommend']):
            llm_severity = "warning"
        elif any(w in content_lower for w in ['minor', 'low priority', 'informational', 'info']):
            llm_severity = "info"
        
        # Use the MORE SEVERE of log-based vs LLM-based severity
        # This ensures critical patterns in logs are never downgraded
        if severity_priority.get(llm_severity, 0) > severity_priority.get(log_severity, 0):
            result.severity = llm_severity
        else:
            result.severity = log_severity
    
    def _determine_severity_from_logs(self, log_content: str) -> str:
        """Determine severity directly from log content patterns.
        
        This provides deterministic severity assessment based on 
        known critical patterns, independent of LLM response.
        
        Returns:
            Severity level: 'critical', 'warning', 'info', or 'unknown'
        """
        import re
        log_lower = log_content.lower()
        
        # CRITICAL patterns - system is down or data loss risk
        critical_patterns = [
            r'kernel panic',
            r'kernel BUG',
            r'BUG:',
            r'OOPS:',
            r'general protection fault',
            r'NULL pointer dereference',
            r'unable to handle kernel',
            r'oom.killer|out of memory|oom_kill',
            r'filesystem.*read.only|remounting.*read.only',
            r'hardware error',
            r'machine check exception',
            r'EDAC.*error',
            r'I/O error.*critical',
            r'data corruption',
            r'hard lockup',
            r'soft lockup.*CPU.*stuck',
            r'rcu.*stall',
            r'watchdog.*timeout',
        ]
        
        for pattern in critical_patterns:
            if re.search(pattern, log_content, re.IGNORECASE):
                return "critical"
        
        # WARNING patterns - needs attention but system operational
        warning_patterns = [
            r'error',
            r'failed',
            r'warning',
            r'I/O error',
            r'EXT4-fs error',
            r'XFS.*error',
            r'segfault',
            r'page allocation failure',
            r'CPU.*throttled',
            r'thermal',
            r'voltage',
            r'fan.*failure',
            r'disk.*smart.*error',
            r'connection.*refused',
            r'timeout',
            r'denied',
        ]
        
        for pattern in warning_patterns:
            if re.search(pattern, log_content, re.IGNORECASE):
                return "warning"
        
        # INFO patterns - informational, no action needed
        info_patterns = [
            r'started|starting',
            r'stopped|stopping', 
            r'loaded|loading',
            r'connected|disconnected',
            r'mounted|unmounted',
        ]
        
        for pattern in info_patterns:
            if re.search(pattern, log_content, re.IGNORECASE):
                return "info"
        
        return "unknown"
    
    def _summarize_from_kb(
        self,
        kb_matches: List[KnowledgeEntry],
        result: AnalysisResult
    ) -> None:
        """Populate result from knowledge base when LLM unavailable."""
        if not kb_matches:
            return
        
        top_match = kb_matches[0]
        result.summary = top_match.description
        result.root_cause = top_match.causes[0] if top_match.causes else ""
        result.solutions = top_match.solutions[:5]
        result.severity = top_match.severity
    
    def format_result(self, result: AnalysisResult, log_content: str = "") -> str:
        """Format analysis result as markdown.
        
        Args:
            result: The analysis result to format
            log_content: Original log content for severity explanation
            
        Returns:
            Formatted markdown string
        """
        lines = []
        
        # Header
        lines.append("# 🤖 AI-Powered Verdict")
        lines.append("")
        
        # Severity badge with explanation
        severity_emoji = {
            "critical": "🔴",
            "warning": "🟡",
            "info": "🔵",
            "unknown": "⚪"
        }
        severity_desc = {
            "critical": "System down, data loss risk, or immediate action required",
            "warning": "Needs attention but system operational",
            "info": "Informational, no action required",
            "unknown": "Unable to determine severity"
        }
        emoji = severity_emoji.get(result.severity, "⚪")
        desc = severity_desc.get(result.severity, "")
        lines.append(f"**Severity Level:** {emoji} **{result.severity.upper()}**")
        lines.append(f"")
        lines.append(f"*{desc}*")
        lines.append("")
        
        # Show what triggered the severity
        if result.severity == "critical" and log_content:
            lines.append("**Detected Critical Patterns:**")
            critical_found = []
            import re
            critical_checks = [
                (r'kernel panic', "Kernel Panic"),
                (r'BUG:|kernel BUG', "Kernel Bug"),
                (r'NULL pointer dereference', "NULL Pointer Dereference"),
                (r'oom.killer|out of memory', "Out of Memory (OOM)"),
                (r'filesystem.*read.only|remounting.*read.only', "Filesystem Read-Only"),
                (r'soft lockup|hard lockup', "CPU Lockup"),
                (r'EDAC.*error', "Memory (ECC) Error"),
                (r'hardware error', "Hardware Error"),
            ]
            for pattern, name in critical_checks:
                if re.search(pattern, log_content, re.IGNORECASE):
                    critical_found.append(name)
            if critical_found:
                for item in critical_found:
                    lines.append(f"- ⚠️ {item}")
            lines.append("")
        
        lines.append("---")
        lines.append("")
        
        # Section 1: What Happened
        lines.append("## 📋 What Happened")
        lines.append("")
        if result.summary:
            lines.append(result.summary)
        elif result.kb_matches:
            lines.append(result.kb_matches[0].description)
        else:
            lines.append("No significant issues were detected in the analyzed logs.")
        lines.append("")
        
        # Section 2: How It Happened (Root Cause)
        lines.append("## 🔍 How It Happened (Root Cause)")
        lines.append("")
        if result.root_cause:
            lines.append(result.root_cause)
        elif result.kb_matches and result.kb_matches[0].causes:
            for cause in result.kb_matches[0].causes[:5]:
                lines.append(f"- {cause}")
        else:
            lines.append("Root cause analysis not available for this log content.")
        lines.append("")
        
        # Section 3: How to Solve It
        lines.append("## 🔧 How to Solve It")
        lines.append("")
        if result.solutions:
            for i, solution in enumerate(result.solutions, 1):
                lines.append(f"{i}. {solution}")
        elif result.kb_matches and result.kb_matches[0].solutions:
            for i, solution in enumerate(result.kb_matches[0].solutions, 1):
                lines.append(f"{i}. {solution}")
        else:
            lines.append("No specific solutions required. System appears healthy.")
        lines.append("")
        
        # Section 4: Detailed AI Analysis (Full LLM response)
        if result.llm_analysis and result.used_llm:
            lines.append("## 🧠 Detailed AI Analysis")
            lines.append(f"*Powered by {result.llm_provider}*")
            lines.append("")
            lines.append("```")
            lines.append(result.llm_analysis)
            lines.append("```")
            lines.append("")
        
        # Section 5: Knowledge Base Matches
        if result.kb_matches:
            lines.append("## 📚 Knowledge Base Matches")
            lines.append("")
            for entry in result.kb_matches:
                lines.append(f"### {entry.title} ({entry.severity})")
                lines.append(f"_{entry.description}_")
                lines.append("")
                if entry.resources:
                    lines.append("**Documentation:**")
                    for resource in entry.resources[:3]:
                        lines.append(f"- {resource}")
                lines.append("")
        
        # Section 6: Web Resources
        if result.web_resources:
            lines.append("## 🌐 Related Resources")
            lines.append("")
            for resource in result.web_resources:
                lines.append(f"- [{resource.title}]({resource.url})")
                if resource.snippet:
                    lines.append(f"  > {resource.snippet[:150]}...")
            lines.append("")
        
        # Footer with sources
        lines.append("---")
        lines.append("")
        lines.append("### Analysis Sources")
        lines.append("")
        sources = []
        if result.used_llm:
            sources.append(f"🤖 {result.llm_provider} LLM")
        if result.used_knowledge_base:
            sources.append("📚 Knowledge Base")
        if result.used_web_search:
            sources.append("🌐 Web Search")
        
        if sources:
            for src in sources:
                lines.append(f"- {src}")
        else:
            lines.append("- None")
        lines.append("")
        lines.append(f"**Analysis Time:** {result.analysis_time_ms}ms")
        
        if result.errors:
            lines.append("")
            lines.append("### ⚠️ Warnings")
            for error in result.errors:
                lines.append(f"- {error}")
        
        return "\n".join(lines)


# Convenience function for quick analysis
async def analyze_logs(
    log_content: str,
    context: Optional[str] = None
) -> AnalysisResult:
    """Analyze logs using default analyzer.
    
    Args:
        log_content: Log content to analyze
        context: Optional system context
        
    Returns:
        AnalysisResult with analysis
    """
    analyzer = LogAnalyzer()
    return await analyzer.analyze(log_content, context)
