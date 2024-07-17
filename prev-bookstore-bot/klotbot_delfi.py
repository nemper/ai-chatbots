import base64
import io
import json
import mysql
import os
import streamlit as st
import uuid

from neo4j import GraphDatabase
from openai import OpenAI
from streamlit_mic_recorder import mic_recorder

os.environ['CHOOSE_RAG'] = "DELFI_CHOOSE_RAG"
os.environ['SYS_RAGBOT'] = "DELFI_SYS_CHATBOT"

from myfunc.embeddings import rag_tool_answer
from myfunc.mojafunkcija import positive_login, initialize_session_state, check_openai_errors, read_txts, copy_to_clipboard
from myfunc.prompts import ConversationDatabase
from myfunc.pyui_javascript import chat_placeholder_color, st_fixed_container
from myfunc.retrievers import HybridQueryProcessor
from myfunc.various_tools import play_audio_from_stream_s, predlozeni_odgovori, process_request, get_structured_decision_from_model
from myfunc.varvars_dicts import work_prompts, work_vars

mprompts = work_prompts()
for key, value in mprompts.items():
    print(key, value)
    print("\n")
default_values = {
    "prozor": st.query_params.get('prozor', "d"),
    "_last_speech_to_text_transcript_id": 0,
    "_last_speech_to_text_transcript": None,
    "success": False,
    "toggle_state": False,
    "button_clicks": False,
    "prompt": '',
    "vrsta": False,
    "messages": {},
    "image_ai": None,
    "thread_id": 'ime',
    "filtered_messages": "",
    "selected_question": None,
    "username": "positive",
    "openai_model": work_vars["names"]["openai_model"],
    "azure_filename": "altass.csv",
    "app_name": "KlotBot",
    "upload_key": 0,
}

initialize_session_state(default_values)

if st.session_state.thread_id not in st.session_state.messages:
    st.session_state.messages[st.session_state.thread_id] = [{'role': 'system', 'content': mprompts["sys_ragbot"]}]

api_key=os.getenv("OPENAI_API_KEY")
client=OpenAI()

# Set chat input placeholder color
chat_placeholder_color("#f1f1f1")
avatar_bg="botbg.png" 
avatar_ai="bot.png" 
avatar_user = "user.webp"
avatar_sys = "positivelogo.jpg"

global phglob
phglob=st.empty()

# Function to get image as base64
@st.cache_data
def get_img_as_base64(file):
    with open(file, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

# Apply background image
def apply_background_image(img_path):
    img = get_img_as_base64(img_path)
    page_bg_img = f"""
    <style>
    [data-testid="stAppViewContainer"] > .main {{
    background-image: url("data:image/png;base64,{img}");
    background-size: auto;
    background-position: center;
    background-repeat: no-repeat;
    background-attachment: fixed;
    }}
    </style>
    """
    st.markdown(page_bg_img, unsafe_allow_html=True)
    
def custom_streamlit_style():   
    custom_streamlit_style = """
        <style>
        div[data-testid="stHorizontalBlock"] {
            display: flex;
            flex-direction: row;
            width: 100%x;
            flex-wrap: nowrap;
            align-items: center;
            justify-content: flex-start;
        }
        .horizontal-item {
            margin-right: 5px; /* Adjust spacing as needed */
        }
        /* Mobile styles */
        @media (max-width: 640px) {
            div[data-testid="stHorizontalBlock"] {
                width: 160px; /* Fixed width for mobile */
            }
        }
        </style>
    """
    st.markdown(custom_streamlit_style, unsafe_allow_html=True)
    
# Callback function for audio recorder
def callback():
    if st.session_state.my_recorder_output:
        return st.session_state.my_recorder_output['bytes']

custom_streamlit_style()
apply_background_image(avatar_bg)


def reset_memory():
    st.session_state.messages[st.session_state.thread_id] = [{'role': 'system', 'content': mprompts["sys_ragbot"]}]
    st.session_state.filtered_messages = ""


from langchain_openai import OpenAIEmbeddings
from langchain_openai.chat_models import ChatOpenAI
from langchain.chains.query_constructor.base import AttributeInfo
from langchain.retrievers.self_query.base import SelfQueryRetriever
from langchain_community.vectorstores import Pinecone as LangPine

def SelfQueryDelfi(upit, api_key=None, environment=None, index_name='delfi', namespace='opisi', openai_api_key=None, host=None):
    """
    Executes a query against a Pinecone vector database using specified parameters or environment variables. 
    The function initializes the Pinecone and OpenAI services, sets up the vector store and metadata, 
    and performs a query using a custom retriever based on the provided input 'upit'.
    
    It is used for self-query on metadata.

    Parameters:
    upit (str): The query input for retrieving relevant documents.
    api_key (str, optional): API key for Pinecone. Defaults to PINECONE_API_KEY from environment variables.
    environment (str, optional): Pinecone environment. Defaults to PINECONE_API_KEY from environment variables.
    index_name (str, optional): Name of the Pinecone index to use. Defaults to 'positive'.
    namespace (str, optional): Namespace for Pinecone index. Defaults to NAMESPACE from environment variables.
    openai_api_key (str, optional): OpenAI API key. Defaults to OPENAI_API_KEY from environment variables.

    Returns:
    str: A string containing the concatenated results from the query, with each document's metadata and content.
         In case of an exception, it returns the exception message.

    Note:
    The function is tailored to a specific use case involving Pinecone and OpenAI services. 
    It requires proper setup of these services and relevant environment variables.
    """
    
    # Use the passed values if available, otherwise default to environment variables
    api_key = api_key if api_key is not None else os.getenv('PINECONE_API_KEY')
    environment = environment if environment is not None else os.getenv('PINECONE_API_KEY')
    # index_name is already defaulted to 'positive'
    namespace = namespace if namespace is not None else os.getenv("NAMESPACE")
    openai_api_key = openai_api_key if openai_api_key is not None else os.getenv("OPENAI_API_KEY")
    host = host if host is not None else os.getenv("PINECONE_HOST")
   
    embeddings = OpenAIEmbeddings(model="text-embedding-3-large")

    # prilagoditi stvanim potrebama metadata
    metadata_field_info = [
        AttributeInfo(name="authors", description="The author(s) of the document", type="string"),
        AttributeInfo(name="category", description="The category of the document", type="string"),
        AttributeInfo(name="chunk", description="The chunk number of the document", type="integer"),
        AttributeInfo(name="date", description="The date of the document", type="string"),
        AttributeInfo(name="eBook", description="Whether the document is an eBook", type="boolean"),
        AttributeInfo(name="genres", description="The genres of the document", type="string"),
        AttributeInfo(name="id", description="The unique ID of the document", type="string"),
        AttributeInfo(name="text", description="The main content of the document", type="string"),
        AttributeInfo(name="title", description="The title of the document", type="string"),
    ]

    # Define document content description
    document_content_description = "Content of the document"

    # Prilagoditi stvanom nazivu namespace-a
    vectorstore = LangPine.from_existing_index(
        index_name, embeddings, "context", namespace=namespace)

    # Initialize OpenAI embeddings and LLM
    llm = ChatOpenAI(model=work_vars["names"]["openai_model"], temperature=0)
    retriever = SelfQueryRetriever.from_llm(
        llm,
        vectorstore,
        document_content_description,
        metadata_field_info,
        enable_limit=True,
        verbose=True,
    )
    try:
        result = ""
        doc_result = retriever.get_relevant_documents(upit)
        for document in doc_result:
            result += "Authors: " + ", ".join(document.metadata['authors']) + "\n"
            result += "Category: " + document.metadata['category'] + "\n"
            result += "Chunk: " + str(document.metadata['chunk']) + "\n"
            result += "Date: " + document.metadata['date'] + "\n"
            result += "eBook: " + str(document.metadata['eBook']) + "\n"
            result += "Genres: " + ", ".join(document.metadata['genres']) + "\n"
            result += "ID: " + document.metadata['id'] + "\n"
            result += "Title: " + document.metadata['title'] + "\n"
            result += "Content: " + document.page_content + "\n\n"
    except Exception as e:
        result = e
    
    return result


def graph_search(pitanje):
    prompt = (
        "Preformuliši sledeće korisničko pitanje tako da bude jasno i razumljivo, uzimajući u obzir sledeće:\n"
        "1. Imamo 3 vrste nodova: Author, Book, Genre.\n"
        "2. Knjige imaju propertije: id, category, title, price, quantity, pages, eBook.\n"
        "3. Nazivi nodova uvek počinju velikim slovom. Posebno je važno da žanrovi budu pravilno napisani (npr. Fantastika, Drama, Religija i mitologija).\n"
        "4. Važno je razlikovati kategoriju od žanra. Kategorije su (npr. Knjiga, Film, Muzika, Udžbenik).\n"
        "5. Naslovi knjiga su često u različitim padežima, pa je potrebno prepoznati pravu reč.\n\n"
        "6. Korisnička pitanja mogu biti zbunjujuća, i važno je da prepoznamo da li se odnose na autora, knjigu ili žanr, i da ih ispravno formulišemo.\n\n"
        "Primeri:\n"
        "Pitanje: 'Interesuju me naslovi pisca Piramida.'\n"
        "Preformulisano pitanje: 'Interesuju me drugi naslovi autora knjige \"Piramide\".'\n\n"
        "Pitanje: 'Koji su autori napisali knjige u žanru drama?'\n"
        "Preformulisano pitanje: 'Koji su autori napisali knjige koje spadaju u žanr Drama?'\n\n"
        f"Pitanje: {pitanje}\n\n"
        "Preformulisano pitanje:"
    )
    
    try:
        response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a helpful assistant that always writes in Serbian."},
            {"role": "user", "content": prompt}
        ]
    )

        preformulisano_pitanje = response.choices[0].message.content.strip()
    except Exception as e:
        st.write(f"Došlo je do greške: {e}")

    # Neo4j detalji

    uri = os.getenv("NEO4J_URI")
    user = os.getenv("NEO4J_USER")
    password = os.getenv("NEO4J_PASS")

    # Kreiranje Neo4j sesije
    driver = GraphDatabase.driver(uri, auth=(user, password))

    def translate_question_to_cypher(question):
        prompt = f"Translate the following user question into a Cypher query. Use the given structure of the database: {question}"
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": """You are a helpful assistant that converts natural language questions into Cypher queries for a Neo4j database. 
                 The database has 3 node types: Author, Books, Genre, and 2 relationship types: BELONGS_TO and WROTE. 
                 Only Book nodes have properties: id, category, title, price, quantity, pages, and eBook. All node and relationship names are capitalized (e.g., Author, Book, Genre, BELONGS_TO, WROTE). 
                 Genre names are also capitalized (e.g., Drama, Fantastika). Please ensure that the generated Cypher query uses these exact capitalizations."""},
                {"role": "user", "content": prompt}
            ]
        )
        cypher_query = response.choices[0].message.content.strip()

        # Uklanjanje nepotrebnog teksta oko upita
        if '```cypher' in cypher_query:
            cypher_query = cypher_query.split('```cypher')[1].split('```')[0].strip()

        return cypher_query

    def execute_cypher_query(cypher_query):
        with driver.session() as session:
            result = session.run(cypher_query)
            return [record.data() for record in result]
        

    result = execute_cypher_query(translate_question_to_cypher(preformulisano_pitanje))
    return json.dumps(result, ensure_ascii=False, indent=2)
 
import re
import csv
def order_search(id_porudzbine):
    match = re.search(r'\d{5,}', id_porudzbine)
    if not match:
        return "No integer found in the prompt."
    
    order_number = int(match.group())

    try:
        with open('orders.csv', mode='r', encoding='utf-8-sig') as file:
            csv_reader = csv.reader(file)
            next(csv_reader)
            for row in csv_reader:
                if int(row[0]) == order_number:
                    return ", ".join(row)
        return f"Order number {order_number} not found in the CSV file."
    except FileNotFoundError:
        return "The file 'orders.csv' does not exist."
    except Exception as e:
        return f"An error occurred: {e}"
    

def rag_tool_answer(prompt, phglob):
    context = " "
    st.session_state.rag_tool = get_structured_decision_from_model(prompt)

    if  st.session_state.rag_tool == "Hybrid":
        processor = HybridQueryProcessor()
        context, scores = processor.process_query_results(prompt)
        # st.info("Score po chunku:")
        # st.write(scores)
        
    elif  st.session_state.rag_tool == "Opisi":
        # Example configuration for SelfQuery
        uvod = mprompts["rag_self_query"]
        prompt = uvod + prompt
        context = SelfQueryDelfi(prompt)
                
    elif  st.session_state.rag_tool == "Korice":
        # Example configuration for SelfQuery
        uvod = mprompts["rag_self_query"]
        prompt = uvod + prompt
        context = SelfQueryDelfi(upit=prompt, namespace="korice")

    elif  st.session_state.rag_tool == "Graph": 
        # Read the graph from the file-like object
        context = graph_search(prompt)

    elif st.session_state.rag_tool == "CSV":
        context = order_search(prompt)

    return context, st.session_state.rag_tool


def main():
    if "thread_id" not in st.session_state:
        def get_thread_ids():
            with ConversationDatabase() as db:
                return db.list_threads(st.session_state.app_name, st.session_state.username)
        new_thread_id = str(uuid.uuid4())
        thread_name = f"Thread_{new_thread_id}"
        conversation_data = [{'role': 'system', 'content': mprompts["sys_ragbot"]}]
        if thread_name not in get_thread_ids():
            with ConversationDatabase() as db:
                try:
                    db.add_sql_record(st.session_state.app_name, st.session_state.username, thread_name, conversation_data)
                    
                except mysql.connector.IntegrityError as e:
                    if e.errno == 1062:  # Duplicate entry for key
                        st.error("Thread ID already exists. Please try again with a different ID.")
                    else:
                        raise  # Re-raise the exception if it's not related to a duplicate entry
        st.session_state.thread_id = thread_name
        st.session_state.messages[thread_name] = []
    try:
        if "Thread_" in st.session_state.thread_id:
            contains_system_role = any(message.get('role') == 'system' for message in st.session_state.messages[thread_name])
            if not contains_system_role:
                st.session_state.messages[thread_name].append({'role': 'system', 'content': mprompts["sys_ragbot"]})
    except:
        pass
    
    if st.session_state.thread_id is None:
        st.info("Start a conversation by selecting a new or existing conversation.")
    else:
        current_thread_id = st.session_state.thread_id
        try:
            if "Thread_" in st.session_state.thread_id:
                contains_system_role = any(message.get('role') == 'system' for message in st.session_state.messages[thread_name])
                if not contains_system_role:
                    st.session_state.messages[thread_name].append({'role': 'system', 'content': mprompts["sys_ragbot"]})
        except:
            pass
       
        # Check if there's an existing conversation in the session state
        if current_thread_id not in st.session_state.messages:
            # If not, initialize it with the conversation from the database or as an empty list
            with ConversationDatabase() as db:
                st.session_state.messages[current_thread_id] = db.query_sql_record(st.session_state.app_name, st.session_state.username, current_thread_id) or []
        if current_thread_id in st.session_state.messages:
            # avatari primena
            for message in st.session_state.messages[current_thread_id]:
                if message["role"] == "assistant": 
                    with st.chat_message(message["role"], avatar=avatar_ai):
                        st.markdown(message["content"])
                elif message["role"] == "user":         
                    with st.chat_message(message["role"], avatar=avatar_user):
                        st.markdown(message["content"])
                elif message["role"] == "system":
                    pass
                else:         
                    with st.chat_message(message["role"], avatar=avatar_sys):
                        st.markdown(message["content"])
                            
    # Opcije
    col1, col2, col3 = st.columns(3)
    with col1:
    # Use the fixed container and apply the horizontal layout
        with st_fixed_container(mode="fixed", position="bottom", border=False, margin='10px'):
            with st.popover("Više opcija", help = "Snimanje pitanja, Slušanje odgovora, Priloži sliku"):
                # prica
                audio = mic_recorder(
                    key='my_recorder',
                    callback=callback,
                    start_prompt="🎤 Počni snimanje pitanja",
                    stop_prompt="⏹ Završi snimanje i pošalji ",
                    just_once=False,
                    use_container_width=False,
                    format="webm",
                )
                #predlozi
                st.session_state.toggle_state = st.toggle('✎ Predlozi pitanja/odgovora', key='toggle_button_predlog', help = "Predlažze sledeće pitanje")
                # govor
                st.session_state.button_clicks = st.toggle('🔈 Slušaj odgovor', key='toggle_button', help = "Glasovni odgovor asistenta")
                # slika  
                st.session_state.image_ai, st.session_state.vrsta = read_txts()

    # main conversation prompt            
    st.session_state.prompt = st.chat_input("Kako vam mogu pomoći?")

    if st.session_state.selected_question != None:
        st.session_state.prompt = st.session_state['selected_question']
        st.session_state['selected_question'] = None
        
    if st.session_state.prompt is None:
        # snimljeno pitanje
        if audio is not None:
            id = audio['id']
            if id > st.session_state._last_speech_to_text_transcript_id:
                st.session_state._last_speech_to_text_transcript_id = id
                audio_bio = io.BytesIO(audio['bytes'])
                audio_bio.name = 'audio.webm'
                st.session_state.success = False
                err = 0
                while not st.session_state.success and err < 3:
                    try:
                        transcript = client.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_bio,
                            language="sr"
                        )
                    except Exception as e:
                        st.error(f"Neočekivana Greška : {str(e)} pokušajte malo kasnije.")
                        err += 1
                        
                    else:
                        st.session_state.success = True
                        st.session_state.prompt = transcript.text

    # Main conversation answer
    if st.session_state.prompt:
        # Original processing to generate complete_prompt
        result, alat = rag_tool_answer(st.session_state.prompt, phglob)
        st.write("Alat koji je koriscen: ", st.session_state.rag_tool)
        st.write("Odgovor direktno iz alata: ", result)

        if result=="CALENDLY":
            full_prompt=""
            full_response=""
            temp_full_prompt = {"role": "user", "content": [{"type": "text", "text": st.session_state.prompt}]}

        elif st.session_state.image_ai:
            if st.session_state.vrsta:
                full_prompt = st.session_state.prompt + st.session_state.image_ai
                temp_full_prompt = {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": full_prompt},
            
                    ]
                }
                st.session_state.messages[current_thread_id].append(
                    {"role": "user", "content": st.session_state.prompt}
                )
                with st.chat_message("user", avatar=avatar_user):
                    st.markdown(st.session_state.prompt)
            if 3>5:   
                pre_prompt = """Describe the uploaded image in detail, focusing on the key elements such as objects, colors, sizes, 
                                positions, actions, and any notable characteristics or interactions. Provide a clear and vivid description 
                                that captures the essence and context of the image. """
                full_prompt = pre_prompt + st.session_state.prompt

                temp_full_prompt = {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": full_prompt},
                        {"type": "image_url", "image_url": {"url": st.session_state.image_ai}}
                    ]
                }
                st.session_state.messages[current_thread_id].append(
                    {"role": "user", "content": st.session_state.prompt}
                )
                with st.chat_message("user", avatar=avatar_user):
                    st.markdown(st.session_state.prompt)
            
        else:    
            temp_full_prompt = {"role": "user", "content": [{"type": "text", "text": f"""Using the following context:
                                                              {result}
                                                              answer the question: 
                                                              {st.session_state.prompt} :
                                                                 """}]}
    
            # Append only the user's original prompt to the actual conversation log
            st.session_state.messages[current_thread_id].append({"role": "user", "content": st.session_state.prompt})

            # Display user prompt in the chat
            with st.chat_message("user", avatar=avatar_user):
                st.markdown(st.session_state.prompt)

        
        # mislim da sve ovo ide samo ako nije kalendly
        if result!="CALENDLY":    
        # Generate and display the assistant's response using the temporary messages list
            with st.chat_message("assistant", avatar=avatar_ai):
                    
                    message_placeholder = st.empty()
                    full_response = ""
                    for response in client.chat.completions.create(
                        model=work_vars["names"]["openai_model"],
                        temperature=0,
                        messages=st.session_state.messages[current_thread_id] + [temp_full_prompt],
                        stream=True,
                        stream_options={"include_usage":True},
                        ):
                        try:
                            full_response += (response.choices[0].delta.content or "")
                            message_placeholder.markdown(full_response + "▌")
                        except Exception as e:
                                pass
            

            message_placeholder.markdown(full_response)
            copy_to_clipboard(full_response)
            # Append assistant's response to the conversation
            st.session_state.messages[current_thread_id].append({"role": "assistant", "content": full_response})
            st.session_state.filtered_messages = ""
            filtered_data = [entry for entry in st.session_state.messages[current_thread_id] if entry['role'] in ["user", 'assistant']]
            for item in filtered_data:  # lista za download conversation
                st.session_state.filtered_messages += (f"{item['role']}: {item['content']}\n")  
    
            # ako su oba async, ako ne onda redovno
            if st.session_state.button_clicks and st.session_state.toggle_state:
                process_request(client, temp_full_prompt, full_response, api_key)
            else:
                if st.session_state.button_clicks: # ako treba samo da cita odgovore
                    play_audio_from_stream_s(full_response)
        
                if st.session_state.toggle_state:  # ako treba samo da prikaze podpitanja
                    predlozeni_odgovori(temp_full_prompt)
    
            if st.session_state.vrsta:
                st.info(f"Dokument je učitan ({st.session_state.vrsta}) - uklonite ga iz uploadera kada ne želite više da pričate o njegovom sadržaju.")
            with ConversationDatabase() as db:   #cuva konverzaciju i sql bazu i tokene
                db.update_sql_record(st.session_state.app_name, st.session_state.username, current_thread_id, st.session_state.messages[current_thread_id])

            with col2:    # cuva konverzaciju u txt fajl
                with st_fixed_container(mode="fixed", position="bottom", border=False, margin='10px'):          
                    st.download_button(
                        "⤓ Preuzmi", 
                        st.session_state.filtered_messages, 
                        file_name="istorija.txt", 
                        help = "Čuvanje istorije ovog razgovora"
                        )
            with col3:
                with st_fixed_container(mode="fixed", position="bottom", border=False, margin='10px'):          
                    st.button("🗑 Obriši", on_click=reset_memory)
            
def main_wrap_for_st():
    check_openai_errors(main)

deployment_environment = os.environ.get("DEPLOYMENT_ENVIRONMENT")
 
if deployment_environment == "Streamlit":
    name, authentication_status, username = positive_login(main_wrap_for_st, " ")
else: 
    if __name__ == "__main__":
        check_openai_errors(main)