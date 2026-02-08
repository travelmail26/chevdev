
import asyncio
import websockets
import json
import base64
import numpy as np
from PIL import Image
import io

# Audio constants
SAMPLE_RATE = 16000
DURATION = 1.0  # seconds
FREQUENCY = 440.0  # Hz

def generate_audio_pcm():
    """Generates 1 second of 440Hz sine wave PCM data."""
    t = np.linspace(0, DURATION, int(SAMPLE_RATE * DURATION), False)
    # Generate sine wave
    audio = np.sin(FREQUENCY * 2 * np.pi * t)
    # Convert to 16-bit PCM
    audio = (audio * 32767).astype(np.int16)
    return base64.b64encode(audio.tobytes()).decode('utf-8')

def generate_red_image():
    """Generates a 640x480 red JPEG image."""
    img = Image.new('RGB', (640, 480), color = 'red')
    buf = io.BytesIO()
    img.save(buf, format='JPEG')
    return base64.b64encode(buf.getvalue()).decode('utf-8')

async def test_live_feed():
    uri = "ws://localhost:8000/ws"
    
    print(f"Connecting to {uri}...")
    try:
        async with websockets.connect(uri) as websocket:
            print("Connected.")
            
            # 1. Send Image
            print("Sending simulated Video (Red Image)...")
            img_data = generate_red_image()
            await websocket.send(json.dumps({
                "realtime_input": {
                    "media_chunks": [{
                        "mime_type": "image/jpeg",
                        "data": img_data
                    }]
                }
            }))
            
            print("Waiting for image response...")
            await asyncio.sleep(5)

            # Send Text Message
            print("Sending Text Message 'Hello'...")
            await websocket.send(json.dumps({
                "realtime_input": {
                    "media_chunks": [{
                        "mime_type": "text/plain",
                        "data": "Hello, are you there?",
                        "end_of_turn": True
                    }]
                }
            }))
            
            # 3. Listen for response
            print("Listening for response...")
            chunks_received = 0
            try:
                while chunks_received < 5: # Listen for a few chunks of audio response
                    message = await asyncio.wait_for(websocket.recv(), timeout=10.0)
                    response = json.loads(message)
                    
                    if "audio" in response:
                        print(f"Received Audio Chunk {chunks_received + 1} ({len(response['audio'])} bytes)")
                        chunks_received += 1
                    else:
                        print("Received non-audio message:", response)
                        
                print("SUCCESS: Received audio response from Gemini!")
                
            except asyncio.TimeoutError:
                print("FAILURE: Timed out waiting for response.")
            except Exception as e:
                print(f"FAILURE: Error receiving message: {e}")

    except Exception as e:
        print(f"FAILURE: Could not connect or send data: {e}")

if __name__ == "__main__":
    asyncio.run(test_live_feed())
