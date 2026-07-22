"""AI Plugin integration for Kernicle.

Automatically detects and uses kernicle-ai when installed.
No --ai flag needed - it just works!
"""

from typing import Optional, Dict, Any, TYPE_CHECKING

# Lazy import to avoid import errors when kernicle-ai is not installed
if TYPE_CHECKING:
    from kernicle_ai import AIPlugin, AnalysisResult


_ai_plugin: Optional["AIPlugin"] = None
_ai_available: Optional[bool] = None


def is_ai_available() -> bool:
    """Check if kernicle-ai plugin is available.
    
    Returns:
        True if kernicle-ai is installed and available
    """
    global _ai_available
    
    if _ai_available is not None:
        return _ai_available
    
    try:
        from kernicle_ai import is_plugin_available
        _ai_available = is_plugin_available()
    except ImportError:
        _ai_available = False
    
    return _ai_available


def get_ai_plugin() -> Optional["AIPlugin"]:
    """Get the AI plugin instance.
    
    Returns:
        AIPlugin instance or None if not available
    """
    global _ai_plugin
    
    if not is_ai_available():
        return None
    
    if _ai_plugin is None:
        try:
            from kernicle_ai import get_plugin
            _ai_plugin = get_plugin()
        except ImportError:
            return None
    
    return _ai_plugin


def get_ai_status() -> Dict[str, Any]:
    """Get AI plugin status information.
    
    Returns:
        Dict with status info or indication that AI is not available
    """
    if not is_ai_available():
        return {
            "available": False,
            "message": "kernicle-ai plugin not installed. Install with: pip install kernicle-ai"
        }
    
    plugin = get_ai_plugin()
    if plugin is None:
        return {
            "available": False,
            "message": "kernicle-ai plugin failed to load"
        }
    
    return plugin.get_status()


def analyze_logs(
    log_content: str,
    context: Optional[str] = None,
    timeout: float = 60.0
) -> Optional["AnalysisResult"]:
    """Analyze logs with AI if available.
    
    Args:
        log_content: Log content to analyze
        context: Optional system context
        timeout: Request timeout
        
    Returns:
        AnalysisResult or None if AI not available
    """
    plugin = get_ai_plugin()
    if plugin is None:
        return None
    
    return plugin.analyze_sync(log_content, context, timeout)


def format_analysis(result: Optional["AnalysisResult"] = None, log_content: str = "") -> str:
    """Format AI analysis as markdown.
    
    Args:
        result: Analysis result to format
        log_content: Original log content for severity explanation
        
    Returns:
        Formatted markdown or empty string
    """
    plugin = get_ai_plugin()
    if plugin is None:
        return ""
    
    return plugin.format_analysis(result, log_content)


def get_html_analysis(result: Optional["AnalysisResult"] = None) -> str:
    """Get AI analysis as HTML section.
    
    Args:
        result: Analysis result
        
    Returns:
        HTML string or empty string
    """
    plugin = get_ai_plugin()
    if plugin is None:
        return ""
    
    return plugin.get_html_section(result)


def enhance_export_data(
    export_data: Dict[str, Any],
    log_content: str,
    system_info: Optional[str] = None
) -> Dict[str, Any]:
    """Enhance export data with AI analysis.
    
    Args:
        export_data: Original export data
        log_content: Log content to analyze
        system_info: Optional system info
        
    Returns:
        Enhanced export data (original if AI not available)
    """
    plugin = get_ai_plugin()
    if plugin is None:
        return export_data
    
    return plugin.enhance_export_data(export_data, log_content, system_info)
