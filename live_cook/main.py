
import asyncio
import os
import json
import base64
from fastapi import FastAPI, WebSocket, Request, WebSocketDisconnect
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from google import genai
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# --- Configuration ---
API_KEY = os.environ.get("GOOGLE_API_KEY")

if not API_KEY:
    print("Error: GOOGLE_API_KEY not found in environment variables or .env file.")

# fallback to flash-exp but allow override
MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.0-flash-exp-image-generation")

app = FastAPI()
templates = Jinja2Templates(directory="live_cook/templates")

# Initialize client only if key is present to avoid crash at import time, 
# though we might want to crash early if no key.
try:
    client = genai.Client(api_key=API_KEY, http_options={'api_version': 'v1alpha'})
except Exception as e:
    client = None
    print(f"Failed to initialize GenAI client: {e}")

@app.get("/", response_class=HTMLResponse)
async def get(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    if not client:
        await websocket.close(code=1011, reason="Server configuration error: Missing API Key")
        return

    config = {
        "response_modalities": ["AUDIO"],
        "system_instruction": "You are a helpful assistant. If you see an image, describe it briefly. If you hear audio, acknowledge it."
    }
    
    try:
        async with client.aio.live.connect(model=MODEL, config=config) as session:
            print("Connected to Gemini Live API")
            
            # Helper to receive from frontend and send to Gemini
            async def receive_from_frontend():
                try:
                    while True:
                        data = await websocket.receive_json()
                        
                        if "realtime_input" in data:
                            for chunk in data["realtime_input"]["media_chunks"]:
                                if chunk["mime_type"] == "audio/pcm":
                                    audio_bytes = base64.b64decode(chunk["data"])
                                    await session.send(input={"data": audio_bytes, "mime_type": "audio/pcm"}, end_of_turn=chunk.get("end_of_turn", False))
                                elif chunk["mime_type"] == "image/jpeg":
                                    image_bytes = base64.b64decode(chunk["data"])
                                    await session.send(input={"data": image_bytes, "mime_type": "image/jpeg"}, end_of_turn=True)
                except WebSocketDisconnect:
                    print("Frontend disconnected")
                except Exception as e:
                    print(f"Error receiving from frontend: {e}")

            # Helper to receive from Gemini and send to frontend
            async def receive_from_gemini():
                try:
                    async for response in session.receive():
                        if response.server_content is None:
                            continue

                        model_turn = response.server_content.model_turn
                        if model_turn:
                            for part in model_turn.parts:
                                if part.inline_data:
                                    # Send audio back to frontend
                                    await websocket.send_json({
                                        "audio": base64.b64encode(part.inline_data.data).decode("utf-8")
                                    })
                except Exception as e:
                    print(f"Error receiving from Gemini: {e}")

            # Run both tasks
            await asyncio.gather(receive_from_frontend(), receive_from_gemini())
            
    except Exception as e:
        print(f"Gemini Connection Error: {e}")
        safe_reason = f"Gemini Error: {str(e)}"
        await websocket.close(code=1011, reason=safe_reason[:100])

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
