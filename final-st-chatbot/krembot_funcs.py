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
from typing import List, Dict, Any, Tuple, Union, Optional, Callable

client = OpenAI(api_key=getenv("OPENAI_API_KEY"))


def check_openai_errors(main_function: Callable[[], Any]) -> None:
    """
    Executes the provided main function and handles OpenAI-related errors gracefully.

    This function attempts to run the given `main_function`. If an OpenAI API-related error occurs,
    such as rate limiting (`RateLimitError`), connection issues (`APIConnectionError`), or other API
    errors (`APIError`), it catches the exception and displays an appropriate warning message using
    Streamlit's `st.warning`. For any other unforeseen exceptions, it also catches them and notifies
    the user accordingly.

    Args:
        main_function (Callable[[], Any]): The function to execute within the error-handling context.

    Returns:
        None

    Raises:
        None: All exceptions are handled internally and do not propagate.
    """
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


def initialize_session_state(defaults: Dict[str, Any]) -> None:
    """
    Initializes the Streamlit session state with default values.

    This function iterates over the provided `defaults` dictionary and sets each key in the
    Streamlit `st.session_state` if it does not already exist. If a default value is callable,
    it invokes the callable and assigns its return value to the session state key. Otherwise,
    it directly assigns the provided value.

    Args:
        defaults (Dict[str, Any]): A dictionary containing default key-value pairs to initialize
                                    in the session state.

    Returns:
        None

    Raises:
        None: The function safely initializes session state without raising exceptions.
    """
    for key, value in defaults.items():
        if key not in st.session_state:
            if callable(value):
                # ako se dodeljuje npr. funkcija
                st.session_state[key] = value()
            else:
                st.session_state[key] = value

    
class FileReader:
    """
    A utility class for reading and processing various document types within a Streamlit application.

    This class provides methods to read `.docx`, `.txt`, `.csv`, and `.pdf` files. It utilizes
    Streamlit's file uploader to handle multiple file uploads and processes each file based on its
    extension. The extracted content is stored in the `documents` dictionary attribute.
    """

    def __init__(self) -> None:
        """
        Initializes the FileReader with an empty documents dictionary.

        This constructor sets up the `documents` attribute as an empty dictionary to store
        the contents of uploaded files.

        Args:
            None

        Returns:
            None
        """
        self.documents = {}

    def read_docx(self, file: Any) -> str:
        """
        Reads a `.docx` file and extracts its text content.

        This method processes a Word document by extracting text from each paragraph and
        concatenating them into a single string. The extracted text is displayed using
        Streamlit's `st.write` and returned.

        Args:
            file (Any): A file-like object representing the `.docx` file to be read.

        Returns:
            str: The extracted text content from the `.docx` file.
        """
        doc = Document(file)
        full_text = [para.text for para in doc.paragraphs]
        text_data = '\n'.join(full_text)
        st.write(text_data)
        return text_data

    def read_txt(self, file: Any) -> str:
        """
        Reads a `.txt` file and extracts its text content.

        This method decodes the uploaded text file using UTF-8 encoding, displays the content
        within an expandable section using Streamlit's `st.expander`, and returns the text.

        Args:
            file (Any): A file-like object representing the `.txt` file to be read.

        Returns:
            str: The extracted text content from the `.txt` file.
        """
        txt_data = file.getvalue().decode("utf-8")
        with st.expander("Prikaži tekst"):
            st.write(txt_data)
        return txt_data

    def read_csv(self, file: Any) -> str:
        """
        Reads a `.csv` file and extracts its content.

        This method utilizes Pandas to read the uploaded CSV file, displays the data within
        an expandable section using Streamlit's `st.expander`, converts the DataFrame to a
        string, and returns the CSV content as a string.

        Args:
            file (Any): A file-like object representing the `.csv` file to be read.

        Returns:
            str: The string representation of the CSV content.
        """
        csv_data = pd.read_csv(file)
        with st.expander("Prikaži CSV podatke"):
            st.write(csv_data)
        csv_content = csv_data.to_string()
        return csv_content

    def read_pdf(self, file: Any) -> str:
        """
        Reads a `.pdf` file and extracts its text content.

        This method processes a PDF document by extracting text from each page using PyPDF2.
        It cleans the extracted text by removing bullet points and fixing space issues, displays
        the content within an expandable section using Streamlit's `st.expander`, and returns the text.

        Args:
            file (Any): A file-like object representing the `.pdf` file to be read.

        Returns:
            str: The extracted and cleaned text content from the `.pdf` file.
        """
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

    def read_files(self) -> Tuple[Union[str, bool], bool]:
        """
        Handles the uploading and reading of multiple files.

        This method allows users to upload multiple files via Streamlit's file uploader. It iterates
        over each uploaded file, determines the file type based on its extension, and calls the
        appropriate reading method (`read_txt`, `read_docx`, `read_pdf`, or `read_csv`). The extracted
        contents are stored in the `documents` dictionary attribute. If any file has an unsupported
        extension, an error message is displayed.

        Returns:
            Tuple[Union[str, bool], bool]: 
                - The first element is a concatenated string of all extracted document contents if files are successfully read,
                  otherwise `False`.
                - The second element is a boolean indicating whether the file reading was successful (`True`) or not (`False`).
        """
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


def callback() -> Optional[bytes]:
    """
    Retrieves the byte content from the session state's recorder output.

    This function checks if the `my_recorder_output` exists in Streamlit's session state.
    If it does, it returns the 'bytes' field from the recorder output. If not, it returns `None`.

    Args:
        None

    Returns:
        Optional[bytes]: The byte content from the recorder output if available, otherwise `None`.
    """
    if st.session_state.my_recorder_output:
        return st.session_state.my_recorder_output['bytes']
    

async def fetch_spoken_response(
    client: Any,
    user_message: str,
    full_response: str,
    api_key: str
    ) -> bytes:
    """
    Fetches a spoken audio response from the OpenAI API based on the provided input.

    This asynchronous function sends a POST request to the OpenAI audio speech API endpoint with the specified
    model and voice parameters. It processes the API response and retrieves the audio data in bytes format.
    If the API request fails (i.e., returns a non-200 status code), it raises an exception with the corresponding
    status code.

    Args:
        client (Any): An instance of the client making the request (unused in the current implementation).
        user_message (str): The message from the user (unused in the current implementation).
        full_response (str): The full textual response to be converted into speech.
        api_key (str): The API key for authenticating with the OpenAI API.

    Returns:
        bytes: The audio data returned by the OpenAI API.

    Raises:
        Exception: If the API request fails with a status code other than 200.
    """
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


async def suggest_questions(
    prompt: str,
    api_key: Optional[str] = None
    ) -> str:
    """
    Generates suggested continuation questions or statements based on the provided prompt using OpenAI's Chat API.

    This asynchronous function sends a POST request to the OpenAI chat completions API endpoint with a system
    message guiding the model to generate three possible continuation sentences. The generated suggestions are
    intended to help guide the user through a Q&A process by predicting their next possible inputs.

    Args:
        prompt (str): The context or conversation history based on which suggestions are to be generated.
        api_key (Optional[str], optional): The API key for authenticating with the OpenAI API.
                                        Defaults to the 'OPENAI_API_KEY' environment variable.

    Returns:
        str: A string containing three suggested continuation sentences, separated by newlines.

    Raises:
        Exception: If the API request fails or the response format is unexpected.
    """
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


async def handle_async_tasks(
    client: Any,
    user_message: str,
    full_response: str,
    api_key: str
    ) -> None:
    """
    Handles concurrent asynchronous tasks for fetching spoken responses and suggesting questions.

    This asynchronous function concurrently executes two tasks:
        1. Fetches a spoken audio response based on the user's message and full response.
        2. Suggests possible continuation questions or statements based on the user's message.

    After fetching the responses, it processes the suggested questions by creating interactive buttons
    within a Streamlit application. When a question is selected, it updates the session state accordingly.
    Additionally, it processes the fetched audio data to be played within the Streamlit app.

    Args:
        client (Any): An instance of the client making the requests.
        user_message (str): The message from the user.
        full_response (str): The full textual response to be converted into speech.
        api_key (str): The API key for authenticating with the OpenAI API.

    Returns:
        None

    Raises:
        Exception: Propagates exceptions from the asynchronous tasks if they are not handled within them.
    """
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


def play_audio_from_stream(spoken_response: bytes) -> Tuple[str, int]:
    """
    Converts spoken audio bytes into a base64-encoded string and retrieves the sample rate.

    This function processes the audio data received as bytes, reads it using the SoundFile library to extract
    audio samples and the sample rate, and then encodes the audio into a base64 string suitable for streaming
    in a web application. It returns both the encoded audio string and the sample rate.

    Args:
        spoken_response (bytes): The raw audio data in bytes format.

    Returns:
        Tuple[str, int]: 
            - A base64-encoded string of the audio data in WAV format.
            - The sample rate of the audio data.

    Raises:
        Exception: If there is an error in processing the audio data.
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


def process_request(
    client: Any,
    full_prompt: str,
    full_response: str,
    api_key: str
    ) -> None:
    """
    Processes a user request by executing asynchronous tasks to fetch audio responses and suggest questions.

    This function orchestrates the handling of a user's request by scheduling and running asynchronous tasks
    that fetch a spoken audio response and generate suggested continuation questions. It leverages asyncio's
    event loop to execute these tasks concurrently, ensuring efficient processing and timely responses.

    Args:
        client (Any): An instance of the client handling the requests.
        full_prompt (str): The complete prompt or context based on which suggestions and audio are generated.
        full_response (str): The full textual response to be converted into speech.
        api_key (str): The API key for authenticating with the OpenAI API.

    Returns:
        None

    Raises:
        Exception: If an error occurs during the execution of asynchronous tasks.
    """
    asyncio.run(handle_async_tasks(client, full_prompt, full_response, api_key))


system_message = {
        "role": "system",
        "content":         
            f"You are an AI language model assistant for a company's chatbot. Your task is to generate "
            f"3 different possible continuation sentences that a user might say based on the given context. "
            f"These continuations should be in the form of questions or statements that naturally follow from "
            f"the conversation.\n\n"
            f"Your goal is to help guide the user through the Q&A process by predicting their next possible inputs. "
            f"Ensure these continuations are from the user's perspective and relevant to the context provided.\n\n"
            f"Provide these sentences separated by newlines, without numbering.\n\n"
            f"Original context:\n"}


def suggest_questions_s(
    system_message: Dict[str, str],
    user_message: Dict[str, str]
    ) -> str:
    """
    Generates suggested continuation questions or statements based on the provided user message.

    This function sends a chat completion request to the OpenAI API with the given system and user messages.
    It retrieves the AI-generated response, which consists of three suggested continuation sentences
    that naturally follow from the provided context.

    Args:
        system_message (Dict[str, str]): A dictionary containing the system prompt for the AI model.
                                         Typically includes instructions or context for the assistant.
        user_message (Dict[str, str]): A dictionary containing the user's message or query that the AI
                                       should respond to with suggestions.

    Returns:
        str: A string containing three suggested continuation sentences, separated by newlines.

    Raises:
        Exception: If the API request fails or the response format is unexpected.
    """
    
    response = client.chat.completions.create(
                    model=getenv("OPENAI_MODEL"),
                    messages=[system_message, user_message],
                    )
               
    odgovor =  response.choices[0].message.content
    return odgovor


def handle_question_click(question: str) -> None:
    """
    Sets the selected question in the Streamlit session state.

    This function updates the `selected_question` key in Streamlit's session state with the provided
    question. It is typically used as a callback for Streamlit button clicks to store the user's
    selected question for further processing.

    Args:
        question (str): The question or statement selected by the user via a Streamlit button.

    Returns:
        None
    """
    """Set the selected question in the session state."""
    st.session_state.selected_question = question


def predlozeni_odgovori(user_message: Dict[str, str]) -> None:
    """
    Generates and displays suggested questions or answers based on the user's message.

    This function utilizes the `suggest_questions_s` function to generate three possible continuation
    sentences that a user might say based on the provided context. It then splits the AI-generated
    suggestions into individual questions and creates interactive buttons for each. When a button is
    clicked, the selected question is stored in the session state for further use.

    Args:
        user_message (Dict[str, str]): A dictionary containing the user's message or query to which
                                       suggestions are to be generated.

    Returns:
        None
    """
    
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


def play_audio_from_stream_s(full_response: str) -> None:
    """
    Converts a textual response into spoken audio and plays it within the Streamlit app.

    This function sends the provided textual response to the OpenAI API's audio speech endpoint to
    generate spoken audio data. It then reads the returned audio bytes, encodes them in base64,
    and invokes the `set_html_audio` function to embed and play the audio within the Streamlit application.

    Args:
        full_response (str): The complete textual response that needs to be converted into spoken audio.

    Returns:
        None

    Raises:
        Exception: If the API request fails or audio processing encounters an error.
    """
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


def set_html_audio(audio_base64: str) -> None:
    """
    Embeds and plays base64-encoded audio within the Streamlit application using an HTML audio element.

    Depending on the user's device preference specified in the query parameters, this function creates
    an HTML audio element with appropriate controls and autoplay settings. The audio is either displayed
    with controls for mobile devices or hidden with autoplay for other environments.

    Args:
        audio_base64 (str): The base64-encoded string of the audio data to be played.

    Returns:
        None

    Raises:
        None: The function handles the embedding of audio without raising exceptions.
    """
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