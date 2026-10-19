from __future__ import annotations

import json
import logging
from typing import Any, Literal

import httpx
from pydantic import BaseModel, Field, ValidationError

from app.config import settings
from app.services.memory_service import (
    VALID_MEMORY_TYPES,
    get_customer_context_snapshot,
    upsert_customer_memory,
)


logger = logging.getLogger(__name__)


MemoryType = Literal[
    "product_interest",
    "occasion_context",
    "communication_style",
    "fabric_or_style_note",
    "other",
]


class DurableMemoryFact(BaseModel):
    memory_type: MemoryType

    memory_key: str = Field(
        min_length=1,
        max_length=120,
    )

    memory_value: Any

    confidence: float = Field(
        ge=0.0,
        le=1.0,
    )

    reason: str | None = Field(
        default=None,
        max_length=300,
    )


class MemoryExtractionResult(BaseModel):
    facts: list[DurableMemoryFact] = Field(
        default_factory=list
    )

MEMORY_KEY_ALIASES = {
    "fabric_preference":
        "preferred_material",

    "material_preference":
        "preferred_material",

    "favorite_material":
        "preferred_material",

    "preferred_fabric":
        "preferred_material",

    "size_preference":
        "usual_size",

    "preferred_size":
        "usual_size",

    "usual_clothing_size":
        "usual_size",

    "category_preference":
        "preferred_category",

    "favorite_category":
        "preferred_category",

    "current_occasion":
        "shopping_occasion",

    "occasion":
        "shopping_occasion",

    "preferred_store":
        "preferred_branch",

    "usual_branch":
        "preferred_branch",

    "recommendation_style":
        "communication_style",
}

class MemoryAgent:
    """
    Memory & Context Agent.

    Responsibilities:
    - load durable customer context at the start of a new conversation
    - use the local Ollama LLM to extract durable facts from conversation history
    - validate every extracted fact before storage
    - persist durable facts through the service-role memory RPC
    - finalize a conversation when the customer leaves it

    The LLM never receives direct database access.
    """

    agent_key = "memory_context"

    def load_context(
        self,
        customer_id: str,
    ) -> dict:
        return get_customer_context_snapshot(
            customer_id
        )

    def finalize_conversation(
        self,
        customer_id: str,
        conversation_id: str,
    ) -> list[dict]:
        """
        Extract and persist durable customer facts when a conversation
        is explicitly left.

        Repeated finalization is idempotent at the application level,
        while the database also deduplicates memories by memory_key.
        """

        from app.services import chat_service

        state = (
            chat_service
            .get_conversation_state(
                customer_id,
                conversation_id,
            )
        )

        if state.get("memory_finalized"):
            return []

        messages = (
            chat_service
            .list_recent_messages(
                customer_id,
                conversation_id,
                limit=100,
            )
        )

        if not messages:
            chat_service.merge_conversation_state(
                customer_id,
                conversation_id,
                {
                    "memory_finalized": True,
                    "memory_fact_count": 0,
                },
            )

            return []

        stored = self.persist_durable_facts(
            customer_id,
            conversation_id,
            messages,
        )

        chat_service.merge_conversation_state(
            customer_id,
            conversation_id,
            {
                "memory_finalized": True,
                "memory_fact_count": len(stored),
            },
        )

        return stored

    def _build_transcript(
        self,
        messages: list[dict],
    ) -> str:
        lines: list[str] = []

        for message in messages:
            role = str(
                message.get(
                    "role",
                    "",
                )
            ).strip()

            content = str(
                message.get(
                    "content",
                    "",
                )
            ).strip()

            if not role or not content:
                continue

            if role not in {
                "user",
                "assistant",
            }:
                continue

            speaker = (
                "CUSTOMER"
                if role == "user"
                else "ASSISTANT"
            )

            lines.append(
                f"{speaker}: {content}"
            )

        return "\n".join(lines)

    def _build_prompt(
        self,
        transcript: str,
    ) -> str:
        return f"""
You are the Memory & Context Agent for Retailigent,
an intelligent clothing retail assistant.

Your job is to extract only DURABLE customer facts
that may genuinely help in a future conversation.

Allowed memory types:
- product_interest
- occasion_context
- communication_style
- fabric_or_style_note
- other

Good memories include:
- preferred clothing materials
- recurring style preferences
- usual clothing size when explicitly stated
- shopping for a specific future occasion
- preferred store branch
- recurring product interests
- communication style preferences

Do NOT remember:
- passwords
- payment card information
- CVV or PIN
- authentication tokens
- one-time cart actions
- temporary stock levels
- temporary prices
- order IDs
- exact purchase transaction details
- facts inferred only from the assistant's words
- uncertain guesses
- information the customer did not state or clearly imply
- short-lived operational details

Important rules:
1. Extract facts only from CUSTOMER messages.
2. Do not invent anything.
3. Use stable snake_case memory_key values.
4. Confidence must be between 0 and 1.
5. Prefer fewer, high-quality durable facts.
6. Return an empty facts list when there is nothing worth remembering.
7. Do not duplicate the same fact under multiple keys.
8. memory_value must contain the actual fact, not an explanation of the fact.

Examples:

Customer:
"I normally wear medium."

Possible fact:
memory_type: other
memory_key: usual_size
memory_value: "M"

Customer:
"I prefer cotton kurtas over synthetic ones."

Possible fact:
memory_type: fabric_or_style_note
memory_key: preferred_material
memory_value: "cotton"

Customer:
"I am shopping for my sister's wedding in December."

Possible fact:
memory_type: occasion_context
memory_key: shopping_occasion
memory_value:
{{
  "occasion": "sister's wedding",
  "timeframe": "December"
}}

Now analyze this conversation:

{transcript}
""".strip()

    def _call_ollama(
        self,
        prompt: str,
    ) -> MemoryExtractionResult:
        endpoint = (
            settings.ollama_url.rstrip("/")
            + "/api/generate"
        )

        payload = {
            "model": settings.ollama_llm_model,
            "prompt": prompt,
            "stream": False,
            "think": False,
            "keep_alive": settings.ollama_keep_alive,
            "format": MemoryExtractionResult.model_json_schema(),
            "options": {
                "temperature": 0,
                "num_predict": 384,
            },
        }

        timeout = httpx.Timeout(
            settings.ollama_llm_timeout_seconds
        )

        try:
            response = httpx.post(
                endpoint,
                json=payload,
                timeout=timeout,
            )

            response.raise_for_status()

        except httpx.HTTPError as exc:
            logger.exception(
                "Ollama memory extraction request failed"
            )

            raise RuntimeError(
                "Local memory model request failed."
            ) from exc

        data = response.json()

        raw_response = str(
            data.get(
                "response",
                "",
            )
        ).strip()

        if not raw_response:
            return MemoryExtractionResult()

        try:
            parsed_json = json.loads(
                raw_response
            )

            return (
                MemoryExtractionResult
                .model_validate(
                    parsed_json
                )
            )

        except (
            json.JSONDecodeError,
            ValidationError,
        ) as exc:
            logger.warning(
                "Memory model returned invalid structured output: %s",
                raw_response,
            )

            raise RuntimeError(
                "Local memory model returned invalid structured output."
            ) from exc

    def extract_durable_facts(
        self,
        messages: list[dict],
    ) -> list[DurableMemoryFact]:
        transcript = self._build_transcript(
            messages
        )

        if not transcript:
            return []

        prompt = self._build_prompt(
            transcript
        )

        result = self._call_ollama(
            prompt
        )

        validated: list[
            DurableMemoryFact
        ] = []

        seen_keys: set[str] = set()

        for fact in result.facts:
            memory_key = (
                fact.memory_key
                .strip()
                .lower()
                .replace(
                    " ",
                    "_",
                )
            )

            if not memory_key:
                continue

            memory_key = (
                MEMORY_KEY_ALIASES.get(
                    memory_key,
                    memory_key,
                )
            )

            if (
                fact.memory_type
                not in VALID_MEMORY_TYPES
            ):
                continue

            if memory_key in seen_keys:
                continue

            seen_keys.add(
                memory_key
            )

            validated.append(
                fact.model_copy(
                    update={
                        "memory_key": memory_key,
                    }
                )
            )

        return validated

    def persist_durable_facts(
        self,
        customer_id: str,
        conversation_id: str,
        messages: list[dict],
    ) -> list[dict]:
        facts = self.extract_durable_facts(
            messages
        )

        stored: list[dict] = []

        for fact in facts:
            memory_id = upsert_customer_memory(
                customer_id,
                memory_type=fact.memory_type,
                memory_key=fact.memory_key,
                memory_value=fact.memory_value,
                confidence=fact.confidence,
                source_conversation_id=conversation_id,
            )

            stored.append(
                {
                    "id": memory_id,
                    "memory_type": fact.memory_type,
                    "memory_key": fact.memory_key,
                    "memory_value": fact.memory_value,
                    "confidence": fact.confidence,
                }
            )

        return stored


memory_agent = MemoryAgent()