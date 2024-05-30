import io
import base64
import requests
import openai  # Ensure you have the correct OpenAI client library

def play_audio_from_stream_s(full_response):
    url = "https://api.openai.com/v1/audio/speech"
    headers = {
        "Authorization": f"Bearer {openai.api_key}",
        "Content-Type": "application/json",
    }
    data = {
        "model": "tts-1-hd",
        "voice": "nova",
        "input": full_response,
    }

    response = requests.post(url, headers=headers, json=data)
    print(response)

play_audio_from_stream_s("Hello, how are you?")