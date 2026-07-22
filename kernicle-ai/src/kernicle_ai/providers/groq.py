"""
Groq LLM Provider - Primary free provider using Llama models.

Groq offers:
- 14,400 tokens/minute free tier
- 30 requests/minute
- Blazing fast inference
- Llama 3.1 70B model

Get API key: https://console.groq.com
"""

import httpx
from typing import Optional
import json

from kernicle_ai.providers.base import BaseLLMProvider, LLMResponse, get_system_prompt


class GroqProvider(BaseLLMProvider):
    """Groq API provider using Llama 3.3 70B."""
    
    name = "groq"
    API_URL = "https://api.groq.com/openai/v1/chat/completions"
    MODEL = "llama-3.3-70b-versatile"
    
    def __init__(self):
        self.api_key = self.get_api_key("GROQ_API_KEY")
    
    def is_available(self) -> bool:
        """Check if Groq API key is configured."""
        return self.api_key is not None and len(self.api_key) > 0
    
    async def generate(self, prompt: str, system_prompt: Optional[str] = None) -> LLMResponse:
        """
        Generate response using Groq API.
        
        Args:
            prompt: User prompt with log content
            system_prompt: Optional system prompt (defaults to log analysis prompt)
            
        Returns:
            LLMResponse with analysis
        """
        if not self.is_available():
            return LLMResponse(
                content="",
                provider=self.name,
                model=self.MODEL,
                success=False,
                error="GROQ_API_KEY not set"
            )
        
        if system_prompt is None:
            system_prompt = get_system_prompt()
        
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        
        payload = {
            "model": self.MODEL,
            "messages": [
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": prompt},
            ],
            "temperature": 0.3,  # Lower temperature for more focused analysis
            "max_tokens": 2000,
        }
        
        try:
            async with httpx.AsyncClient(timeout=60.0) as client:
                response = await client.post(
                    self.API_URL,
                    headers=headers,
                    json=payload,
                )
                
                if response.status_code == 200:
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    tokens = data.get("usage", {}).get("total_tokens")
                    
                    return LLMResponse(
                        content=content,
                        provider=self.name,
                        model=self.MODEL,
                        tokens_used=tokens,
                        success=True,
                    )
                else:
                    error_msg = f"Groq API error: {response.status_code}"
                    try:
                        error_data = response.json()
                        if "error" in error_data:
                            error_msg = f"Groq API: {error_data['error'].get('message', str(error_data['error']))}"
                    except:
                        pass
                    
                    return LLMResponse(
                        content="",
                        provider=self.name,
                        model=self.MODEL,
                        success=False,
                        error=error_msg,
                    )
                    
        except httpx.TimeoutException:
            return LLMResponse(
                content="",
                provider=self.name,
                model=self.MODEL,
                success=False,
                error="Groq API timeout",
            )
        except Exception as e:
            return LLMResponse(
                content="",
                provider=self.name,
                model=self.MODEL,
                success=False,
                error=f"Groq API error: {str(e)}",
            )
