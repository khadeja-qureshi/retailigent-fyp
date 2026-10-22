from __future__ import annotations

import re
from typing import Any


_NEGATIVE_TERMS = (
    "angry", "awful", "bad", "broken", "complain",
    "disappointed", "disgusted", "failed", "fraud",
    "hate", "late", "lost", "missing", "never arrived",
    "not received", "poor", "refund", "ridiculous",
    "scam", "terrible", "unacceptable", "wrong",
    "masla", "maslay", "naraz", "shikayat", "pareshan",
    "late hai", "nahi mila", "nahi ayi", "nahi aya",
    "refund chahiye", "bohat bura",
)

_POSITIVE_TERMS = (
    "amazing", "excellent", "good", "great", "happy",
    "helpful", "love it", "perfect", "thank you",
    "thanks", "shukriya", "bohat acha", "bohat achi",
)

_URGENT_TERMS = (
    "urgent", "immediately", "asap", "chargeback",
    "charged twice", "double charged", "payment fraud",
    "safety issue", "unsafe", "legal action",
)

_HIGH_PRIORITY_TERMS = (
    "still not received", "multiple times", "third time",
    "second time", "very disappointed", "extremely angry",
    "refund", "wrong item", "damaged", "missing order",
)


def _contains_phrase(text: str, phrases: tuple[str, ...]) -> bool:
    normalized = text.casefold()
    return any(phrase in normalized for phrase in phrases)


def _short(value: Any, limit: int = 240) -> str:
    if value is None:
        return ""
    if isinstance(value, (dict, list)):
        value = str(value)
    return " ".join(str(value).split())[:limit]


class SupportAgent:
    """Prepare safe support responses and human-handoff context."""

    agent_key = "support"

    def detect_sentiment(self, message: str) -> str:
        text = message.strip().casefold()
        negative = _contains_phrase(text, _NEGATIVE_TERMS)
        positive = _contains_phrase(text, _POSITIVE_TERMS)

        if negative:
            return "negative"
        if positive:
            return "positive"
        return "neutral"

    def determine_priority(self, message: str, sentiment: str) -> str:
        text = message.strip().casefold()

        if _contains_phrase(text, _URGENT_TERMS):
            return "urgent"

        if (
            _contains_phrase(text, _HIGH_PRIORITY_TERMS)
            or (sentiment == "negative" and
                _contains_phrase(text, ("angry", "unacceptable", "fraud")))
        ):
            return "high"

        if sentiment == "negative":
            return "high"

        return "normal"

    def answer_faq(self, message: str) -> str | None:
        """Answer only safe general questions; never invent store policy."""
        text = message.strip().casefold()

        if re.search(r"\b(contact|human|agent|representative|support team)\b", text):
            return (
                "I can help route your concern to the support team. "
                "If your issue needs account-specific investigation, "
                "I'll prepare a ticket for a team member."
            )

        if re.search(r"\b(return policy|refund policy|exchange policy|return window)\b", text):
            return (
                "Return, refund, and exchange eligibility depends on the "
                "applicable store policy and order details. I don't want "
                "to give you an unverified answer, so the support team "
                "can confirm the policy for your case."
            )

        if re.search(r"\b(where is my order|track my order|order status)\b", text):
            return (
                "I can help route an order-status question to support. "
                "A team member may need to verify your order details "
                "before confirming its status."
            )

        return None

    def prepare_escalation(
        self,
        *,
        message: str,
        language: str = "english",
        customer_context: dict[str, Any] | None = None,
        recent_messages: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        clean_message = " ".join(message.split())[:4000]
        context = customer_context or {}
        history = recent_messages or []

        sentiment = self.detect_sentiment(clean_message)
        priority = self.determine_priority(clean_message, sentiment)

        normalized = clean_message[:180]
        subject = f"Support request: {normalized}"[:200]

        history_lines: list[str] = []
        for item in history[-8:]:
            role = _short(item.get("role"), 24)
            content = _short(item.get("content"), 320)
            if role and content:
                history_lines.append(f"{role}: {content}")

        open_tickets = context.get("open_support_tickets") or []
        ticket_lines: list[str] = []
        for ticket in open_tickets[:5]:
            if not isinstance(ticket, dict):
                continue
            ticket_lines.append(
                "Ticket "
                + _short(ticket.get("id"), 80)
                + " | status: "
                + _short(ticket.get("status"), 40)
                + " | priority: "
                + _short(ticket.get("priority"), 40)
                + " | subject: "
                + _short(ticket.get("subject"), 160)
            )

        facts = context.get("remembered_facts") or []
        fact_lines: list[str] = []
        for fact in facts[:5]:
            if not isinstance(fact, dict):
                continue
            key = _short(fact.get("memory_key"), 80)
            value = _short(fact.get("memory_value"), 160)
            if key and value:
                fact_lines.append(f"{key}: {value}")

        summary_parts = [
            f"Customer issue: {clean_message}",
            f"Detected sentiment: {sentiment}",
            f"Suggested priority: {priority}",
        ]

        if history_lines:
            summary_parts.append(
                "Recent conversation:\n" + "\n".join(history_lines)
            )
        if ticket_lines:
            summary_parts.append(
                "Existing open support tickets:\n"
                + "\n".join(ticket_lines)
            )
        if fact_lines:
            summary_parts.append(
                "Relevant remembered context:\n"
                + "\n".join(fact_lines)
            )

        handoff_summary = "\n\n".join(summary_parts)[:4000]

        if language == "roman_urdu":
            response = (
                "Samajh gaya/gayi. Main aapki baat support team ko "
                "bhejne ke liye ticket tayyar kar raha/rahi hoon."
            )
        else:
            response = (
                "I'm sorry you're having to deal with this. I'll pass "
                "the details to our support team so they can investigate."
                if sentiment == "negative"
                else
                "I'll pass the details to our support team so they can "
                "review your request."
            )

        return {
            "subject": subject,
            "description": clean_message,
            "sentiment": sentiment,
            "priority": priority,
            "handoff_summary": handoff_summary,
            "agent_context": {
                "source": "support_agent",
                "sentiment": sentiment,
                "priority": priority,
                "language": language,
                "open_support_ticket_count": len(open_tickets),
                "recent_message_count": len(history),
            },
            "response": response,
            "should_escalate": True,
        }


support_agent = SupportAgent()
