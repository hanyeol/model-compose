from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
import asyncio
import aiohttp

app = FastAPI()

@app.post("/process")
async def process_request(request: Request):
    """
    Accepts a request with data and callback URL.
    Returns immediately and sends result to callback URL after processing.
    """
    body = await request.json()

    data = body.get("data", "")
    callback_url = body.get("callback_url")
    task_id = body.get("task_id", "unknown")

    # Return immediate response
    response = {
        "task_id": task_id
    }

    # Start background processing
    if callback_url:
        asyncio.create_task(process_and_callback(task_id, data, callback_url))

    return JSONResponse(content=response)

async def process_and_callback(task_id: str, data: str, callback_url: str):
    """Process data and send callback"""
    try:
        # Simulate processing delay
        await asyncio.sleep(1)

        # Process data
        result = {
            "task_id": task_id,
            "result": {
                "processed_data": data.upper(),
                "length": len(data)
            }
        }

        # Send callback
        async with aiohttp.ClientSession() as session:
            async with session.post(callback_url, json=result) as response:
                await response.text()

    except Exception as e:
        print(f"Error: {e}")
