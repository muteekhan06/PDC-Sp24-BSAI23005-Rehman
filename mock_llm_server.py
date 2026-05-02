"""
Mock LLM server used for the live demo.

Modes:
  healthy - responds in about 200 ms
  slow    - waits 8 seconds before responding
  down    - returns a 500 error
"""

import asyncio

import uvicorn
from fastapi import FastAPI, HTTPException


mock_app = FastAPI(title="Mock LLM API")
SERVICE_STATE = {"mode": "healthy"}


@mock_app.post("/llm/generate")
async def generate(payload: dict):
    prompt = payload.get("prompt", "")

    if SERVICE_STATE["mode"] == "healthy":
        await asyncio.sleep(0.2)
        return {
            "response": (
                f"Here is a study guide for: {prompt}. "
                "Key ideas include distributed systems, fault tolerance, and CAP."
            )
        }

    if SERVICE_STATE["mode"] == "slow":
        await asyncio.sleep(8)
        return {"response": "This response was delayed by the mock LLM."}

    raise HTTPException(status_code=500, detail="LLM service is down")


@mock_app.post("/control")
async def set_mode(payload: dict):
    mode = payload.get("mode", "healthy")
    if mode not in {"healthy", "slow", "down"}:
        raise HTTPException(status_code=400, detail="Invalid mode")

    SERVICE_STATE["mode"] = mode
    return {"status": f"LLM mode set to {mode}"}


@mock_app.get("/status")
async def status():
    return {"mode": SERVICE_STATE["mode"]}


if __name__ == "__main__":
    print("=" * 50)
    print("Mock LLM Server starting on port 8100")
    print("Modes: healthy | slow | down")
    print('Control: POST /control {"mode": "..."}')
    print("=" * 50)
    uvicorn.run(mock_app, host="0.0.0.0", port=8100)
