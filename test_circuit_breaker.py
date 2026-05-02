"""
Live demo script for the circuit breaker.

Run this after starting both servers:
  1. python mock_llm_server.py
  2. uvicorn app.main:app --port 8000
  3. python test_circuit_breaker.py
"""

import asyncio
import time

import httpx


STUDYSYNC_URL = "http://localhost:8000"
MOCK_LLM_URL = "http://localhost:8100"

GREEN = "\033[92m"
RED = "\033[91m"
YELLOW = "\033[93m"
CYAN = "\033[96m"
BOLD = "\033[1m"
RESET = "\033[0m"


def header(text: str) -> None:
    print(f"\n{BOLD}{CYAN}{'=' * 60}")
    print(f"  {text}")
    print(f"{'=' * 60}{RESET}\n")


def print_result(label: str, data: dict, elapsed_ms: int) -> None:
    source = data.get("source", "?")
    state = data.get("circuit_state", "?")
    color = GREEN if source == "llm" else YELLOW if source == "fallback" else RED
    print(
        f"  {color}[{label}]{RESET} "
        f"source={color}{source}{RESET} | "
        f"circuit={state} | "
        f"time={elapsed_ms}ms"
    )


async def set_llm_mode(client: httpx.AsyncClient, mode: str) -> None:
    await client.post(f"{MOCK_LLM_URL}/control", json={"mode": mode})
    print(f"  Mock LLM mode: {mode}")


async def ask_llm(
    client: httpx.AsyncClient,
    prompt: str,
    label: str,
    use_naive: bool = False,
) -> dict | None:
    endpoint = "/llm/ask-naive" if use_naive else "/llm/ask"
    start = time.time()

    try:
        response = await client.post(
            f"{STUDYSYNC_URL}{endpoint}",
            json={"prompt": prompt},
            timeout=65.0,
        )
        elapsed_ms = int((time.time() - start) * 1000)
        data = response.json()
        print_result(label, data, elapsed_ms)

        student_id = response.headers.get("X-Student-ID", "MISSING")
        print(f"    X-Student-ID: {student_id}")
        return data
    except Exception as exc:
        elapsed_ms = int((time.time() - start) * 1000)
        print(f"  {RED}[{label}] failed after {elapsed_ms}ms: {exc}{RESET}")
        return None


async def show_circuit(client: httpx.AsyncClient) -> None:
    response = await client.get(f"{STUDYSYNC_URL}/circuit-status")
    data = response.json()
    print(
        f"  Circuit state: {data['state']} | "
        f"failures: {data['fail_counter']}/{data['fail_max']}"
    )


async def run_demo() -> None:
    async with httpx.AsyncClient() as client:
        header("PHASE 0: BEFORE FIX - NAIVE ENDPOINT")
        await set_llm_mode(client, "slow")
        print("  Calling the unprotected endpoint. It waits on the slow LLM.")
        await ask_llm(client, "Explain the CAP theorem", "naive", use_naive=True)

        header("PHASE 1: NORMAL CASE - LLM HEALTHY")
        await set_llm_mode(client, "healthy")
        await asyncio.sleep(0.5)
        await show_circuit(client)
        await ask_llm(client, "Give me a study tip", "healthy-1")
        await ask_llm(client, "Explain distributed systems", "healthy-2")

        header("PHASE 2: AFTER FIX - LLM DOWN")
        await set_llm_mode(client, "down")
        print("  Sending failures until the breaker opens.")
        for index in range(5):
            await ask_llm(client, f"Failure test {index + 1}", f"failure-{index + 1}")
            await asyncio.sleep(0.2)

        await show_circuit(client)

        print("\n  Circuit is open now, so the next calls return fallback immediately.")
        await ask_llm(client, "Fast fallback please", "fast-fallback-1")
        await ask_llm(client, "Another fallback", "fast-fallback-2")

        header("PHASE 3: RECOVERY")
        await set_llm_mode(client, "healthy")
        print("  Waiting 16 seconds for the breaker reset timeout.")
        await asyncio.sleep(16)
        await ask_llm(client, "Recovery test", "recovery")
        await show_circuit(client)

        header("DEMO COMPLETE")
        print(f"  {GREEN}The protected endpoint stays responsive and returns fallback answers.{RESET}")


if __name__ == "__main__":
    asyncio.run(run_demo())
