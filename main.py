from fastapi import FastAPI, UploadFile, File, HTTPException, WebSocket

from azure.cognitiveservices.speech import SpeechConfig, SpeechRecognizer, AudioConfig
# from azure.cognitiveservices.speech.audio import AudioInputStream, PullAudioInputStreamCallback
from azure.cognitiveservices.speech.audio import  AudioInputStream, AudioConfig, PullAudioInputStreamCallback, PullAudioInputStream
from fastapi.responses import JSONResponse
from fastapi.middleware.cors import CORSMiddleware
import tempfile
import os
import io
import wave
import base64
import asyncio
from dotenv import load_dotenv
load_dotenv()
# Initialize FastAPI app
app = FastAPI()


# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Update with specific domains in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Azure STT configuration
SPEECH_KEY = os.getenv("SPEECH_KEY")
SERVICE_REGION = os.getenv("SERVICE_REGION")
speech_config = SpeechConfig(subscription=SPEECH_KEY, region=SERVICE_REGION)

# API for speech-to-text from audio file
@app.post("/stt/audio-file")
async def speech_to_text_audio_file(file: UploadFile = File(...)):
    try:
        # Save uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            temp_file.write(await file.read())
            temp_file_path = temp_file.name

        # Configure audio input
        audio_config = AudioConfig(filename=temp_file_path)
        recognizer = SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

        # Recognize speech
        result = recognizer.recognize_once()

        # Clean up temp file
        os.remove(temp_file_path)

        # Handle recognition result
        if result.reason == 0:
            return JSONResponse(status_code=400, content={"error": "Speech could not be recognized."})
        return {"text": result.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# API for speech-to-text from microphone (streaming)
@app.post("/stt/microphone")
async def speech_to_text_microphone():
    try:
        # Configure audio input from the default microphone
        audio_config = AudioConfig(use_default_microphone=True)
        recognizer = SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

        # Perform speech recognition
        print("Speak into your microphone...")
        result = recognizer.recognize_once()

        # Handle recognition result
        if result.reason == 0:
            return JSONResponse(status_code=400, content={"error": "Speech could not be recognized."})
        return {"text": result.text}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

# Custom audio stream class
class AudioStreamCallback(PullAudioInputStreamCallback):
    def __init__(self):
        super().__init__()
        self.audio_buffer = io.BytesIO()

    def read(self, buffer: memoryview) -> int:
        try:
            data = self.audio_buffer.read(buffer.nbytes)
            buffer[:len(data)] = data
            return len(data)
        except Exception as e:
            print(f"Error reading audio buffer: {e}")
            return 0

    def close(self) -> None:
        self.audio_buffer.close()

    def add_data(self, audio_data: bytes):
        position = self.audio_buffer.tell()
        self.audio_buffer.seek(0, io.SEEK_END)
        self.audio_buffer.write(audio_data)
        self.audio_buffer.seek(position)

# WebSocket endpoint for live transcription
@app.websocket("/ws/stt")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    
    stream_callback = AudioStreamCallback()
    stream = AudioInputStream(stream_callback)
    audio_config = AudioConfig(stream=stream)
    speech_recognizer = SpeechRecognizer(speech_config=speech_config, audio_config=audio_config)

    def handle_result(evt):
        if evt.result.text:
            asyncio.create_task(websocket.send_json({
                "type": "final",
                "text": evt.result.text
            }))

    speech_recognizer.recognized.connect(handle_result)

    try:
        while True:
            data = await websocket.receive_text()
            
            # Skip the "data:audio/wav;base64," prefix
            if 'base64,' in data:
                audio_data = base64.b64decode(data.split('base64,')[1])
                stream_callback.add_data(audio_data)
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        speech_recognizer.stop_continuous_recognition()
        await websocket.close()

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)