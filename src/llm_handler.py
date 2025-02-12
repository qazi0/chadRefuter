from typing import Optional
import httpx
from dataclasses import dataclass
from abc import ABC, abstractmethod

@dataclass
class LLMResponse:
    text: str
    raw_response: dict

class LLMHandler(ABC):
    @abstractmethod
    async def generate_response(self, prompt: str) -> LLMResponse:
        pass

class OllamaHandler(LLMHandler):
    def __init__(self, logger, model="llama3.1:8b", base_url="http://localhost:11434"):
        self.logger = logger
        self.model = model
        self.base_url = base_url
        self.client = httpx.AsyncClient(timeout=30.0)

    async def generate_response(self, prompt: str) -> LLMResponse:
        """Send prompt to Ollama and get response"""
        try:
            url = f"{self.base_url}/api/generate"
            payload = {
                "model": self.model,
                "prompt": prompt,
                "stream": False
            }

            # Log the prompt
            full_prompt_message = f"Sending request to LLM - Prompt: {prompt}"
            console_prompt_message = f"Sending request to LLM - Prompt: {prompt[:100]}..."
            self.logger.debug(full_prompt_message, console_prompt_message)
            
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            generated_text = data.get('response', '')
            
            # Log the response
            full_response_message = f"Received LLM response: {generated_text}"
            console_response_message = f"Received LLM response: {generated_text[:100]}..."
            self.logger.debug(full_response_message, console_response_message)
            
            return LLMResponse(text=generated_text, raw_response=data)

        except httpx.HTTPError as e:
            self.logger.error(f"HTTP error while querying LLM: {str(e)}")
            raise
        except Exception as e:
            self.logger.error(f"Error generating LLM response: {str(e)}")
            raise

    async def close(self):
        await self.client.aclose() 