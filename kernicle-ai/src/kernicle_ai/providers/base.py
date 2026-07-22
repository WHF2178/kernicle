"""
Base LLM provider interface and common utilities.
"""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Optional
import os


@dataclass
class LLMResponse:
    """Response from an LLM provider."""
    content: str
    provider: str
    model: str
    tokens_used: Optional[int] = None
    error: Optional[str] = None
    success: bool = True


class BaseLLMProvider(ABC):
    """Abstract base class for LLM providers."""
    
    name: str = "base"
    
    @abstractmethod
    def is_available(self) -> bool:
        """Check if this provider is configured and available."""
        pass
    
    @abstractmethod
    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """
        Generate a response from the LLM.
        
        Args:
            prompt: The user prompt
            system_prompt: Optional system prompt for context
            
        Returns:
            LLMResponse with the generated content
        """
        pass
    
    def get_api_key(self, env_var: str) -> Optional[str]:
        """Get API key from environment variable."""
        return os.environ.get(env_var)


def get_system_prompt() -> str:
    """Get the system prompt for log analysis."""
    return """You are an expert Linux system administrator and kernel developer. 
Your task is to analyze system logs, identify issues, and provide actionable solutions.

When analyzing logs:
1. Identify the root cause of any errors, panics, or anomalies
2. Explain the issue in clear, technical but understandable terms
3. Provide specific, actionable fix recommendations
4. Suggest relevant documentation or resources

Format your response as:
DIAGNOSIS:
[Clear explanation of what happened and why]

SEVERITY: [Critical/Warning/Info]

ROOT_CAUSE:
[Technical root cause analysis]

FIXES:
1. [First recommended fix with exact commands]
2. [Second option if applicable]
3. [Third option if applicable]

PREVENTION:
[How to prevent this issue in the future]

Keep responses concise but complete. Focus on actionable information."""
