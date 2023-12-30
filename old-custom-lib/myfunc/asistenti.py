import streamlit as st
from io import StringIO, BytesIO
import pandas as pd
import requests
import os
import base64
from PIL import Image
from streamlit_javascript import st_javascript
from ast import literal_eval
from azure.storage.blob import BlobServiceClient
from os import environ
import pinecone
from pinecone_text.sparse import BM25Encoder
import openai
from langchain.agents import create_sql_agent
from langchain.agents.agent_toolkits import SQLDatabaseToolkit
from langchain.sql_database import SQLDatabase
from langchain.llms.openai import OpenAI
from langchain.agents.agent_types import AgentType
from langchain.chat_models import ChatOpenAI
from langchain.utilities import GoogleSerperAPIWrapper

class SQLSearchTool:
    """
    A tool to search an SQL database using natural language queries.
    This class uses the LangChain library to create an SQL agent that
    interprets natural language and executes corresponding SQL queries.
    """

    def __init__(self, db_uri=None):
        """
        Initialize the SQLSearchTool with a database URI.

        :param db_uri: The database URI. If None, it reads from the DB_URI environment variable.
        """

        if db_uri is None:
            db_uri = os.getenv("DB_URI")
        self.db = SQLDatabase.from_uri(db_uri)

        llm = ChatOpenAI(model="gpt-4-1106-preview", temperature=0)
        toolkit = SQLDatabaseToolkit(
            db=self.db, llm=llm
        )

        self.agent_executor = create_sql_agent(
            llm=llm,
            toolkit=toolkit,
            verbose=True,
            agent_type=AgentType.ZERO_SHOT_REACT_DESCRIPTION,
            handle_parsing_errors=True,
        )

    def search(self, query, queries = 10):
        """
        Execute a search using a natural language query.

        :param query: The natural language query.
        :param queries: The number of results to return (default 10).
        :return: The response from the agent executor.
        """
        formatted_query = f"[Use Serbian language to answer questions] Limit the final output to max {queries} records. If the answer cannot be found, respond with 'I don't know'. Use MySQL syntax. For any LIKE clauses, add an 'N' in front of the wildcard character. Here is the query: '{query}' "

        try:
            
            response = self.agent_executor.run(formatted_query)
        except Exception as e:
            
            response = f"Ne mogu da odgovorim na pitanje, molim vas korigujte zahtev. Opis greske je \n {e}"
        
        return response


class HybridQueryProcessor:
    """
    A processor for executing hybrid queries using Pinecone.

    This class allows the execution of queries that combine dense and sparse vector searches,
    typically used for retrieving and ranking information based on text data.

    Attributes:
        api_key (str): The API key for Pinecone.
        environment (str): The Pinecone environment setting.
        alpha (float): The weight used to balance dense and sparse vector scores.
        score (float): The score treshold.
        index_name (str): The name of the Pinecone index to be used.
        index: The Pinecone index object.
        namespace (str): The namespace to be used for the Pinecone index.
        top_k (int): The number of results to be returned.
            
    Example usage:
    processor = HybridQueryProcessor(api_key=environ["PINECONE_API_KEY_POS"], 
                                 environment=environ["PINECONE_ENVIRONMENT_POS"],
                                 alpha=0.7, 
                                 score=0.35,
                                 index_name='custom_index'), 
                                 namespace=environ["NAMESPACE"],
                                 top_k = 10 # all params are optional

    result = processor.hybrid_query("some query text")    
    """

    def __init__(self, **kwargs):
        """
        Initializes the HybridQueryProcessor with optional parameters.

        The API key and environment settings are fetched from the environment variables.
        Optional parameters can be passed to override these settings.

        Args:
            **kwargs: Optional keyword arguments:
                - api_key (str): The API key for Pinecone (default fetched from environment variable).
                - environment (str): The Pinecone environment setting (default fetched from environment variable).
                - alpha (float): Weight for balancing dense and sparse scores (default 0.5).
                - score (float): Weight for balancing dense and sparse scores (default 0.05).
                - index_name (str): Name of the Pinecone index to be used (default 'positive').
                - namespace (str): The namespace to be used for the Pinecone index (default fetched from environment variable).
                - top_k (int): The number of results to be returned (default 6).
        """
        self.api_key = kwargs.get('api_key', os.getenv('PINECONE_API_KEY_POS'))
        self.environment = kwargs.get('environment', os.getenv('PINECONE_ENVIRONMENT_POS'))
        self.alpha = kwargs.get('alpha', 0.5)  # Default alpha is 0.5
        self.score = kwargs.get('score', 0.05)  # Default score is 0.05
        self.index_name = kwargs.get('index', 'positive')  # Default index is 'positive'
        self.namespace = kwargs.get('namespace', os.getenv("NAMESPACE"))  
        self.top_k = kwargs.get('top_k', 6)  # Default top_k is 6
        self.index = None
        self.init_pinecone()

    def init_pinecone(self):
        """
        Initializes the Pinecone connection and index.
        """
        pinecone.init(api_key=self.api_key, environment=self.environment)
        self.index = pinecone.Index(self.index_name)

    def get_embedding(self, text, model="text-embedding-ada-002"):
        """
        Retrieves the embedding for the given text using the specified model.

        Args:
            text (str): The text to be embedded.
            model (str): The model to be used for embedding. Default is "text-embedding-ada-002".

        Returns:
            list: The embedding vector of the given text.
        """
        client = openai
        text = text.replace("\n", " ")
        
        return client.embeddings.create(input=[text], model=model).data[0].embedding

    def hybrid_score_norm(self, dense, sparse):
        """
        Normalizes the scores from dense and sparse vectors using the alpha value.

        Args:
            dense (list): The dense vector scores.
            sparse (dict): The sparse vector scores.

        Returns:
            tuple: Normalized dense and sparse vector scores.
        """
        return ([v * self.alpha for v in dense], 
                {"indices": sparse["indices"], 
                 "values": [v * (1 - self.alpha) for v in sparse["values"]]})

    def hybrid_query(self, upit):
        """
        Executes a hybrid query on the Pinecone index using the provided query text.

        Args:
            upit (str): The query text.

        Returns:
            dict: The query results returned from the Pinecone index.
        """
        hdense, hsparse = self.hybrid_score_norm(
            sparse=BM25Encoder().fit([upit]).encode_queries(upit),
            dense=self.get_embedding(upit))
        return self.index.query(
            top_k=self.top_k,
            vector=hdense,
            sparse_vector=hsparse,
            include_metadata=True,
            namespace=self.namespace).to_dict()

    def process_query_results(self, upit):
        """
        Processes the query results based on relevance score and formats them for a chat or dialogue system.

        Args:
            upit (str): The original query text.
            
        Returns:
            str: Formatted string for chat prompt.
        """
        tematika = self.hybrid_query(upit)

        uk_teme = ""
        for _, item in enumerate(tematika["matches"]):
            if item["score"] > self.score:  # Score threshold
                uk_teme += item["metadata"]["context"] + "\n\n"

        return uk_teme   
    


def read_aad_username():
    js_code = """(await fetch("/.auth/me")
        .then(function(response) {return response.json();}).then(function(body) {return body;}))
    """

    return_value = st_javascript(js_code)

    username = None
    if return_value == 0:
        pass  # this is the result before the actual value is returned
    elif isinstance(return_value, list) and len(return_value) > 0:  # this is the actual value
        username = return_value[0]["user_id"]
    else:
        st.warning(
            f"could not directly read username from azure active directory: {return_value}.")  # this is an error
    
    return username


def load_data_from_azure(bsc):
    try:
        blob_service_client = bsc
        container_client = blob_service_client.get_container_client("positive-user")
        blob_client = container_client.get_blob_client("assistant_data.csv")

        streamdownloader = blob_client.download_blob()
        df = pd.read_csv(StringIO(streamdownloader.readall().decode("utf-8")), usecols=["user", "chat", "ID", "assistant", "fajlovi"])
        df["fajlovi"] = df["fajlovi"].apply(literal_eval)
        return df.dropna(how="all")               
    except FileNotFoundError:
        return {"Nisam pronasao fajl"}
    except Exception as e:
        return {f"An error occurred: {e}"}
    

def upload_data_to_azure(z):
    z["fajlovi"] = z["fajlovi"].apply(lambda z: str(z))
    blob_client = BlobServiceClient.from_connection_string(
        environ.get("AZ_BLOB_API_KEY")).get_blob_client("positive-user", "assistant_data.csv")
    blob_client.upload_blob(z.to_csv(index=False), overwrite=True)

# ZAPISNIK
def audio_izlaz(content):
    api_key = os.getenv("OPENAI_API_KEY")
    response = requests.post(
        "https://api.openai.com/v1/audio/speech",
        headers={
            "Authorization": f"Bearer {api_key}",
        },
        json={
            "model" : "tts-1-hd",
            "voice" : "alloy",
            "input": content,
        
        },
    )    
    audio = b""
    for chunk in response.iter_content(chunk_size=1024 * 1024):
        audio += chunk

    # Convert the byte array to AudioSegment
    #audio_segment = AudioSegment.from_file(io.BytesIO(audio))

    # Save AudioSegment as MP3 file
    mp3_data = BytesIO(audio)
    #audio_segment.export(mp3_data, format="mp3")
    mp3_data.seek(0)

    # Display the audio using st.audio
    st.caption("mp3 fajl možete download-ovati odabirom tri tačke ne desoj strani audio plejera")
    st.audio(mp3_data.read(), format="audio/mp3")


def priprema():
    
    izbor_radnji = st.selectbox("Odaberite pripremne radnje", 
                    ("Transkribovanje Zvučnih Zapisa", "Čitanje sa slike iz fajla", "Čitanje sa slike sa URL-a"),
                    help = "Odabir pripremnih radnji"
                    )
    if izbor_radnji == "Transkribovanje Zvučnih Zapisa":
        transkript()
    elif izbor_radnji == "Čitanje sa slike iz fajla":
        read_local_image()
    elif izbor_radnji == "Čitanje sa slike sa URL-a":
        read_url_image()



# This function does transcription of the audio file and then corrects the transcript. 
# It calls the function transcribe and generate_corrected_transcript
def transkript():
    # Read OpenAI API key from env
    with st.sidebar:  # App start
        st.info("Konvertujte MP3 u TXT")
        audio_file = st.file_uploader(
            "Max 25Mb",
            type="mp3",
            key="audio_",
            help="Odabir dokumenta",
        )
        transcript = ""
        
        if audio_file is not None:
            st.audio(audio_file.getvalue(), format="audio/mp3")
            placeholder = st.empty()
            st.session_state["question"] = ""

            with placeholder.form(key="my_jezik", clear_on_submit=False):
                jezik = st.selectbox(
                    "Odaberite jezik izvornog teksta 👉",
                    (
                        "sr",
                        "en",
                    ),
                    key="jezik",
                    help="Odabir jezika",
                )

                submit_button = st.form_submit_button(label="Submit")
                client = openai
                if submit_button:
                    with st.spinner("Sačekajte trenutak..."):

                        system_prompt="""
                        You are the Serbian language expert. You must fix grammar and spelling errors but otherwise keep the text as is, in the Serbian language. \
                        Your task is to correct any spelling discrepancies in the transcribed text. \
                        Make sure that the names of the participants are spelled correctly: Miljan, Goran, Darko, Nemanja, Đorđe, Šiška, Zlatko, BIS, Urbanizam. \
                        Only add necessary punctuation such as periods, commas, and capitalization, and use only the context provided. If you could not transcribe the whole text for any reason, \
                        just say so. If you are not sure about the spelling of a word, just write it as you hear it. \
                        """
                        # does transcription of the audio file and then corrects the transcript
                        transcript = generate_corrected_transcript(client, system_prompt, audio_file, jezik)
                                                
                        with st.expander("Transkript"):
                            st.info(transcript)
                            
            if transcript !="":
                st.download_button(
                    "Download transcript",
                    transcript,
                    file_name="transcript.txt",
                    help="Odabir dokumenta",
                )


def read_local_image():

    st.info("Čita sa slike")
    image_f = st.file_uploader(
        "Odaberite sliku",
        type="jpg",
        key="slika_",
        help="Odabir dokumenta",
    )
    content = ""
  
    
    if image_f is not None:
        base64_image = base64.b64encode(image_f.getvalue()).decode('utf-8')
        # Decode the base64 image
        image_bytes = base64.b64decode(base64_image)
        # Create a PIL Image object
        image = Image.open(BytesIO(image_bytes))
        # Display the image using st.image
        st.image(image, width=150)
        placeholder = st.empty()
        # st.session_state["question"] = ""

        with placeholder.form(key="my_image", clear_on_submit=False):
            default_text = "What is in this image? Please read and reproduce the text. Read the text as is, do not correct any spelling and grammar errors. "
            upit = st.text_area("Unesite uputstvo ", default_text)  
            submit_button = st.form_submit_button(label="Submit")
            
            if submit_button:
                with st.spinner("Sačekajte trenutak..."):            
            
            # Path to your image
                    
                    api_key = os.getenv("OPENAI_API_KEY")
                    # Getting the base64 string
                    

                    headers = {
                      "Content-Type": "application/json",
                      "Authorization": f"Bearer {api_key}"
                    }

                    payload = {
                      "model": "gpt-4-vision-preview",
                      "messages": [
                        {
                          "role": "user",
                          "content": [
                            {
                              "type": "text",
                              "text": upit
                            },
                            {
                              "type": "image_url",
                              "image_url": {
                                "url": f"data:image/jpeg;base64,{base64_image}"
                              }
                            }
                          ]
                        }
                      ],
                      "max_tokens": 300
                    }

                    response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload)

                    json_data = response.json()
                    content = json_data['choices'][0]['message']['content']
                    with st.expander("Opis slike"):
                            st.info(content)
                            
        if content !="":
            st.download_button(
                "Download opis slike",
                content,
                file_name=f"{image_f.name}.txt",
                help="Čuvanje dokumenta",
            )


def read_url_image():
    # version url

    client = openai
    
    st.info("Čita sa slike sa URL")
    content = ""
    
    # st.session_state["question"] = ""
    #with placeholder.form(key="my_image_url_name", clear_on_submit=False):
    img_url = st.text_input("Unesite URL slike ")
    #submit_btt = st.form_submit_button(label="Submit")
    image_f = os.path.basename(img_url)   
    if img_url !="":
        st.image(img_url, width=150)
        placeholder = st.empty()    
    #if submit_btt:        
        with placeholder.form(key="my_image_url", clear_on_submit=False):
            default_text = "What is in this image? Please read and reproduce the text. Read the text as is, do not correct any spelling and grammar errors. "
        
            upit = st.text_area("Unesite uputstvo ", default_text)
            submit_button = st.form_submit_button(label="Submit")
            if submit_button:
                with st.spinner("Sačekajte trenutak..."):         
                    
                    response = client.chat.completions.create(
                      model="gpt-4-vision-preview",
                      messages=[
                        {
                          "role": "user",
                          "content": [
                            {"type": "text", "text": upit},
                            {
                              "type": "image_url",
                              "image_url": {
                                "url": img_url,
                              },
                            },
                          ],
                        }
                      ],
                      max_tokens=300,
                    )
                    content = response.choices[0].message.content
                    with st.expander("Opis slike"):
                                st.info(content)
                            
    if content !="":
        st.download_button(
            "Download opis slike",
            content,
            file_name=f"{image_f}.txt",
            help="Čuvanje dokumenta",
        )



def generate_corrected_transcript(client, system_prompt, audio_file, jezik):
    client= openai
    
    def chunk_transcript(transkript, token_limit):
        words = transkript.split()
        chunks = []
        current_chunk = ""

        for word in words:
            if len((current_chunk + " " + word).split()) > token_limit:
                chunks.append(current_chunk.strip())
                current_chunk = word
            else:
                current_chunk += " " + word

        chunks.append(current_chunk.strip())

        return chunks


    def transcribe(client, audio_file, jezik):
        client=openai
        
        return client.audio.transcriptions.create(model="whisper-1", file=audio_file, language=jezik, response_format="text")
    
    
    transcript = transcribe(client, audio_file, jezik)
    st.caption("delim u delove po 1000 reci")
    chunks = chunk_transcript(transcript, 1000)
    broj_delova = len(chunks)
    st.caption (f"Broj delova je: {broj_delova}")
    corrected_transcript = ""

    # Loop through the token chunks
    for i, chunk in enumerate(chunks):
        
        st.caption(f"Obradjujem {i + 1}. deo...")
          
        response = client.chat.completions.create(
            model="gpt-4-1106-preview",
            temperature=0,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": chunk}])
    
        corrected_transcript += " " + response.choices[0].message.content.strip()

    return corrected_transcript


def dugacki_iz_kratkih(uploaded_text, entered_prompt):
   
    uploaded_text = uploaded_text[0].page_content

    if uploaded_text is not None:
        all_prompts = {
                 "p_system_0" : (
                    "You are helpful assistant."
                ),
                 "p_user_0" : ( 
                     "[In Serbian, using markdown formatting] At the begining of the text write the Title [formatted as H1] for the whole text, the date (dd.mm.yy), topics that vere discussed in the numbered list. After that list the participants in a numbered list. "
                ),
                "p_system_1": (
                    "You are a helpful assistant that identifies the main topics in a provided text. Please ensure clarity and focus in your identification."
                ),
                "p_user_1": (
                    "Please provide a numerated list of up to 10 main topics described in the text - one topic per line. Avoid including any additional text or commentary."
                ),
                "p_system_2": (
                    "You are a helpful assistant that corrects structural mistakes in a provided text, ensuring the response follows the specified format. Address any deviations from the request."
                ),
                "p_user_2": (
                    "Please check if the previous assistant's response adheres to this request: 'Provide a numerated list of topics - one topic per line, without additional text.' Correct any deviations or structural mistakes. If the response is correct, re-send it as is."
                ),
                "p_system_3": (
                    "You are a helpful assistant that summarizes parts of the provided text related to a specific topic. Ask for clarification if the context or topic is unclear."
                ),
                "p_user_3": (
                    "[In Serbian, using markdown formatting, use H2 as a top level] Please summarize the above text, focusing only on the topic {topic}. Start with a simple title, followed by 2 empty lines before and after the summary. "
                ),
                "p_system_4": (
                    "You are a helpful assistant that creates a conclusion of the provided text. Ensure the conclusion is concise and reflects the main points of the text."
                ),
                "p_user_4": (
                    "[In Serbian, using markdown formatting, use H2 as a top level ] Please create a conclusion of the above text. The conclusion should be succinct and capture the essence of the text."
                )
            }

        

        def get_response(p_system, p_user_ext):
            client = openai
            
            response = client.chat.completions.create(
                model="gpt-4-1106-preview",
                temperature=0,
                messages=[
                    {"role": "system", "content": all_prompts[p_system]},
                    {"role": "user", "content": uploaded_text},
                    {"role": "user", "content": p_user_ext}
                ]
            )
            return response.choices[0].message.content.strip()


        response = get_response("p_system_1", all_prompts["p_user_1"])
        
        # ovaj double check je veoma moguce bespotreban, no sto reskirati
        response = get_response("p_system_2", all_prompts["p_user_2"]).split('\n')
        topics = [item for item in response if item != ""]  # just in case - triple check

        # Prvi deo teksta sa naslovom, datumom, temama i ucesnicima
        formatted_pocetak_summary = f"{get_response('p_system_0', all_prompts['p_user_0'])}"
        
        # Start the final summary with the formatted 'pocetak_summary'
        final_summary = formatted_pocetak_summary + "\n\n"
        i = 0
        imax = len(topics)

        for topic in topics:
            summary = get_response("p_system_3", f"{all_prompts['p_user_3'].format(topic=topic)}")
            st.info(f"Summarizing topic: {topic} - {i}/{imax}")
            final_summary += f"{summary}\n\n"
            i += 1

        final_summary += f"{get_response('p_system_4', all_prompts['p_user_4'])}"
        
        return final_summary
    
    else:
        return "Please upload a text file."

def hybrid_search_process(upit: str) -> str:
        processor = HybridQueryProcessor()
        stringic = processor.process_query_results(upit)
        return stringic
    
def sql_search_tool(upit: str) -> str:
    processor = SQLSearchTool()
    stringic = processor.search(upit)
    return stringic
# krecemo polako i sa definisanjem UI-a

def web_serach_process(q: str) -> str:
    return GoogleSerperAPIWrapper(environment=os.environ["SERPER_API_KEY"]).run(q)
