Mutee ur Rehman - BSAI23005

# PDC Assignment 2: Building Resilient Distributed Systems

This repository is my submission for the Parallel and Distributed Computing assignment. I implemented Problem 3, Fault Tolerance, using a Circuit Breaker around the external LLM API.

The required custom header is included in every FastAPI response:

```http
X-Student-ID: BSAI23005
```

## What is implemented

- FastAPI backend for the StudySync scenario.
- Circuit Breaker for the LLM endpoint in `app/circuit_breaker.py`.
- Fallback response when the LLM is slow or down.
- A broken naive endpoint for the before/after demo.
- `X-Student-ID` middleware in `app/main.py`.
- Pytest tests that prove the circuit breaker and header work.
- PDF report covering Parts 1 and 2.

## Project structure

```text
app/
  main.py                  FastAPI app and middleware
  circuit_breaker.py       Circuit Breaker implementation
  database.py              SQLite setup
  models.py                SQLAlchemy models
  schemas.py               Pydantic schemas
tests/
  test_circuit_breaker.py  Automated tests
mock_llm_server.py         Mock external LLM service for live demo
test_circuit_breaker.py    Demo script for video recording
PDC_Assignment2_Report.pdf Written report
requirements.txt
README.md
```

## How to run

Install dependencies:

```bash
pip install -r requirements.txt
```

Run the automated tests:

```bash
pytest tests/ -v
```

Run the live demo:

Terminal 1:

```bash
python mock_llm_server.py
```

Terminal 2:

```bash
uvicorn app.main:app --reload --port 8000
```

Terminal 3:

```bash
python test_circuit_breaker.py
```

## Main endpoints

```text
GET  /                    App status
GET  /health              Health check
GET  /circuit-status      Circuit breaker status
POST /llm/ask             Protected LLM endpoint
POST /llm/ask-naive       Broken endpoint for demo
POST /documents           Create document
GET  /documents/{id}      Read document
PUT  /documents/{id}      Update document with version check
```

## Verify the required header

```bash
curl -i http://localhost:8000/
```

Expected header:

```http
X-Student-ID: BSAI23005
```
