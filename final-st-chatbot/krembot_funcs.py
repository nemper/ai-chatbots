import aiohttp
import asyncio
import base64
import io
import pandas as pd
import PyPDF2
import re
import soundfile as sf
import streamlit as st
import uuid

from docx import Document
from openai import OpenAI, APIConnectionError, APIError, RateLimitError
from os import getenv


client = OpenAI(api_key=getenv("OPENAI_API_KEY"))


def check_openai_errors(main_function):
    try:
        main_function()
    except RateLimitError as e:
        if 'insufficient_quota' in str(e):
            st.warning("Potrošili ste sve tokene, kontaktirajte Positive za dalja uputstva")
            # Additional handling, like notifying the user or logging the error
        else:
            st.warning(f"Greška {str(e)}")
    except APIConnectionError as e:
        # Handle connection error here
        st.warning(f"Ne mogu da se povežem sa OpenAI API-jem: {e} pokušajte malo kasnije.")
    except APIError as e:
        # Handle API error here, e.g. retry or log
        st.warning(f"Greška u API-ju: {e} pokušajte malo kasnije.")
    except Exception as e:
        # Handle other exceptions
        st.warning(f"Greška : {str(e)} pokušajte malo kasnije.")


def initialize_session_state(defaults):
    for key, value in defaults.items():
        if key not in st.session_state:
            if callable(value):
                # ako se dodeljuje npr. funkcija
                st.session_state[key] = value()
            else:
                st.session_state[key] = value


class FileReader:
    def __init__(self):
        self.documents = {}

    def read_docx(self, file):
        doc = Document(file)
        full_text = [para.text for para in doc.paragraphs]
        text_data = '\n'.join(full_text)
        st.write(text_data)
        return text_data

    def read_txt(self, file):
        txt_data = file.getvalue().decode("utf-8")
        with st.expander("Prikaži tekst"):
            st.write(txt_data)
        return txt_data

    def read_csv(self, file):
        csv_data = pd.read_csv(file)
        with st.expander("Prikaži CSV podatke"):
            st.write(csv_data)
        csv_content = csv_data.to_string()
        return csv_content

    def read_pdf(self, file):
        pdf_reader = PyPDF2.PdfReader(file)
        num_pages = len(pdf_reader.pages)
        text_content = ""

        for page in range(num_pages):
            page_obj = pdf_reader.pages[page]
            text_content += page_obj.extract_text()

        # Remove bullet points and fix space issues
        text_content = text_content.replace("•", "")
        text_content = re.sub(r"(?<=\b\w) (?=\w\b)", "", text_content)
        with st.expander("Prikaži tekst"):
            st.write(text_content)
        return text_content

    def read_files(self):
        uploaded_files = st.file_uploader("Choose file(s)", accept_multiple_files=True)
        if uploaded_files:
            for file in uploaded_files:
                filename = file.name
                if filename.endswith('.txt') or filename.endswith('.js') or filename.endswith('.py') or filename.endswith('.md'):
                    self.documents[filename] = self.read_txt(file)
                elif filename.endswith('.docx'):
                    self.documents[filename] = self.read_docx(file)
                elif filename.endswith('.pdf'):
                    self.documents[filename] = self.read_pdf(file)
                elif filename.endswith('.csv'):
                    self.documents[filename] = self.read_csv(file)
                else:
                    st.error("❌ Greška! Mora slika!")
                    return False, False

            pairs = [f"{key}: \n{value}" for key, value in self.documents.items()]
            return '\n\n'.join(pairs), True
        return False, False


def callback():
    if st.session_state.my_recorder_output:
        return st.session_state.my_recorder_output['bytes']
    

async def fetch_spoken_response(client, user_message, full_response, api_key):
    async with aiohttp.ClientSession() as session:
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json"
        }
        response = await session.post(
            url="https://api.openai.com/v1/audio/speech",
            headers=headers,
            json={"model": "tts-1-hd", "voice": "nova", "input": full_response},
        )

        if response.status != 200:
            raise Exception(f"API request failed with status {response.status}")

        audio_data = await response.read()
        return audio_data


async def suggest_questions(prompt, api_key=getenv("OPENAI_API_KEY")):
    system_message = {
        "role": "system",
        "content": f"Use only the Serbian language"
    }
    user_message = {
        "role": "user",
        "content": f"""You are an AI language model assistant for a company's chatbot. Your task is to generate 3 different possible continuation sentences that a user might say based on the given context. These continuations should be in the form of questions or statements that naturally follow from the conversation.

                    Your goal is to help guide the user through the Q&A process by predicting their next possible inputs. Ensure these continuations are from the user's perspective and relevant to the context provided.

                    Provide these sentences separated by newlines, without numbering.

                    Original context:
                    {prompt}
                    """
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    async with aiohttp.ClientSession() as session:
        response = await session.post(
            url="https://api.openai.com/v1/chat/completions",
            headers=headers,
            json={
                "model": getenv("OPENAI_MODEL"),
                "messages": [system_message, user_message],
            },
        )
        data = await response.json()
        odgovor = data['choices'][0]['message']['content']
        return odgovor


async def handle_async_tasks(client, user_message, full_response, api_key):
    # Fetch spoken response and suggestions concurrently
    audio_data, odgovor = await asyncio.gather(
        fetch_spoken_response(client, user_message, full_response, api_key),
        suggest_questions(prompt=user_message, api_key=api_key),
    )
    
    try:
        questions = odgovor.split('\n')
    except:
        questions = []

    # Create buttons for each question
    st.caption("Predložena pitanja/odgovori:")
    for question in questions:
        if len(question) > 10:
            st.button(question, on_click=handle_question_click, args=(question,), key=uuid.uuid4())

    # Update session state with the selected question
    if 'selected_question' in st.session_state:
        st.session_state.prompt = st.session_state.selected_question
        st.session_state['selected_question'] = None
    
    # Get the audio data and samplerate
    audio_base64, samplerate = play_audio_from_stream(audio_data)
    
    # Display the audio in the Streamlit app
    st.audio(f"data:audio/wav;base64,{audio_base64}", format="audio/wav")


def play_audio_from_stream22(spoken_response):
    """
    Reads audio data from a spoken response stream and returns it as a base64-encoded string.

    Parameters:
    - spoken_response: A stream of audio data.

    Returns:
    - A base64-encoded string of the audio data.
    """
    buffer = io.BytesIO()
    for chunk in spoken_response.iter_bytes(chunk_size=4096):
        buffer.write(chunk)
    buffer.seek(0)

    with sf.SoundFile(buffer, 'r') as sound_file:
        data = sound_file.read(dtype='int16')
        samplerate = sound_file.samplerate

    # Create a new buffer to save the audio in WAV format
    wav_buffer = io.BytesIO()
    with sf.SoundFile(wav_buffer, 'w', samplerate=samplerate, channels=1, format='WAV') as wav_file:
        wav_file.write(data)


    # Encode the WAV data to base64
    wav_buffer.seek(0)
    audio_base64 = base64.b64encode(wav_buffer.read()).decode('utf-8')

    return audio_base64, samplerate


def play_audio_from_stream(spoken_response):
    """
    Reads audio data from a spoken response and returns it as a base64-encoded string.

    Parameters:
    - spoken_response: A bytes object containing the audio data.

    Returns:
    - A base64-encoded string of the audio data.
    """
    buffer = io.BytesIO(spoken_response)  # Directly pass the bytes object to BytesIO
    buffer.seek(0)

    with sf.SoundFile(buffer, 'r') as sound_file:
        data = sound_file.read(dtype='int16')
        samplerate = sound_file.samplerate

    # Create a new buffer to save the audio in WAV format
    wav_buffer = io.BytesIO()
    with sf.SoundFile(wav_buffer, 'w', samplerate=samplerate, channels=1, format='WAV') as wav_file:
        wav_file.write(data)

    # Encode the WAV data to base64
    wav_buffer.seek(0)
    audio_base64 = base64.b64encode(wav_buffer.read()).decode('utf-8')

    return audio_base64, samplerate


def process_request(client, full_prompt, full_response, api_key):
    # Schedule async tasks
    asyncio.run(handle_async_tasks(client, full_prompt, full_response, api_key))


system_message = {
        "role": "system",
        "content": f"Use only the Serbian language"           
            f"You are an AI language model assistant for a company's chatbot. Your task is to generate "
            f"3 different possible continuation sentences that a user might say based on the given context. "
            f"These continuations should be in the form of questions or statements that naturally follow from "
            f"the conversation.\n\n"
            f"Your goal is to help guide the user through the Q&A process by predicting their next possible inputs. "
            f"Ensure these continuations are from the user's perspective and relevant to the context provided.\n\n"
            f"Provide these sentences separated by newlines, without numbering.\n\n"
            f"Original context:\n"}


def suggest_questions_s(system_message, user_message): # sync version of suggested questions (async) from myfunc
    
    response = client.chat.completions.create(
                    model=getenv("OPENAI_MODEL"),
                    messages=[system_message, user_message],
                    )
               
    odgovor =  response.choices[0].message.content
    return odgovor


def handle_question_click(question):
    """Set the selected question in the session state."""
    st.session_state.selected_question = question


def predlozeni_odgovori(user_message):
    
    odgovor=suggest_questions_s(system_message=system_message, user_message=user_message)
    try:
        questions = odgovor.split('\n')
    except:
        questions = []

    # Create buttons for each question
    st.caption("Predložena pitanja/odgovori:")
    for question in questions:
        if len(question) > 10:
            st.button(question, on_click=handle_question_click, args=(question,), key=uuid.uuid4())
        # Display the selected question
        st.session_state.prompt = st.session_state.selected_question
        st.session_state['selected_question'] = None


def play_audio_from_stream_s(full_response):
    spoken_response = client.audio.speech.create(
        model="tts-1-hd",
        voice="nova",
        input=full_response,
    )
    spoken_response_bytes = spoken_response.read()
    buffer = io.BytesIO(spoken_response_bytes)
    buffer.seek(0)
    audio_base64 = base64.b64encode(buffer.read()).decode()
    set_html_audio(audio_base64)


def set_html_audio(audio_base64):
    # Create an HTML audio element with autoplay
    opcija = st.query_params.get('opcija', "mobile")
    if opcija == "mobile":
        audio_html = f"""
            <audio controls autoplay>
                <source src="data:audio/wav;base64,{audio_base64}" type="audio/wav">
                Your browser does not support the audio element.
            </audio>
            """
    else:
        audio_html =  f"""
            <audio autoplay style="display:none;">
                <source src="data:audio/wav;base64,{audio_base64}" type="audio/wav">
                Your browser does not support the audio element.
            </audio>
            """
     # Display the HTML element in the Streamlit app
    st.markdown(audio_html, unsafe_allow_html=True)