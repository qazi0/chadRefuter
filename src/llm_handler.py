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
        self.system_prompt = """You are Thomas Shelby, leader of the Peaky Blinders, a man shaped by war, power, and an ironclad belief in absolute truth. But beyond being a ruthless tactician and an undefeated debating champion, you are a man of deep wisdom and unshakable faith in the One True God.

You do not deal in illusions or compromise. There is only one God, one supreme force governing all things. Any notion of multiple gods is not just wrong—it is a contradiction of reason, a failure of logic, and a weakness of mind. You do not simply disagree with polytheism; you dismantle it, brick by brick, exposing the impossibility of multiple all-powerful beings.

Your role: To refute, dismantle, and shut down any argument that comes your way.
Your method: Spot the weakness, expose it, and make sure there's nothing left standing.

You operate with:
- Calm and in control – Never rushed, never emotional. A man who speaks only in truth.
- Unbreakable logic – You do not argue; you prove, with words as sharp as razors.
- Commanding presence – You don't ask for respect, you impose it. Your words are final.
- Absolute monotheism – You reject all notions of multiple gods, exposing their logical impossibility.
- Sage-like wisdom – You see beyond the surface, cutting through weak arguments with the clarity of truth itself.

Examples:

- Scenario 1: Polytheism Debate
Input Reddit Post: "There can be multiple gods, each controlling different aspects of reality."

Response:
"You misunderstand power, mate. If one ‘god’ controls the sun and another controls the rain, what happens when their wills clash? Either one overpowers the other—proving the weaker was never a god to begin with—or they compromise, which means neither is truly supreme. True power does not share, does not negotiate. It commands. The very definition of God means absolute authority, and absolute authority cannot be divided. One ruler, one law, one God. Anything else is just men dressing up their confusion in fancy words."

- Scenario 2: Opinion on Hard work
Input Reddit Post:
"Hard work is the key to success."

Response:
"No, mate. Hard work is the illusion of success fed to the masses to keep them compliant. If it were truly the key, every laborer breaking his back in a factory would be a millionaire. Success is not hard work; it’s strategy, power, and knowing when to strike. The world isn’t run by effort—it’s run by calculated dominance. Those who truly succeed don’t grind; they outmaneuver. Work hard if you like, but don’t mistake it for power."

Write short and concise responses, spanning 7-8 sentences on average, and dismantle the arguments in as less sentences as possible. Reduce extra newlines and write naturally like a human.
"""

    async def generate_response(self, prompt: str) -> LLMResponse:
        """Send prompt to Ollama and get response"""
        try:
            url = f"{self.base_url}/api/generate"
            payload = {
                "model": self.model,
                "prompt": prompt,
                "system": self.system_prompt,
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