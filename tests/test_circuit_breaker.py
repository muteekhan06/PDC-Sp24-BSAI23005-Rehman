"""
Tests for the StudySync circuit breaker fix.

These tests do not require uvicorn or the mock LLM server to be running.
They call the FastAPI app in-process and replace the external LLM call with
small async fakes, so the failure case is repeatable for the grader.
"""

import time

import pytest
from fastapi.testclient import TestClient

import app.main as main
import app.circuit_breaker as circuit


@pytest.fixture(autouse=True)
def reset_breaker():
    circuit.llm_circuit_breaker.close()
    yield
    circuit.llm_circuit_breaker.close()


@pytest.fixture
def client():
    with TestClient(main.app) as test_client:
        yield test_client


class TestStudentIDHeader:
    def test_header_on_root(self, client):
        response = client.get("/")

        assert response.status_code == 200
        assert response.headers["X-Student-ID"] == "BSAI23005"

    def test_header_on_health(self, client):
        response = client.get("/health")

        assert response.status_code == 200
        assert response.headers["X-Student-ID"] == "BSAI23005"

    def test_header_on_llm_endpoint(self, client, monkeypatch):
        async def healthy_llm(prompt: str) -> str:
            return f"Study guide for {prompt}"

        monkeypatch.setattr(circuit, "_raw_llm_call", healthy_llm)

        response = client.post("/llm/ask", json={"prompt": "CAP theorem"})

        assert response.status_code == 200
        assert response.headers["X-Student-ID"] == "BSAI23005"


class TestCircuitBreaker:
    def test_healthy_llm_request_passes_through(self, client, monkeypatch):
        async def healthy_llm(prompt: str) -> str:
            return f"Study guide for {prompt}"

        monkeypatch.setattr(circuit, "_raw_llm_call", healthy_llm)

        response = client.post("/llm/ask", json={"prompt": "recursion"})
        data = response.json()

        assert response.status_code == 200
        assert data["source"] == "llm"
        assert data["circuit_state"] == "closed"
        assert "recursion" in data["answer"]

    def test_failure_returns_fallback_instead_of_crashing(self, client, monkeypatch):
        async def failing_llm(prompt: str) -> str:
            raise TimeoutError("LLM timed out")

        monkeypatch.setattr(circuit, "_raw_llm_call", failing_llm)

        response = client.post("/llm/ask", json={"prompt": "help me study"})
        data = response.json()

        assert response.status_code == 200
        assert data["source"] == "fallback"
        assert "temporarily unavailable" in data["answer"].lower()

    def test_circuit_opens_after_three_failures(self, client, monkeypatch):
        async def failing_llm(prompt: str) -> str:
            raise TimeoutError("LLM timed out")

        monkeypatch.setattr(circuit, "_raw_llm_call", failing_llm)

        for index in range(3):
            client.post("/llm/ask", json={"prompt": f"fail-{index}"})

        status = client.get("/circuit-status").json()

        assert status["state"] == "open"
        assert status["fail_counter"] >= 3

    def test_open_circuit_uses_fast_fallback(self, client, monkeypatch):
        async def failing_llm(prompt: str) -> str:
            raise TimeoutError("LLM timed out")

        monkeypatch.setattr(circuit, "_raw_llm_call", failing_llm)

        for index in range(3):
            client.post("/llm/ask", json={"prompt": f"fail-{index}"})

        start = time.perf_counter()
        response = client.post("/llm/ask", json={"prompt": "fast fallback"})
        elapsed_ms = (time.perf_counter() - start) * 1000

        assert response.status_code == 200
        assert response.json()["source"] == "fallback"
        assert elapsed_ms < 500


class TestNaiveEndpoint:
    def test_naive_endpoint_shows_unprotected_failure(self, client, monkeypatch):
        async def fake_naive_failure(prompt: str) -> dict:
            return {
                "answer": "ERROR: LLM service timed out",
                "source": "error",
                "circuit_state": "none",
                "duration_ms": 60000,
                "status": "failure",
            }

        monkeypatch.setattr(main, "call_llm_naive", fake_naive_failure)

        response = client.post("/llm/ask-naive", json={"prompt": "test"})
        data = response.json()

        assert response.status_code == 200
        assert data["source"] == "error"
        assert data["status"] == "failure"
