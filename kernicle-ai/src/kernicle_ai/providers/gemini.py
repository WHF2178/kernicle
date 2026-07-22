"""Gemini API provider (fallback)."""

import os
from typing import Optional

import httpx

from .base import BaseLLMProvider, LLMResponse, get_system_prompt


class GeminiProvider(BaseLLMProvider):
    """Google Gemini API provider.
    
    Free tier: 60 requests/minute, 1M tokens/day
    Get API key at: https://aistudio.google.com/app/apikey
    """
    
    name = "gemini"
    API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-1.5-flash:generateContent"
    MODEL = "gemini-1.5-flash"
    
    def __init__(self):
        """Initialize with API key from env."""
        # Try GOOGLE_API_KEY first (per spec), then GEMINI_API_KEY as fallback
        self.api_key = self.get_api_key("GOOGLE_API_KEY") or self.get_api_key("GEMINI_API_KEY")
    
    def is_available(self) -> bool:
        """Check if Gemini API key is configured."""
        return bool(self.api_key)
    
    async def generate(
        self,
        prompt: str,
        system_prompt: Optional[str] = None
    ) -> LLMResponse:
        """Generate analysis using Gemini API.
        
        Args:
            prompt: The log data and context to analyze
            system_prompt: Optional system prompt (defaults to log analysis prompt)
            
        Returns:
            LLMResponse with analysis or error
        """
        if not self.is_available():
            return LLMResponse(
                content="",
                provider=self.name,
                model=self.MODEL,
                success=False,
                error="GOOGLE_API_KEY not set. Get one at https://aistudio.google.com/app/apikey"
            )
        
        sys_prompt = system_prompt or get_system_prompt()
        
        # Gemini uses a different format - system instruction + user content
        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [
                        {"text": f"{sys_prompt}\n\n---\n\nAnalyze this:\n\n{prompt}"}
                    ]
                }
            ],
            "generationConfig": {
                "temperature": 0.3,
                "maxOutputTokens": 2048,
                "topP": 0.8,
                "topK": 40
            },
            "safetySettings": [
                {
                    "category": "HARM_CATEGORY_DANGEROUS_CONTENT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_HARASSMENT",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_HATE_SPEECH",
                    "threshold": "BLOCK_NONE"
                },
                {
                    "category": "HARM_CATEGORY_SEXUALLY_EXPLICIT",
                    "threshold": "BLOCK_NONE"
                }
            ]
        }
        
        headers = {
            "Content-Type": "application/json"
        }
        
        # API key goes in URL for Gemini
        url = f"{self.API_URL}?key={self.api_key}"
        timeout = 60.0
        
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    url,
                    json=payload,
                    headers=headers,
                    timeout=timeout
                )
                
                if response.status_code == 429:
                    return LLMResponse(
                        content="",
                        provider=self.name,
                        model=self.MODEL,
                        success=False,
                        error="Gemini rate limit exceeded. Try again later."
                    )
                
                if response.status_code == 400:
                    error_data = response.json()
                    error_msg = error_data.get("error", {}).get("message", "Bad request")
                    return LLMResponse(
                        content="",
                        provider=self.name,
                        model=self.MODEL,
                        success=False,
                        error=f"Gemini API error: {error_msg}"
                    )
                
                response.raise_for_status()
                
                data = response.json()
                
                # Extract content from Gemini response
                candidates = data.get("candidates", [])
                if not candidates:
                    return LLMResponse(
                        content="",
                        provider=self.name,
                        model=self.MODEL,
                        success=False,
                        error="No response from Gemini API"
                    )
                
                content = candidates[0].get("content", {})
                parts = content.get("parts", [])
                if not parts:
                    return LLMResponse(
                        content="",
                        provider=self.name,
                        model=self.MODEL,
                        success=False,
                        error="Empty response from Gemini API"
                    )
                
                text = parts[0].get("text", "")
                
                # Get token counts if available
                usage = data.get("usageMetadata", {})
                tokens_used = usage.get("totalTokenCount")
                
                return LLMResponse(
                    content=text.strip(),
                    provider=self.name,
                    model=self.MODEL,
                    tokens_used=tokens_used,
                    success=True
                )
                
        except httpx.TimeoutException:
            return LLMResponse(
                content="",
                provider=self.name,
                model=self.MODEL,
                success=False,
                error=f"Request timed out after {timeout}s"
            )
        except httpx.HTTPStatusError as e:
            return LLMResponse(
                content="",
                provider=self.name,
                model=self.MODEL,
                success=False,
                error=f"HTTP error: {e.response.status_code}"
            )
        except Exception as e:
            return LLMResponse(
                content="",
                provider=self.name,
                model=self.MODEL,
                success=False,
                error=f"Unexpected error: {str(e)}"
            )
