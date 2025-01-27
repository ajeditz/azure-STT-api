import azure.cognitiveservices.speech as speechsdk
from fastapi import FastAPI, WebSocket
from fastapi.responses import HTMLResponse
import uvicorn
import asyncio
import os
from dotenv import load_dotenv
load_dotenv()

app = FastAPI()

key=os.getenv("SPEECH_KEY")
region=os.getenv("SERVICE_REGION")

# Azure Speech SDK configuration
speech_config = speechsdk.SpeechConfig(subscription=key, region=region)

@app.get("/")
async def get():
    return HTMLResponse(open("static/index.html").read())

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    stream = speechsdk.audio.PushAudioInputStream()
    audio_config = speechsdk.audio.AudioConfig(stream=stream)
    recognizer = speechsdk.SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    loop = asyncio.get_event_loop()

    def result_callback(evt):
        if evt.result.text:
            loop.create_task(websocket.send_json({"transcription": evt.result.text}))

    recognizer.recognized.connect(result_callback)
    recognizer.start_continuous_recognition()

    try:
        while True:
            data = await websocket.receive_bytes()
            stream.write(data)
    except Exception as e:
        print(f"Connection closed: {e}")
    finally:
        recognizer.stop_continuous_recognition()
        await websocket.close()


if __name__ == "__main__":
    uvicorn.run(app, host="0.0.0.0", port=8000)
