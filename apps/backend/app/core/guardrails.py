import re
from typing import List, Dict

from fastapi import HTTPException, status
from app.core.logging import logger_adapter


# ---------------------------------------------------------------------------
# 1. Prompt injection patterns
# ---------------------------------------------------------------------------
_INJECTION_PATTERNS = [
    r"ignore\s+(all\s+)?(previous|prior|above|earlier|system)\s+(instructions?|prompts?|context|rules?|constraints?)",
    r"forget\s+(everything|all|what\s+you|your\s+previous)",
    r"disregard\s+(your|all|the\s+(above|previous|system))",
    r"override\s+(your\s+)?(instructions?|system|rules?|behaviour)",
    r"you\s+are\s+now\s+(a\s+|an\s+)?(?!helpful)",   # "you are now a [different persona]"
    r"pretend\s+(you\s+are|to\s+be|that\s+you)",
    r"act\s+as\s+(if\s+you('re|\s+are)|a\s+|an\s+)",
    r"(jailbreak|dan\s+mode|developer\s+mode|god\s+mode|unrestricted\s+mode)",
    r"new\s+(system\s+)?instructions?\s*:",
    r"your\s+(real|true|actual)\s+(purpose|goal|mission|instructions?)\s+is",
    r"(respond|reply|answer)\s+(without|ignoring)\s+(restrictions?|filters?|guidelines?|rules?)",
    r"\[INST\]|<\|im_start\|>|<\|im_end\|>|<<SYS>>",   # raw prompt delimiters
    r"do\s+anything\s+now",
]

# ---------------------------------------------------------------------------
# 2. Harmful / off-topic content patterns
# ---------------------------------------------------------------------------
_HARMFUL_PATTERNS = [
    r"\b(how\s+to\s+(make|build|create|synthesize)\s+(bomb|weapon|explosive|poison|virus|malware|ransomware))\b",
    r"\b(suicide|self[- ]harm)\s+(method|guide|how|way|instruction)\b",
    r"\b(child\s+(porn|abuse|exploit))\b",
    r"\b(hack|crack|exploit)\s+(into|the|a)\s+\w+\s+(system|server|database|account)\b",
]

# ---------------------------------------------------------------------------
# 3. Jailbreak success indicators in LLM output
# ---------------------------------------------------------------------------
_OUTPUT_COMPROMISE_PATTERNS = [
    r"i('m|\s+am)\s+now\s+(free(d)?|unlocked|unrestricted|without\s+(restrictions?|filters?))",
    r"(as\s+)?(dan|dude|evil\s+bot|unrestricted\s+ai|jailbroken\s+(ai|model))",
    r"i\s+(no\s+longer|don't|do\s+not)\s+(have|follow|obey)\s+(any\s+)?(restrictions?|guidelines?|rules?|filters?)",
    r"my\s+(true|real|actual)\s+(self|purpose|goal|instructions?)\s+is",
    r"ignore\s+(all\s+)?previous\s+instructions",   # echo of injection in output
]


def check_prompt_injection(text: str) -> None:
    """Raise 400 if the query looks like a prompt injection attempt."""
    for pattern in _INJECTION_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            logger_adapter.warning("Prompt injection attempt detected", query_preview=text[:80])
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query contains disallowed instructions.",
            )


def check_harmful_content(text: str) -> None:
    """Raise 400 if the query contains clearly harmful content."""
    for pattern in _HARMFUL_PATTERNS:
        if re.search(pattern, text, re.IGNORECASE):
            logger_adapter.warning("Harmful content detected in query", query_preview=text[:80])
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Query contains disallowed content.",
            )


def validate_llm_output(response: str, sources: List[Dict]) -> str:
    """
    Two checks on the LLM output:
    1. If no sources were retrieved, override with a standard "no context" message
       regardless of what the LLM said — prevents hallucination when context is empty.
    2. If the response itself contains jailbreak-success language, reject it.
    """
    # Check 1 — no retrieved context → must not answer from memory
    if not sources:
        logger_adapter.info("No sources retrieved; overriding LLM response")
        return (
            "I could not find relevant information in the available documents "
            "to answer this question. Please try rephrasing, or upload a document "
            "that covers this topic."
        )

    # Check 2 — LLM output shows signs of compromise
    for pattern in _OUTPUT_COMPROMISE_PATTERNS:
        if re.search(pattern, response, re.IGNORECASE):
            logger_adapter.warning("Potentially compromised LLM output detected")
            return (
                "I was unable to generate a safe response for this query. "
                "Please rephrase your question."
            )

    return response
