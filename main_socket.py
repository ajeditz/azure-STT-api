from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
import socketio
import azure.cognitiveservices.speech as speechsdk
from datetime import datetime
import os
import asyncio
from dotenv import load_dotenv

load_dotenv()

class bcolors:
    HEADER = '\033[95m'
    OKBLUE = '\033[94m'
    OKCYAN = '\033[96m'
    OKGREEN = '\033[92m'
    WARNING = '\033[93m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'
    BOLD = '\033[1m'
    UNDERLINE = '\033[4m'

app = FastAPI()
sio = socketio.AsyncServer(
    async_mode='asgi',
    cors_allowed_origins='*',
    logger=True,
    engineio_logger=True,
    ping_timeout=60,
    ping_interval=25,
)
socket_app = socketio.ASGIApp(sio, app)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

speech_key = os.getenv("SPEECH_KEY")
speech_region = os.getenv("SERVICE_REGION")
run_as_process=os.getenv("RUN_AS_PROCESS")

async def create_speech_recognizer(client_sid):
    """Creates and configures the speech recognizer"""
    speech_config = speechsdk.SpeechConfig(
        subscription=speech_key,
        region=speech_region
    )

    format = speechsdk.audio.AudioStreamFormat(
        compressed_stream_format=speechsdk.AudioStreamContainerFormat.ANY
    )
    stream = speechsdk.audio.PushAudioInputStream(format)
    audio_config = speechsdk.audio.AudioConfig(stream=stream)

    speech_recognizer = speechsdk.SpeechRecognizer(
        speech_config=speech_config,
        audio_config=audio_config,
        language="en-US"
    )

    # Create an async queue for recognition results
    result_queue = asyncio.Queue()

    def recognized_cb(evt: speechsdk.SpeechRecognitionEventArgs):
        text = evt.result.text
        print(f"{bcolors.OKGREEN}Azure Speech Recognition -> Recognized: {text}{bcolors.ENDC}")
        asyncio.create_task(result_queue.put(text))

    def recognizing_cb(evt: speechsdk.SpeechRecognitionEventArgs):
        print(f"{bcolors.OKGREEN}Azure Speech Recognition -> Recognizing: {evt.result.text}{bcolors.ENDC}")

    def stop_cb(evt: speechsdk.SessionEventArgs):
        print(f"{bcolors.WARNING}Azure Speech Recognition -> Session stopped: {evt}{bcolors.ENDC}")

    def canceled_cb(evt: speechsdk.SessionEventArgs):
        print(f"{bcolors.FAIL}Azure Speech Recognition -> Session canceled: {evt}{bcolors.ENDC}")

    speech_recognizer.recognizing.connect(recognizing_cb)
    speech_recognizer.recognized.connect(recognized_cb)
    speech_recognizer.session_stopped.connect(stop_cb)
    speech_recognizer.canceled.connect(canceled_cb)

    return speech_recognizer, stream, result_queue

# Store client-specific recognizers and streams
clients = {}

@sio.event
async def connect(sid, environ):
    print(f"{bcolors.OKBLUE}Socket.IO -> Client connected: {sid}{bcolors.ENDC}")

@sio.event
async def disconnect(sid):
    print(f"{bcolors.OKBLUE}Socket.IO -> Client disconnected: {sid}{bcolors.ENDC}")
    if sid in clients:
        recognizer, stream, audio_data = clients[sid]
        stream.close()
        recognizer.stop_continuous_recognition()

        if run_as_process:
            audio_file_path=f"records/received_audio_{datetime.now()}.webm"
        else:
            # In your Python code
            audio_file_path = f"/tmp/received_audio_{datetime.now()}.webm"
        
        # Save the audio file
        with open(audio_file_path, "wb") as f:
            f.write(audio_data)
        
        del clients[sid]

@sio.event
async def start_recognition(sid):
    """Initialize speech recognition for a client"""
    recognizer, stream, result_queue = await create_speech_recognizer(sid)
    clients[sid] = (recognizer, stream, b"", result_queue)
    recognizer.start_continuous_recognition()
    print(f"{bcolors.OKGREEN}Socket.IO -> Started recognition for client: {sid}{bcolors.ENDC}")
    
    # Start background task to process recognition results
    asyncio.create_task(process_recognition_results(sid, result_queue))

async def process_recognition_results(sid, result_queue):
    """Process recognition results and emit to client"""
    try:
        while True:
            text = await result_queue.get()
            print(f"Processing recognized text: {text}")
            await sio.emit('transcription', {'text': text}, room=sid)
            print(f"Emitted text to client {sid}: {text}")
    except Exception as e:
        print(f"Error processing recognition results: {e}")


@sio.event
async def audio_data(sid, data):
    """Handle incoming audio data"""
    try:
        if sid in clients:
            recognizer, stream, audio_data, result_queue = clients[sid]
            if isinstance(data, str):
                data = data.encode()
            
            clients[sid] = (recognizer, stream, audio_data + data, result_queue)
            stream.write(data)
            print(f"{bcolors.OKCYAN}Socket.IO -> Processed audio data: {len(data)} bytes{bcolors.ENDC}")
    except Exception as e:
        print(f"Error processing audio data: {e}")
        await sio.emit('error', {'message': str(e)}, room=sid)

        
# Mount the Socket.IO app
app.mount("/", socket_app)