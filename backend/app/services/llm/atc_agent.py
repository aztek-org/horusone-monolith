"""LangChain + Ollama integration for ATC agent."""

import logging
from typing import Optional

from langchain_community.llms import Ollama

from app.config import get_settings
from app.services.llm.prompts import get_atc_prompt

logger = logging.getLogger(__name__)


class ATCAgent:
    """Air Traffic Controller agent powered by LangChain and Ollama."""

    def __init__(self) -> None:
        """Initialize the ATC agent with Ollama LLM."""
        self.settings = get_settings()
        self.llm = Ollama(
            base_url=self.settings.ollama_base_url,
            model=self.settings.ollama_llm_model,
            temperature=0.7,
        )
        self.conversation_history: list[dict[str, str]] = []
        logger.info(
            f"ATC Agent initialized with model: {self.settings.ollama_llm_model}"
        )

    async def generate_response(
        self,
        pilot_message: str,
        context: Optional[dict] = None,
        language: str = "en",
    ) -> str:
        """Generate an ATC response to a pilot transmission.

        Args:
            pilot_message: The transcribed pilot message
            context: Optional flight context information
            language: Language code (en or es)

        Returns:
            ATC response text
        """
        try:
            # Build the prompt with context and language
            full_prompt = get_atc_prompt(pilot_message, context, language)

            # Generate response using Ollama
            response = await self.llm.ainvoke(full_prompt)

            # Clean up the response
            atc_response = self._clean_response(response)

            # Store in conversation history
            self.conversation_history.append(
                {
                    "pilot": pilot_message,
                    "atc": atc_response,
                    "language": language,
                }
            )

            logger.info(f"Generated ATC response ({language}): {atc_response}")
            return atc_response

        except Exception as e:
            logger.error(f"Error generating ATC response: {e}")
            # Fallback response based on language
            if language == "es":
                return "Repita, transmisión no clara."
            return "Say again, transmission unclear."

    def _clean_response(self, response: str) -> str:
        """Clean and format the ATC response.

        Args:
            response: Raw LLM response

        Returns:
            Cleaned response text
        """
        # Remove any extra whitespace
        cleaned = " ".join(response.strip().split())

        # Remove common prefixes if present
        prefixes_to_remove = [
            "ATC:",
            "Tower:",
            "Approach:",
            "Ground:",
            "Response:",
        ]

        for prefix in prefixes_to_remove:
            if cleaned.startswith(prefix):
                cleaned = cleaned[len(prefix) :].strip()

        return cleaned

    def reset_conversation(self) -> None:
        """Reset the conversation history."""
        self.conversation_history = []
        logger.info("Conversation history reset")

    def get_conversation_history(self) -> list[dict[str, str]]:
        """Get the conversation history.

        Returns:
            List of conversation exchanges
        """
        return self.conversation_history
