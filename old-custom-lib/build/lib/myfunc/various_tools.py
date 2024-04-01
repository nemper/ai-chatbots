import datetime
import html
import json
import logging
import openai
import os
import pandas as pd
import re
import requests
import streamlit as st
import sys

from bs4 import BeautifulSoup
from io import StringIO
from openai import OpenAI
from tqdm.auto import tqdm
from urllib.parse import urljoin, urlparse
from uuid import uuid4

from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.utilities import GoogleSerperAPIWrapper

from myfunc.mojafunkcija import st_style
from myfunc.prompts import PromptDatabase

if "init_prompts" not in st.session_state:
    st.session_state.init_prompts = 42
    with PromptDatabase() as db:
        prompt_map = db.get_prompts_by_names(["hyde_rag", "choose_rag"],[os.getenv("HYDE_RAG"), os.getenv("CHOOSE_RAG")])
        st.session_state.hyde_rag = prompt_map.get("hyde_rag", "You are helpful assistant")
        st.session_state.choose_rag = prompt_map.get("choose_rag", "You are helpful assistant")
    
AZ_BLOB_API_KEY = os.getenv("AZ_BLOB_API_KEY")

st_style()
client=OpenAI()


# novi dugacki zapisnik
class MeetingTranscriptSummarizer:
    def __init__(self, transcript, temperature, number_of_topics):
        self.transcript = transcript
        self.temperature = temperature
        self.number_of_topics = number_of_topics

    def get_response(self, prompt, text):
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
            temperature=self.temperature,
            messages=[
                {"role": "system", "content": prompt + "Use only the Serbian Language"},
                {"role": "user", "content": text}
            ]
        )
        return response.choices[0].message.content

    def summarize(self):
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


def summarize_meeting_transcript(transcript, temp, broj_tema):
    """
    Summarize a meeting transcript by first extracting the date, participants, and topics,
    and then summarizing each topic individually while excluding the introductory information
    from the summaries.

    Parameters: 
        transcript (str): The transcript of the meeting.
    """

    def get_response(prompt, text, temp):
        """
        Generate a response from the model based on the given prompt and text.
        
        Parameters:
            prompt (str): The prompt to send to the model.
            text (str): The text to summarize or extract information from.
        """
        
        response = client.chat.completions.create(
            model="gpt-4-turbo-preview",
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


# Define a function to scrape a given URL
def scrape(url: str):
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


# Define a function to scrape a given URL
def main_scraper(chunk_size, chunk_overlap):
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


def positive_calendly(phglob):
    with st.sidebar:
        with phglob.container():
            calendly_url = "https://calendly.com/djordje-thai/30min/?embed=true"
            iframe_html = f'<iframe src="{calendly_url}" width="320" height="820"></iframe>'
            st.components.v1.html(iframe_html, height=820)
            
    return "Do not answer to this question, just say Hvala"


def load_prompts_from_azure(bsc, inner_dict, key):
    blob_client = bsc.get_container_client("positive-user").get_blob_client("positive_prompts.json")
    prompts = json.loads(blob_client.download_blob().readall().decode('utf-8'))
    
    return prompts["POSITIVE"][inner_dict][key]


def load_data_from_azure(bsc, filename):
    """ Load data from Azure Blob Storage. """
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


def upload_data_to_azure(bsc, filename, new_data):
    """ Upload data to Azure Blob Storage with appending new data. """

    # Convert DataFrame to CSV
    csv_data = new_data.to_csv(index=False)
    
    # Upload combined CSV data to Azure Blob Storage
    blob_service_client = bsc
    blob_client = blob_service_client.get_blob_client("positive-user", filename)
    blob_client.upload_blob(csv_data, overwrite=True)


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


def hyde_rag(prompt):
  
    client = OpenAI()
    response = client.chat.completions.create(
        model= "gpt-4-turbo-preview",
        temperature=0.5,
        messages=[
            {"role": "system", "content": st.session_state.hyde_rag},
            {"role": "user", "content": prompt}
            ]
        )
    response = response.choices[0].message.content
    
    return response


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
    return [
        {"role": "system", "content": st.session_state.choose_rag},
        {"role": "user", "content": user_query}
    ]


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
        model= "gpt-4-turbo-preview",
        temperature=0,
        response_format= { "type": "json_object" },
        messages=create_structured_prompt(user_query),
    )
    json_string = response.choices[0].message.content
    # Parse the JSON string into a Python dictionary
    data_dict = json.loads(json_string)
    # Access the 'tool' value
    tool_value = data_dict['tool']
    
    return tool_value  
        