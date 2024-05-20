# in myfunc.various_tools.py
import datetime
import html
import io
import base64
import json
import logging
import openai
import os
import pandas as pd
import re
import requests
import streamlit as st
import sys
import aiohttp

from audiosegment import AudioSegment
from bs4 import BeautifulSoup
from io import StringIO
from openai import OpenAI
import sounddevice as sd
import soundfile as sf
from tqdm.auto import tqdm
from urllib.parse import urljoin, urlparse
from uuid import uuid4

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.utilities import GoogleSerperAPIWrapper

from myfunc.mojafunkcija import st_style
from myfunc.prompts import PromptDatabase
from myfunc.varvars_dicts import work_vars


# in myfunc.various_tools.py
# try:
#     x = st.session_state.choose_rag
# except:
with PromptDatabase() as db:
    prompt_map = db.get_prompts_by_names(["hyde_rag", "choose_rag"],[os.getenv("HYDE_RAG"), os.getenv("CHOOSE_RAG_KLOT")])
    # prompt_map = db.get_prompts_by_names(["hyde_rag", "choose_rag"],[os.getenv("HYDE_RAG"), os.getenv("CHOOSE_RAG")])
    st.session_state.hyde_rag = prompt_map.get("hyde_rag", "You are helpful assistant")
    st.session_state.choose_rag = prompt_map.get("choose_rag", "You are helpful assistant")
    
AZ_BLOB_API_KEY = os.getenv("AZ_BLOB_API_KEY")

st_style()
client=OpenAI()


# in myfunc.various_tools.py
class MeetingTranscriptSummarizer:
    """
    A class to summarize meeting transcripts by extracting main topics and summarizing discussions.

    This class takes a meeting transcript, temperature setting for the AI model, and the number of 
    topics to identify. It uses an AI model to extract meeting details, identify main topics, 
    summarize discussions for each topic, and generate a conclusion for the meeting.

    Attributes:
    - transcript: The full text of the meeting transcript.
    - temperature: The temperature setting for the AI model, controlling the randomness of its responses.
    - number_of_topics: The maximum number of main topics to identify in the transcript.

    Methods:
    - get_response(prompt, text): Sends a prompt and text to the AI model and returns the model's response.
    - summarize(): Extracts meeting details, identifies main topics, summarizes discussions for each topic, and generates a conclusion.
    """
    def __init__(self, transcript, temperature, number_of_topics):
        self.transcript = transcript
        self.temperature = temperature
        self.number_of_topics = number_of_topics

    def get_response(self, prompt, text):
        """
        Sends a prompt and text to the AI model and returns the model's response.

        This method uses the AI model to generate a response based on the provided prompt and text.
        
        Parameters:
        - prompt: The prompt instructing the AI on how to process the text.
        - text: The text to be processed by the AI model.

        Returns:
        - The AI model's response as a string.
        """
        response = client.chat.completions.create(
            model=work_vars["names"]["openai_model"],
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": prompt + "Use only the Serbian Language"},
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message.content

    def summarize(self):
        """
        Extracts meeting details, identifies main topics, summarizes discussions for each topic, and generates a conclusion.

        This method processes the transcript to extract the meeting date and participants, identify main topics discussed, 
        summarize each topic, and generate a conclusion for the meeting. The final summarized text is formatted and returned.
        
        Returns:
        - The full summarized text of the meeting as a string.
        """
        introduction = self.get_response("Extract the meeting date and the participants.", self.transcript)
        topic_identification_prompt = (
            f"List up to {self.number_of_topics} main topics discussed in the transcript "
            "excluding the introductory details and explanation of the topics. "
            "All remaining topics summarize in the single topic Razno."
        )
        topics = self.get_response(topic_identification_prompt, self.transcript).split('\n')
        
        st.success("Identifikovane su teme:")
        for topic in topics:
            st.success(topic)

        summaries = []
        for topic in topics:
            summary_prompt = f"Summarize the discussion on the topic: {topic}, excluding the introductory details."
            summary = self.get_response(summary_prompt, self.transcript)
            summaries.append(f"## Tema: {topic} \n{summary}")
            st.info(f"Obradjujem temu: {topic}")
        
        conclusion = self.get_response("Generate a conclusion from the whole meeting.", self.transcript)
        full_text = (
            f"## Sastanak koordinacije AI Tima\n\n{introduction}\n\n"
            f"## Teme sastanka\n\n" + "\n".join([f"{topic}" for topic in topics]) + "\n\n"
            + "\n\n".join(summaries) 
            + f"\n\n## Zaključak\n\n{conclusion}"
        )
        return full_text
    

# in myfunc.various_tools.py
class StringLogHandler(logging.Handler):
    """A custom logging handler to collect log records in a list.

    This class is primarily used for debugging and development purposes.
    """
    def __init__(self):
        super().__init__()
        self.log_records = []

    def emit(self, record):
        """Collects log records into a list.

        Args:
            record (logging.LogRecord): The log record to be collected.
        """
        log_entry = self.format(record)
        self.log_records.append(log_entry)


# in myfunc.various_tools.py
def summarize_meeting_transcript(transcript, temp, broj_tema):
    """
    Summarize a meeting transcript by first extracting the date, participants, and topics,
    and then summarizing each topic individually while excluding the introductory information
    from the summaries.

    Parameters: 
        transcript (str): The transcript of the meeting.
    Returns: full_text (str): The summarized meeting transcript.
    """

    def get_response(prompt, text, temp):
        """
        Generate a response from the model based on the given prompt and text.
        
        Parameters:
            prompt (str): The prompt to send to the model.
            text (str): The text to summarize or extract information from.
        """
        
        response = client.chat.completions.create(
            model=work_vars["names"]["openai_model"],
            temperature=temp,  
            messages=[
                {"role": "system", "content": prompt + "Use only the Serbian Language"},
                {"role": "user", "content": text}
            ]
        )
        
        return response.choices[0].message.content

    # Extract introductory details like date, participants, and a brief overview
    intro_prompt = "Extract the meeting date and the participants."
    introduction = get_response(intro_prompt, transcript, temp)

    # Identify the main topics in the transcript
    topic_identification_prompt = f"List up to {broj_tema} main topics discussed in the transcript excluding the introductory details and explanation of the topics. All remaining topics summarize in the single topic Razno."
    topics = get_response(topic_identification_prompt, transcript, temp).split('\n')
    
    st.success("Identifikovane su teme:")
    for topic in topics:
        st.success(topic)

    # Summarize each identified topic
    summaries = []
    for topic in topics:
        summary_prompt = f"Summarize the discussion on the topic: {topic}, excluding the introductory details."
        summary = get_response(summary_prompt, transcript, temp)
        summaries.append(f"## Tema: {topic} \n{summary}")
        st.info(f"Obradjujem temu: {topic}")
        
    # Optional: Generate a conclusion from the whole transcript
    conclusion_prompt = "Generate a conclusion from the whole meeting."
    conclusion = get_response(conclusion_prompt, transcript, temp)
    
    # Compile the full text
    full_text = (
    f"## Sastanak koordinacije AI Tima\n\n{introduction}\n\n"
    f"## Teme sastanka\n\n" + "\n".join([f"{topic}" for topic in topics]) + "\n\n"
    + "\n\n".join(summaries) 
    + f"\n\n## Zaključak\n\n{conclusion}"
    )
    return full_text


# in myfunc.various_tools.py
def scrape(url: str):
    """
    Scrapes the main content and local links from a given URL.

    This function sends a GET request to the specified URL, checks the response status code,
    and extracts the main content and local links from the webpage using BeautifulSoup. The main
    content is identified based on the specified CSS selector and cleaned to remove HTML tags and
    extra whitespace. Local links are collected if they point to pages within the same domain.

    Parameters:
    - url: The URL of the webpage to be scraped.

    Returns:
    - A tuple containing:
        - A dictionary with the URL and cleaned text content of the main section.
        - A list of local links found on the webpage.
      If an error occurs, None is returned.
    """
    global headers, sajt, err_log, tiktoken_len, vrsta
    # Send a GET request to the URL
    res = requests.get(url, headers=headers)

    # Check the response status code
    if res.status_code != 200:
        # If the status code is not 200 (OK), write the status code and return None
        err_log += f"{res.status_code} for {url}\n"
        return None

    # If the status code is 200, initialize BeautifulSoup with the response text
    soup = BeautifulSoup(res.text, "html.parser")
    # soup = BeautifulSoup(res.text, 'lxml')

    # Find all links to local pages on the website
    local_links = []
    for link in soup.find_all("a", href=True):
        if (
            link["href"].startswith(sajt)
            or link["href"].startswith("/")
            or link["href"].startswith("./")
        ):
            href = link["href"]
            base_url, extension = os.path.splitext(href)
            if not extension and not "mailto" in href and not "tel" in href:
          
                local_links.append(urljoin(sajt, href))

                # Find the main content using CSS selectors
                try:
                    # main_content_list = soup.select('body main')
                    main_content_list = soup.select(vrsta)

                    # Check if 'main_content_list' is not empty
                    if main_content_list:
                        main_content = main_content_list[0]

                        # Extract the plaintext of the main content
                        main_content_text = main_content.get_text()

                        # Remove all HTML tags
                        main_content_text = re.sub(r"<[^>]+>", "", main_content_text)

                        # Remove extra white space
                        main_content_text = " ".join(main_content_text.split())

                        # Replace HTML entities with their corresponding characters
                        main_content_text = html.unescape(main_content_text)

                    else:
                        # Handle the case when 'main_content_list' is empty
                        main_content_text = "error"
                        err_log += f"Error in page structure, use body instead\n"
                        st.error(err_log)
                        sys.exit()
                except Exception as e:
                    err_log += f"Error while discovering page content\n"
                    return None

    # return as json
    return {"url": url, "text": main_content_text}, local_links


# in myfunc.various_tools.py
def main_scraper(chunk_size, chunk_overlap):
    """
    Scrapes a website for text content and prepares it for embedding.

    This function uses Streamlit to create a web interface for scraping text content from a website.
    It prompts the user to enter the website URL, a text prefix, and the type of content to scrape.
    The scraped content is then split into chunks, which are prepared for embedding. The final
    data is saved as a JSON file that can be downloaded.

    Parameters:
    - chunk_size: The size of each text chunk for embedding.
    - chunk_overlap: The overlap between consecutive text chunks.

    Returns:
    - None
    """
    skinuto = False
    napisano = False
    file_name = "chunks.json"
    with st.form(key="my_form_scrape", clear_on_submit=False):
        global res, err_log, headers, sajt, source, vrsta
        st.subheader("Pinecone Scraping")
        headers = {
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.3"
        }

        # Set the domain URL

        # with st.form(key="my_form", clear_on_submit=False):
        sajt = st.text_input("Unesite sajt : ")
        # prefix moze da se definise i dinamicki
        text_prefix = st.text_input(
            "Unesite prefiks za tekst: ",
            help="Prefiks se dodaje na početak teksta pre podela na delove za indeksiranje",
        )
        vrsta = st.radio(
            "Unesite vrstu (default je body main): ", ("body main", "body")
        )
        # add_schema = st.radio(
        #     "Da li želite da dodate Schema Data (može značajno produžiti vreme potrebno za kreiranje): ",
        #     ("Da", "Ne"),
        #     help="Schema Data se dodaje na početak teksta",
        #     key="add_schema_web",
        # )
        # chunk_size, chunk_overlap = def_chunk()
        submit_button = st.form_submit_button(label="Submit")
        st.info(f"Chunk veličina: {chunk_size}, chunk preklapanje: {chunk_overlap}")
        if len(text_prefix) > 0:
            text_prefix = text_prefix + " "
        if submit_button and not sajt == "":
            res = requests.get(sajt, headers=headers)
            err_log = ""

            # Read OpenAI API key from file
            openai.api_key = os.environ.get("OPENAI_API_KEY")

            # # Retrieving API keys from files
            # PINECONE_API_KEY = os.environ.get("PINECONE_API_KEY")

            # # Setting the environment for Pinecone API
            # PINECONE_API_ENV = os.environ.get("PINECONE_API_ENV")

            # pinecone.init(api_key=PINECONE_API_KEY, environment=PINECONE_API_ENV)

            # Initialize BeautifulSoup with the response text
            soup = BeautifulSoup(res.text, "html.parser")
            # soup = BeautifulSoup(res.text, 'html5lib')

            # Define a function to scrape a given URL

            links = [sajt]
            scraped = set()
            data = []
            i = 0
            placeholder = st.empty()

            with st.spinner(f"Scraping "):
                while True:
                    # while i < 2:
                    i += 1
                    if len(links) == 0:
                        st.success("URL lista je kompletirana")
                        break
                    url = links[0]

                    # st.write(f'{url}, ">>", {i}')
                    placeholder.text(f"Obrađujem link broj {i}")
                    try:
                        res = scrape(url)
                        err_log += f" OK scraping {url}: {i}\n"
                    except Exception as e:
                        err_log += f"An error occurred while scraping {url}: page can not be scraped.\n"

                    scraped.add(url)

                    if res is not None:
                        page_content, local_links = res
                        data.append(page_content)
                        # add new links to links list
                        links.extend(local_links)
                        # remove duplicates
                        links = list(set(links))
                    # remove links already scraped
                    links = [link for link in links if link not in scraped]

                # Initialize RecursiveCharacterTextSplitter
                text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=chunk_size, chunk_overlap=chunk_overlap
                )
            chunks = []

            progress_text = "Podaci za Embeding se trenutno kreiraju. Molimo sačekajte."

            progress_bar = st.progress(0.0, text=progress_text)
            ph = st.empty()
            progress_barl = st.progress(0.0, text=progress_text)
            ph2 = st.empty()
            ph3 = st.empty()
            # Iterate over data records
            with st.spinner(f"Kreiranje podataka za Embeding"):
                for idx, record in enumerate(tqdm(data)):
                    # Split the text into chunks using the text splitter
                    texts = text_splitter.split_text(record["text"])

                    sto = len(data)
                    odsto = idx + 1
                    procenat = odsto / sto

                    k = int(odsto / sto * 100)
                    progress_bar.progress(procenat, text=progress_text)
                    ph.text(f"Učitano {odsto} od {sto} linkova što je {k} % ")
                    # Create a list of chunks for each text

                    # ovde moze da se doda dinamicko dadavanje prefixa
                    for il in range(len(texts)):
                        stol = len(texts)
                        odstol = il + 1
                        procenatl = odstol / stol

                        kl = int(odstol / stol * 100)
                        progress_barl.progress(procenatl, text=progress_text)
                        ph2.text(f"Učitano {odstol} od {stol} chunkova što je {kl} % ")

                        chunks.append(
                            {
                                "id": str(uuid4()),
                                "text": f"{text_prefix}  {texts[il]}",
                                "source": record["url"],
                                "date": datetime.datetime.now().strftime("%d.%m.%Y")
                            }
                        )

                    # Generate JSON strings for each chunk and join them with newline characters
                    json_strings = [
                        json.dumps(chunk, ensure_ascii=False) for chunk in chunks
                    ]
                    json_string = ",\n".join(json_strings)

                    # Add "[" at the beginning and "]" at the end of the entire JSON string
                    json_string = "[" + json_string + "]"
                    # Assuming 'chunks' is your list of dictionaries

                    # Now, json_string contains the JSON data as a string

                    napisano = st.info(
                        "Tekstovi su sačuvani u JSON obliku, downloadujte ih na svoj računar"
                    )

                    # Specify the file name where you want to save the JSON data

    parsed_url = urlparse(sajt)
    # Get the netloc (which includes the website name)
    website_name = parsed_url.netloc
    # Remove any potential "www." prefix
    if website_name.startswith("www."):
        website_name = website_name[4:]
    parts = website_name.split(".")
    if len(parts) > 1:
        website_name = parts[0]

    if napisano:
        skinuto = st.download_button(
            "Download JSON",
            data=json_string,
            file_name=f"{website_name}.json",
            mime="application/json",
        )
    if skinuto:
        st.success(f"Tekstovi sačuvani na {file_name} su sada spremni za Embeding")


# in myfunc.various_tools.py
def scrape_webpage_text(url):
    """
    Fetches the content of a webpage by URL and returns the textual content,
    excluding HTML tags and script content.

    Args:
    - url (str): The URL of the webpage to scrape.

    Returns:
    - str: The textual content of the webpage.
    """
    try:
        # Send a GET request to the webpage
        response = requests.get(url)
        # Raise an exception if the request was unsuccessful
        response.raise_for_status()
        
        # Parse the content of the request with BeautifulSoup
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # Remove script and style elements
        for script_or_style in soup(['script', 'style']):
            script_or_style.decompose()
        
        # Get text from the parsed content
        text = soup.get_text()
        
        # Clean up the text by collapsing whitespace
        lines = (line.strip() for line in text.splitlines())
        chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
        text = '\n'.join(chunk for chunk in chunks if chunk)
        
        return text
    except requests.RequestException as e:
        return f"An error occurred: {e}"


# in myfunc.various_tools.py
def positive_calendly(phglob):
    """
    Embeds a Calendly scheduling iframe into a Streamlit sidebar container.

    This function creates a container within the Streamlit sidebar and embeds a Calendly scheduling
    iframe into it. The iframe allows users to schedule a 30-minute meeting via Calendly directly
    within the Streamlit app.
    
    Parameters:
    - phglob: A placeholder or container object for the Streamlit sidebar.

    Returns:
    - A string response "Do not answer to this question, just say Hvala".
    """
    
    calendly_url = "https://calendly.com/nina-lalovic/30min/?embed=true"
    iframe_html = f'<iframe src="{calendly_url}" width="320" height="820"></iframe>'
    st.components.v1.html(iframe_html, height=820)        
 
    return "CALENDLY"


# in myfunc.various_tools.py
def load_prompts_from_azure(bsc, inner_dict, key):
    """
    Loads specific prompts from an Azure Blob Storage JSON file.

    This function connects to an Azure Blob Storage container and retrieves a JSON file
    containing prompts. It then extracts and returns a specific prompt based on the provided
    inner dictionary and key.
    
    Parameters:
    - bsc: The Azure Blob Service Client object used to interact with the Blob Storage.
    - inner_dict: The key for the inner dictionary within the "POSITIVE" section of the JSON file.
    - key: The key for the specific prompt within the inner dictionary.

    Returns:
    - The specified prompt as a string from the JSON file.
    """
    blob_client = bsc.get_container_client("positive-user").get_blob_client("positive_prompts.json")
    prompts = json.loads(blob_client.download_blob().readall().decode('utf-8'))
    
    return prompts["POSITIVE"][inner_dict][key]


# in myfunc.various_tools.py
def load_data_from_azure(bsc, filename):
    """
    Loads data from a CSV file stored in Azure Blob Storage into a pandas DataFrame.

    This function connects to an Azure Blob Storage container and downloads a specified CSV file.
    It reads the CSV file into a pandas DataFrame and drops any rows that are completely empty.
    If the file is not found or another error occurs, it returns an empty DataFrame with specified columns.
    
    Parameters:
    - bsc: The Azure Blob Service Client object used to interact with the Blob Storage.
    - filename: The name of the CSV file to be loaded from the Blob Storage.

    Returns:
    - A pandas DataFrame containing the data from the CSV file, or an empty DataFrame with specified columns if an error occurs.
    """
    try:
        blob_service_client = bsc
        container_client = blob_service_client.get_container_client("positive-user")
        blob_client = container_client.get_blob_client(filename)

        streamdownloader = blob_client.download_blob()
        df = pd.read_csv(StringIO(streamdownloader.readall().decode("utf-8")))
        return df.dropna(how="all")
    
    except FileNotFoundError:
        return pd.DataFrame(columns=['Username', 'Thread ID', 'Thread Name', 'Conversation'])
    except Exception as e:
        print(f"An error occurred: {e}")
        return pd.DataFrame(columns=['Username', 'Thread ID', 'Thread Name', 'Conversation'])


# in myfunc.various_tools.py
def upload_data_to_azure(bsc, filename, new_data):
    """
    Uploads a pandas DataFrame as a CSV file to Azure Blob Storage.

    This function converts a given pandas DataFrame to CSV format and uploads it to a specified
    location in an Azure Blob Storage container. If a file with the same name already exists,
    it will be overwritten.
    
    Parameters:
    - bsc: The Azure Blob Service Client object used to interact with the Blob Storage.
    - filename: The name of the CSV file to be uploaded to the Blob Storage.
    - new_data: The pandas DataFrame containing the data to be uploaded.

    Returns:
    - None
    """
    # Convert DataFrame to CSV
    csv_data = new_data.to_csv(index=False)
    
    # Upload combined CSV data to Azure Blob Storage
    blob_service_client = bsc
    blob_client = blob_service_client.get_blob_client("positive-user", filename)
    blob_client.upload_blob(csv_data, overwrite=True)


# in myfunc.various_tools.py
def web_search_process(query: str) -> str:
    """
    Executes a web search using the provided query string.

    This function wraps the Google Search API, specifically using a service wrapper
    designed for this purpose (`GoogleSerperAPIWrapper`). It requires an API key, which
    is expected to be provided via environment variables. The function then runs the query
    through the API and returns the search results as a string.

    Parameters:
    - query (str): The search query string to be submitted to the Google Search API.

    Returns:
    - str: The search results returned by the Google Search API as a string.
    """    
    return GoogleSerperAPIWrapper(environment=os.environ["SERPER_API_KEY"]).run(query)


# in myfunc.various_tools.py
def hyde_rag(prompt):
    """
    Generates a response to a given prompt using an AI model.

    This function sends a prompt to an AI model and receives a generated response. The function
    uses a specified system message and user prompt to instruct the AI on how to process the input.
    The temperature parameter controls the randomness of the AI's output.
    
    Parameters:
    - prompt: The user's prompt to which the AI should respond.

    Returns:
    - The generated response from the AI as a string.
    """
    response = client.chat.completions.create(
        model= work_vars["names"]["openai_model"],
        temperature=0.5,
        messages=[
            {"role": "system", "content": st.session_state.hyde_rag},
            {"role": "user", "content": prompt}
            ]
        )
    response = response.choices[0].message.content
    
    return response


# in myfunc.various_tools.py
def create_structured_prompt(user_query):
    """
    Constructs a structured prompt for use with an AI model, based on a user's query.

    This function generates a structured JSON prompt that outlines various tools the AI
    assistant can use to answer questions. The prompt includes a description of each tool and
    specifies the scenarios in which each should be used, such as queries related to specific
    company data, SQL queries, or general questions that require web search. The user's query
    is incorporated into the prompt to provide context for the AI's response generation.

    Parameters:
    - user_query: The original query from the user that needs to be addressed by the AI model.

    Returns:
    - A list of dictionaries, each representing a part of the structured prompt, including
      the role (system or user) and the content (instructions for the AI or the user query).
    """
    if "choose_rag" not in st.session_state:
        with PromptDatabase() as db:
            prompt_map = db.get_prompts_by_names(["choose_rag"],[os.getenv("CHOOSE_RAG_KLOT")])
            st.session_state.choose_rag = prompt_map.get("choose_rag", "You are helpful assistant")
    return [
        {"role": "system", "content": st.session_state.choose_rag},
        {"role": "user", "content": f"Please provide the response in JSON format: {user_query}"}
    ]


# in myfunc.various_tools.py
def get_structured_decision_from_model(user_query):

    """
    Determines the most appropriate tool to use for a given user query using an AI model.

    This function sends a user query to an AI model and receives a structured decision in the
    form of a JSON object. The decision includes the recommended tool to use for addressing
    the user's query, based on the content and context of the query. The function uses a
    structured prompt, generated by `create_structured_prompt`, to instruct the AI on how
    to process the query. The AI's response is parsed to extract the tool recommendation.

    Parameters:
    - user_query: The user's query for which the tool recommendation is sought.

    Returns:
    - The name of the recommended tool as a string, based on the AI's analysis of the user query.
    """
    client = OpenAI()
    response = client.chat.completions.create(
        model=work_vars["names"]["openai_model"],
        temperature=0,
        response_format={"type": "json_object"},
        messages=create_structured_prompt(user_query),
    )
    json_string = response.choices[0].message.content
    # Parse the JSON string into a Python dictionary
    data_dict = json.loads(json_string)
    # Access the 'tool' value
    return data_dict['tool'] if 'tool' in data_dict else list(data_dict.values())[0]


# in myfunc.various_tools.py
def transcribe_audio_file(file_path, language="en"):
    """
    Transcribes the audio content of a file using an AI model.

    This function takes the path of an audio file and transcribes its content into text
    using the specified language. The transcription is performed by the AI model "whisper-1".
    The function opens the audio file in binary mode and sends it to the AI for transcription.
    
    Parameters:
    - file_path: The path to the audio file to be transcribed.
    - language: The language code for the audio content (default is "en" for English).

    Returns:
    - The transcription of the audio file as a string.
    """
    with open(file_path, "rb") as audio_file:
        transcript = client.audio.transcriptions.create(
            model="whisper-1", 
            file=audio_file, 
            language=language,
            response_format="text"
        )
    return transcript


# in myfunc.various_tools.py
def record_audio(duration=5, samplerate=16000, file_path='output.mp3'):
    """
    Records audio for a specified duration and saves it to a file.

    This function records audio using the specified sample rate and duration. The recorded audio
    is then converted to an MP3 file and saved at the specified file path.
    
    Parameters:
    - duration: The duration of the audio recording in seconds (default is 5 seconds).
    - samplerate: The sample rate for the audio recording in Hz (default is 16000 Hz).
    - file_path: The file path where the recorded audio will be saved (default is 'output.mp3').

    Returns:
    - The file path of the saved audio recording as a string.
    """
    myrecording = sd.rec(int(duration * samplerate), samplerate=samplerate, channels=1, dtype='int16')
    sd.wait()  # Wait until recording is finished
    # Convert the NumPy array to an audio segment
    audio_segment = AudioSegment(myrecording.tobytes(), frame_rate=samplerate, sample_width=myrecording.dtype.itemsize, channels=1)
    audio_segment.export(file_path, format="mp3")
    return file_path


# in myfunc.various_tools.py


async def suggest_questions(prompt, api_key = os.environ.get("OPENAI_API_KEY")):
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
                "model": work_vars["names"]["openai_model"],
                "messages": [system_message, user_message],
            },
        )
        data = await response.json()
        odgovor = data['choices'][0]['message']['content']
        return odgovor


def play_audio_from_stream(spoken_response):
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
