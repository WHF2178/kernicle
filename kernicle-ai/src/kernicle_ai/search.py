"""DuckDuckGo search for finding relevant resources.

Uses DuckDuckGo's HTML search - no API key required!
"""

import re
from dataclasses import dataclass
from typing import List, Optional
from urllib.parse import quote_plus

import httpx


@dataclass
class SearchResult:
    """A single search result."""
    
    title: str
    url: str
    snippet: str


class DuckDuckGoSearch:
    """Search DuckDuckGo for relevant resources.
    
    Uses the HTML interface, no API key needed.
    """
    
    BASE_URL = "https://html.duckduckgo.com/html/"
    
    def __init__(self, timeout: float = 10.0):
        self.timeout = timeout
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        }
    
    async def search(
        self,
        query: str,
        max_results: int = 5
    ) -> List[SearchResult]:
        """Search DuckDuckGo for the query.
        
        Args:
            query: Search query
            max_results: Maximum number of results to return
            
        Returns:
            List of SearchResult objects
        """
        results: List[SearchResult] = []
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    self.BASE_URL,
                    data={"q": query, "b": ""},
                    headers=self.headers,
                    timeout=self.timeout,
                    follow_redirects=True
                )
                
                if response.status_code != 200:
                    return results
                
                html = response.text
                results = self._parse_results(html, max_results)
                
        except Exception:
            # Silently fail - search is optional
            pass
        
        return results
    
    def _parse_results(self, html: str, max_results: int) -> List[SearchResult]:
        """Parse search results from HTML.
        
        Args:
            html: Raw HTML response
            max_results: Max results to extract
            
        Returns:
            List of parsed SearchResult objects
        """
        results: List[SearchResult] = []
        
        # Find result blocks
        # DuckDuckGo HTML format: <a class="result__a" href="...">title</a>
        # and <a class="result__snippet">snippet</a>
        
        # Pattern for result links
        link_pattern = re.compile(
            r'<a[^>]*class="result__a"[^>]*href="([^"]*)"[^>]*>([^<]*)</a>',
            re.IGNORECASE
        )
        
        # Pattern for snippets
        snippet_pattern = re.compile(
            r'<a[^>]*class="result__snippet"[^>]*>([^<]*(?:<[^>]*>[^<]*</[^>]*>)*[^<]*)</a>',
            re.IGNORECASE
        )
        
        # Find all matches
        links = link_pattern.findall(html)
        snippets = snippet_pattern.findall(html)
        
        for i, (url, title) in enumerate(links[:max_results]):
            # Clean up URL (DuckDuckGo wraps URLs)
            actual_url = self._extract_url(url)
            if not actual_url:
                continue
            
            # Get corresponding snippet
            snippet = ""
            if i < len(snippets):
                snippet = self._clean_html(snippets[i])
            
            # Clean title
            title = self._clean_html(title)
            
            if title and actual_url:
                results.append(SearchResult(
                    title=title,
                    url=actual_url,
                    snippet=snippet[:300] if snippet else ""
                ))
        
        return results
    
    def _extract_url(self, wrapped_url: str) -> Optional[str]:
        """Extract actual URL from DuckDuckGo's redirect wrapper.
        
        Args:
            wrapped_url: The wrapped URL from DDG
            
        Returns:
            Actual URL or None
        """
        # DDG wraps URLs like: //duckduckgo.com/l/?uddg=https%3A%2F%2F...
        if "uddg=" in wrapped_url:
            match = re.search(r'uddg=([^&]+)', wrapped_url)
            if match:
                from urllib.parse import unquote
                return unquote(match.group(1))
        
        # Direct URL
        if wrapped_url.startswith("http"):
            return wrapped_url
        
        # Protocol-relative URL
        if wrapped_url.startswith("//"):
            return "https:" + wrapped_url
        
        return None
    
    def _clean_html(self, text: str) -> str:
        """Remove HTML tags and clean text.
        
        Args:
            text: Text possibly containing HTML
            
        Returns:
            Cleaned text
        """
        # Remove HTML tags
        text = re.sub(r'<[^>]+>', '', text)
        # Decode common entities
        text = text.replace("&amp;", "&")
        text = text.replace("&lt;", "<")
        text = text.replace("&gt;", ">")
        text = text.replace("&quot;", '"')
        text = text.replace("&#x27;", "'")
        text = text.replace("&nbsp;", " ")
        # Clean whitespace
        text = " ".join(text.split())
        return text.strip()


async def search_for_error(
    error_message: str,
    context: str = "linux kernel"
) -> List[SearchResult]:
    """Convenience function to search for an error.
    
    Args:
        error_message: The error message to search for
        context: Additional context (e.g., "linux kernel", "ubuntu")
        
    Returns:
        List of search results
    """
    search = DuckDuckGoSearch()
    query = f"{context} {error_message}"
    return await search.search(query)


def format_search_results(results: List[SearchResult]) -> str:
    """Format search results as markdown.
    
    Args:
        results: List of search results
        
    Returns:
        Formatted markdown string
    """
    if not results:
        return "No relevant resources found."
    
    lines = ["### Related Resources", ""]
    
    for result in results:
        lines.append(f"- [{result.title}]({result.url})")
        if result.snippet:
            lines.append(f"  > {result.snippet}")
        lines.append("")
    
    return "\n".join(lines)
