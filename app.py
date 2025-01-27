import streamlit as st
import requests
import tempfile
import os

# API URLs
API_BASE_URL = "http://127.0.0.1:8000"
AUDIO_FILE_API = f"{API_BASE_URL}/stt/audio-file"
MICROPHONE_API = f"{API_BASE_URL}/stt/microphone"

# Streamlit app
st.title("Azure Speech-to-Text Demonstration")
st.sidebar.title("Options")
option = st.sidebar.radio("Choose Input Method", ("Audio File", "Microphone"))

if option == "Audio File":
    st.header("Speech-to-Text from Audio File")
    uploaded_file = st.file_uploader("Upload an audio file (WAV format only):", type=["wav"])

    if uploaded_file is not None:
        # Save the uploaded file temporarily
        with tempfile.NamedTemporaryFile(delete=False, suffix=".wav") as temp_file:
            temp_file.write(uploaded_file.read())
            temp_file_path = temp_file.name

        if st.button("Transcribe Audio File"):
            with open(temp_file_path, "rb") as f:
                response = requests.post(AUDIO_FILE_API, files={"file": f})

            # Clean up the temporary file
            os.remove(temp_file_path)

            if response.status_code == 200:
                st.success("Transcription Successful!")
                st.text_area("Transcribed Text:", value=response.json().get("text", ""), height=200)
            else:
                st.error(f"Error: {response.json().get('detail', 'Unknown error')}")

elif option == "Microphone":
    st.header("Speech-to-Text from Microphone")

    if st.button("Start Transcription"):
        with st.spinner("Listening... Speak now into your microphone."):
            response = requests.post(MICROPHONE_API)

        if response.status_code == 200:
            st.success("Transcription Successful!")
            st.text_area("Transcribed Text:", value=response.json().get("text", ""), height=200)
        else:
            st.error(f"Error: {response.json().get('detail', 'Unknown error')}")
