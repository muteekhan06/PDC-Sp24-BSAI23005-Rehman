"""
Circuit Breaker wrapper for the external LLM API.

This is the code fix for Problem 3. The naive version waits on the external
LLM with a long timeout. The protected version fails fast, opens the circuit
after repeated failures, and returns a fallback answer while the LLM is down.
"""

import logging
import time
from datetime import timedelta

import httpx
from aiobreaker import CircuitBreaker, CircuitBreakerError


logger = logging.getLogger("studysync.llm")

LLM_API_URL = "http://localhost:8100/llm/generate"
LLM_TIMEOUT_SECONDS = 5
BREAKER_FAIL_MAX = 3
BREAKER_RESET_TIMEOUT = timedelta(seconds=15)

llm_circuit_breaker = CircuitBreaker(
    fail_max=BREAKER_FAIL_MAX,
    timeout_duration=BREAKER_RESET_TIMEOUT,
    name="LLM-Service-Breaker",
)

FALLBACK_RESPONSES = {
    "default": (
        "I'm sorry, the AI study assistant is temporarily unavailable. "
        "Here are some general study tips while we reconnect:\n\n"
        "1. Break your study sessions into 25-minute focused blocks.\n"
        "2. Use active recall instead of only re-reading.\n"
        "3. Teach the concept to someone else.\n"
        "4. Review your notes within 24 hours."
    ),
}


def get_fallback_response(prompt: str) -> str:
    """Return a static fallback when the LLM is unreachable."""
    return FALLBACK_RESPONSES["default"]


def get_circuit_state() -> str:
    """Return a simple circuit state string for API responses."""
    state_name = type(llm_circuit_breaker.state).__name__
    if "Closed" in state_name:
        return "closed"
    if "Half" in state_name:
        return "half-open"
    if "Open" in state_name:
        return "open"
    return state_name


async def _raw_llm_call(prompt: str) -> str:
    """Make the actual HTTP request to the external LLM API."""
    async with httpx.AsyncClient(timeout=LLM_TIMEOUT_SECONDS) as client:
        response = await client.post(LLM_API_URL, json={"prompt": prompt})
        response.raise_for_status()
        data = response.json()
        return data.get("response", data.get("text", str(data)))


async def call_llm_with_breaker(prompt: str) -> dict:
    """Call the LLM through the circuit breaker and return a safe result."""
    start = time.time()

    try:
        answer = await llm_circuit_breaker.call_async(_raw_llm_call, prompt)
        elapsed = int((time.time() - start) * 1000)

        logger.info("LLM call succeeded in %sms", elapsed)
        return {
            "answer": answer,
            "source": "llm",
            "circuit_state": get_circuit_state(),
            "duration_ms": elapsed,
            "status": "success",
        }

    except CircuitBreakerError:
        elapsed = int((time.time() - start) * 1000)
        logger.warning("Circuit open, returning fallback in %sms", elapsed)
        return {
            "answer": get_fallback_response(prompt),
            "source": "fallback",
            "circuit_state": get_circuit_state(),
            "duration_ms": elapsed,
            "status": "circuit_open",
        }

    except Exception as exc:
        elapsed = int((time.time() - start) * 1000)
        logger.error("LLM call failed: %s (%sms)", type(exc).__name__, elapsed)
        return {
            "answer": get_fallback_response(prompt),
            "source": "fallback",
            "circuit_state": get_circuit_state(),
            "duration_ms": elapsed,
            "status": "failure",
        }


async def call_llm_naive(prompt: str) -> dict:
    """
    Broken version used for the demo. It has no circuit breaker and waits up
    to 60 seconds for the external LLM.
    """
    start = time.time()
    try:
        async with httpx.AsyncClient(timeout=60.0) as client:
            response = await client.post(LLM_API_URL, json={"prompt": prompt})
            response.raise_for_status()
            data = response.json()
            elapsed = int((time.time() - start) * 1000)
            return {
                "answer": data.get("response", str(data)),
                "source": "llm",
                "circuit_state": "none",
                "duration_ms": elapsed,
                "status": "success",
            }
    except Exception as exc:
        elapsed = int((time.time() - start) * 1000)
        return {
            "answer": f"ERROR: {exc}",
            "source": "error",
            "circuit_state": "none",
            "duration_ms": elapsed,
            "status": "failure",
        }
