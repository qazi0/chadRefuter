from typing import Optional
import httpx
from dataclasses import dataclass
from abc import ABC, abstractmethod
import os
from openai import AsyncOpenAI
from anthropic import AsyncAnthropic
import json
import google.generativeai as genai

def load_system_prompt(prompt_path: str) -> str:
    """Load system prompt from file"""
    try:
        with open(prompt_path, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except Exception as e:
        raise ValueError(f"Failed to load system prompt from {prompt_path}: {str(e)}")

@dataclass
class LLMResponse:
    text: str
    raw_response: dict

class LLMHandler(ABC):
    @abstractmethod
    async def generate_response(self, prompt: str) -> LLMResponse:
        pass

    @abstractmethod
    async def close(self):
        pass

    @classmethod
    def load_prompt(cls, prompt_path: str) -> str:
        return load_system_prompt(prompt_path)

class OllamaHandler(LLMHandler):
    def __init__(self, logger, prompt_path: str, model="llama3.1:8b", base_url=None):
        self.logger = logger
        self.model = model
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.client = httpx.AsyncClient(timeout=30.0)
        self.system_prompt = self.load_prompt(prompt_path)

    async def check_connection(self) -> bool:
        """Check if Ollama is accessible"""
        try:
            response = await self.client.get(f"{self.base_url}/api/tags")
            return response.status_code == 200
        except Exception as e:
            self.logger.error(f"Failed to connect to Ollama: {str(e)}")
            return False

    async def generate_response(self, prompt: str) -> LLMResponse:
        """Send prompt to Ollama and get response"""
        try:
            # Check connection first
            if not await self.check_connection():
                self.logger.error("Ollama is not accessible. Falling back to default response.")
                return LLMResponse(
                    text="By order of the Peaky Blinders, I must inform you that I'm temporarily indisposed. I'll return to address your concerns shortly.",
                    raw_response={"error": "Ollama service unavailable"}
                )

            url = f"{self.base_url}/api/generate"  # This is correct
            
            # Restructured payload to match Ollama's expected format
            payload = {
                "model": self.model,
                "prompt": f"{self.system_prompt}\n\nUser: {prompt}",
                "stream": False,
                "options": {
                    "temperature": 0.7,
                    "top_p": 0.95
                }
            }

            # Log the request
            self.logger.debug(
                f"Sending request to Ollama at {url}",
                f"Model: {self.model}, Prompt length: {len(prompt)}"
            )
            
            response = await self.client.post(url, json=payload)
            response.raise_for_status()
            
            data = response.json()
            generated_text = data.get('response', '')

            if generated_text.startswith('"') and generated_text.endswith('"'):
                generated_text = generated_text[1:-1]
            
            # Log the response
            full_response_message = f"Received Ollama response: {generated_text}"
            console_response_message = f"Received Ollama response: {generated_text[:100]}..."
            self.logger.debug(full_response_message, console_response_message)
            
            return LLMResponse(text=generated_text, raw_response=data)

        except httpx.HTTPError as e:
            self.logger.error(f"HTTP error while querying Ollama: {str(e)}")
            self.logger.debug(f"Request URL: {url}")
            self.logger.debug(f"Request payload: {payload}")
            return LLMResponse(
                text="Listen mate, I'm having a bit of technical difficulty at the moment. I'll be back to address your point properly soon.",
                raw_response={"error": str(e)}
            )
        except Exception as e:
            self.logger.error(f"Error generating Ollama response: {str(e)}")
            return LLMResponse(
                text="By order of the Peaky Blinders, there's been a temporary setback. I'll return to this matter shortly.",
                raw_response={"error": str(e)}
            )

    async def close(self):
        await self.client.aclose()

class OpenAIHandler(LLMHandler):
    def __init__(self, logger, prompt_path: str, model="gpt-3.5-turbo"):
        self.logger = logger
        self.model = model
        self.client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        self.system_prompt = self.load_prompt(prompt_path)

    async def generate_response(self, prompt: str) -> LLMResponse:
        try:
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": self.system_prompt},
                    {"role": "user", "content": prompt}
                ]
            )
            generated_text = response.choices[0].message.content
            
            # Log responses
            self.logger.debug(
                f"Received OpenAI response: {generated_text}",
                f"Received OpenAI response: {generated_text[:100]}..."
            )
            
            return LLMResponse(text=generated_text, raw_response=response.model_dump())
        except Exception as e:
            self.logger.error(f"Error generating OpenAI response: {str(e)}")
            raise

    async def close(self):
        pass  # OpenAI client doesn't need explicit cleanup

class AnthropicHandler(LLMHandler):
    def __init__(self, logger, prompt_path: str, model="claude-3-sonnet-20240229"):
        self.logger = logger
        self.model = model
        self.client = AsyncAnthropic(api_key=os.getenv("ANTHROPIC_API_KEY"))
        self.system_prompt = self.load_prompt(prompt_path)

    async def generate_response(self, prompt: str) -> LLMResponse:
        try:
            response = await self.client.messages.create(
                model=self.model,
                system=self.system_prompt,
                messages=[{"role": "user", "content": prompt}]
            )
            generated_text = response.content[0].text
            
            # Log responses
            self.logger.debug(
                f"Received Anthropic response: {generated_text}",
                f"Received Anthropic response: {generated_text[:100]}..."
            )
            
            return LLMResponse(text=generated_text, raw_response=response.model_dump())
        except Exception as e:
            self.logger.error(f"Error generating Anthropic response: {str(e)}")
            raise

    async def close(self):
        pass  # Anthropic client doesn't need explicit cleanup

class HuggingFaceHandler(LLMHandler):
    def __init__(self, logger, prompt_path: str, model="meta-llama/Llama-2-7b-chat-hf"):
        self.logger = logger
        self.model = model
        self.api_key = os.getenv("HUGGINGFACE_API_KEY")
        self.client = httpx.AsyncClient(timeout=30.0)
        self.system_prompt = self.load_prompt(prompt_path)

    async def generate_response(self, prompt: str) -> LLMResponse:
        try:
            headers = {
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "inputs": f"{self.system_prompt}\n\nUser: {prompt}",
                "parameters": {
                    "max_new_tokens": 256,
                    "temperature": 0.7,
                    "top_p": 0.95
                }
            }
            
            response = await self.client.post(
                f"https://api-inference.huggingface.co/models/{self.model}",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            data = response.json()
            generated_text = data[0]["generated_text"]
            
            # Log responses
            self.logger.debug(
                f"Received HuggingFace response: {generated_text}",
                f"Received HuggingFace response: {generated_text[:100]}..."
            )
            
            return LLMResponse(text=generated_text, raw_response=data)
        except Exception as e:
            self.logger.error(f"Error generating HuggingFace response: {str(e)}")
            raise

    async def close(self):
        await self.client.aclose()

class GeminiHandler(LLMHandler):
    def __init__(self, logger, prompt_path: str, model="gemini-2.0-flash"):
        self.logger = logger
        self.model = model
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            raise ValueError("GEMINI_API_KEY environment variable not set")
        genai.configure(api_key=api_key)
        self.client = genai.GenerativeModel(model_name=model)
        self.system_prompt = self.load_prompt(prompt_path)

    async def generate_response(self, prompt: str) -> LLMResponse:
        try:
            # Combine system prompt and user prompt
            full_prompt = f"{self.system_prompt}\n\nUser: {prompt}"
            
            # Generate response
            response = await self.client.generate_content_async(full_prompt)
            generated_text = response.text
            
            # Log responses
            self.logger.debug(
                f"Received Gemini response: {generated_text}",
                f"Received Gemini response: {generated_text[:100]}..."
            )
            
            # Convert response to dict format for consistency
            response_dict = {
                "model": self.model,
                "text": generated_text,
                "prompt_tokens": len(full_prompt.split()),
                "completion_tokens": len(generated_text.split()),
                "finish_reason": "stop"
            }
            
            return LLMResponse(text=generated_text, raw_response=response_dict)
        except Exception as e:
            self.logger.error(f"Error generating Gemini response: {str(e)}")
            raise

    async def close(self):
        pass  # Gemini client doesn't need explicit cleanup 