from math import fabs
import streamlit as st

import os
import io
import asyncio
import re
import mysql
import uuid
import aiohttp
import base64

import soundfile as sf
import sounddevice as sd
from PIL import Image
from docx import Document
import pandas as pd
import PyPDF2
from openai import OpenAI

from myfunc.various_tools import work_vars

if 'prompt' not in st.session_state:
    st.session_state.prompt = ''
api_key=os.getenv("OPENAI_API_KEY")
client=OpenAI()

# read docx file
def read_docx(file):
                doc = Document(file)
                full_text = []
                for para in doc.paragraphs:
                    full_text.append(para.text)
                text_data = '\n'.join(full_text)
                st.write(text_data)
                return text_data

# read txt file
def read_txt(file):
    txt_data = file.getvalue().decode("utf-8")
    with st.expander("Prikaži tekst"):
        st.write(txt_data)
    return 

# read csv file
def read_csv(file):
    csv_data = pd.read_csv(file)
    with st.expander("Prikaži CSV podatke"):
        st.write(csv_data)
    csv_content = csv_data.to_string()
    return csv_content

# read pdf file
def read_pdf(file):
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

# read image file
def read_image(file):
    base64_image = base64.b64encode(file.getvalue()).decode('utf-8')
    image_bytes = base64.b64decode(base64_image)
    image = Image.open(io.BytesIO(image_bytes))
    with st.expander("Prikaži sliku"):
        st.image(image, width=150)
    return f"data:image/jpeg;base64,{base64_image}"

# Upload file and return the content and type of the file
def read_file():
    uploaded_file = st.file_uploader("🗀 Odaberite dokument", key="dokument_", help="Odabir dokumenta")
    if uploaded_file is not None:
        if uploaded_file.name.endswith(".docx"):
            # Read the DOCX file and convert it to a string
            docx_text = read_docx(uploaded_file)
            return docx_text, "tekst"
        elif uploaded_file.name.endswith((".txt", ".me", ".py", ".json", "yaml")):
            # Read the TXT file and convert it to a string
            txt_text = read_txt(uploaded_file)
            return txt_text, "tekst"
        elif uploaded_file.name.endswith(".csv"):
            # Read the CSV file and convert it to a pandas DataFrame
            csv_df = read_csv(uploaded_file)
            return csv_df, "tekst"
        elif uploaded_file.name.endswith(".pdf"):
            # Read the PDF file and convert it to a string
            pdf_text = read_pdf(uploaded_file)
            return pdf_text, "tekst"
        elif uploaded_file.name.endswith((".jpg", ".jpeg", ".png", ".webp")):
            # Read the image file and convert it to a string
            image_data = read_image(uploaded_file)
            return image_data, "slika"
        else:
            st.error("❌ Greška! Odabrani dokument nije podržan.")
            return False, False 
    return False, False

############### pocetak Async funkcija #####################  

async def suggest_questions(system_message, user_message, api_key):
    
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json"
    }
    async with aiohttp.ClientSession() as session:
        response = await session.post(
            url="https://api.openai.com/v1/chat/completions",
            headers=headers,
            json={
                "model": work_vars["names"]["openai_model"],
                "messages": [system_message, user_message],
            },
        )
        data = await response.json()
        odgovor = data['choices'][0]['message']['content']
        return odgovor

# Function to fetch spoken response from API
async def fetch_spoken_response(client, full_response, api_key):
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

# Function to play audio from stream
async def play_audio_from_stream(spoken_response):
    buffer = io.BytesIO(spoken_response)
    buffer.seek(0)

    with sf.SoundFile(buffer, 'r') as sound_file:
        data = sound_file.read(dtype='int16')
        sd.play(data, sound_file.samplerate)
        sd.wait()

# Function to handle async tasks
async def handle_async_tasks(client, user_message, full_response, api_key):
    # Fetch spoken response and suggestions concurrently
    audio_data, odgovor = await asyncio.gather(
        fetch_spoken_response(client, user_message, full_response, api_key),
        suggest_questions(system_message=system_message, user_message=user_message, api_key=api_key),
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
    await play_audio_from_stream(audio_data)
    
# Function to process the request
def process_request(client, full_prompt, full_response, api_key):
    # Schedule async tasks
    asyncio.run(handle_async_tasks(client, full_prompt, full_response, api_key))
    
############### kraj Async funkcija #####################

def create_system_message(language="Serbian"):
    return {
        "role": "system",
        "content": f"Use only the {language} language"           
            f"You are an AI language model assistant for a company's chatbot. Your task is to generate "
            f"3 different possible continuation sentences that a user might say based on the given context. "
            f"These continuations should be in the form of questions or statements that naturally follow from "
            f"the conversation.\n\n"
            f"Your goal is to help guide the user through the Q&A process by predicting their next possible inputs. "
            f"Ensure these continuations are from the user's perspective and relevant to the context provided.\n\n"
            f"Provide these sentences separated by newlines, without numbering.\n\n"
            f"Original context:\n"
    }

language = "Serbian"
system_message = create_system_message(language)

def play_audio_from_stream_s(full_response):
    spoken_response = client.audio.speech.create(
        model="tts-1-hd",
        voice="nova",
        input=full_response,
    )
    # Read the content to get the bytes
    #from pydub.generators import Sine
    
    # buffer = io.BytesIO()
    # audio_segment.export(buffer, format="wav")
    
    spoken_response_bytes = spoken_response.read()

    buffer = io.BytesIO(spoken_response_bytes)
    buffer.seek(0)
    buffer = io.BytesIO(spoken_response_bytes)
    buffer.seek(0)

    # Encode the audio as base64 to embed it in HTML
    audio_base64 = base64.b64encode(buffer.read()).decode()

    # Create an HTML audio element with autoplay
    audio_html =  f"""
<audio autoplay style="display:none;">
    <source src="data:audio/wav;base64,{audio_base64}" type="audio/wav">
    Your browser does not support the audio element.
</audio>
"""

    # Display the HTML element in the Streamlit app
    st.markdown(audio_html, unsafe_allow_html=True)
    
    # with sf.SoundFile(buffer, 'r') as sound_file:
    #     data = sound_file.read(dtype='int16')
    #     sd.play(data, sound_file.samplerate)
    #     sd.wait()
    
def suggest_questions_s(system_message, user_message): # sync version of suggested questions (async) from myfunc
    
    response = client.chat.completions.create(
                    model=work_vars["names"]["openai_model"],
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
    
