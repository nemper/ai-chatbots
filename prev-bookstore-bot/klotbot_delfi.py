import os
os.environ["OPENAI_MODEL"] = "gpt-4o"
os.environ["CHOOSE_RAG"] = "DELFI_CHOOSE_RAG"
os.environ["SYS_RAGBOT"] = "DELFI_SYS_CHATBOT"
os.environ["PINECONE_ENVIRONMENT"] = "us-west1-gcp-free"
import base64
import io
import mysql
import streamlit as st
import uuid
import soundfile as sf
from openai import OpenAI
from streamlit_mic_recorder import mic_recorder
from myfunc.mojafunkcija import positive_login, initialize_session_state, check_openai_errors, read_txts, copy_to_clipboard
from klotbot_delfi_funcs import SelfQueryDelfi, order_search, graph_search, graph_search2, graph_search3, HybridQueryProcessor
from klotbot_promptdb import ConversationDatabase, work_prompts
from myfunc.pyui_javascript import chat_placeholder_color, st_fixed_container
import json
import asyncio
import aiohttp

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
    "thread_id": str(uuid.uuid4()),
    "filtered_messages": "",
    "selected_question": None,
    "username": "positive",
    "openai_model": os.getenv("OPENAI_MODEL"),
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
avatar_bg="delfilogo.png" 
avatar_ai="delfiavatar.jpg" 
avatar_user = "user.webp"
avatar_sys = "delfilogo.png"

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
                "model": os.getenv("OPENAI_MODEL"),
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
                    model=os.getenv("OPENAI_MODEL"),
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


def reset_memory():
    st.session_state.messages[st.session_state.thread_id] = [{'role': 'system', 'content': mprompts["sys_ragbot"]}]
    st.session_state.filtered_messages = ""
    

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
        model=os.getenv("OPENAI_MODEL"),
        temperature=0,
        response_format={"type": "json_object"},
        messages=[
        {"role": "system", "content": mprompts["choose_rag"]},
        {"role": "user", "content": f"Please provide the response in JSON format: {user_query}"}],
        )
    json_string = response.choices[0].message.content
    # Parse the JSON string into a Python dictionary
    data_dict = json.loads(json_string)
    # Access the 'tool' value
    return data_dict['tool'] if 'tool' in data_dict else list(data_dict.values())[0]


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

    elif st.session_state.rag_tool == "Graph2":
        context = graph_search2(prompt)
    
    elif st.session_state.rag_tool == "Graph3":
        context = graph_search3(prompt)

    elif st.session_state.rag_tool == "CSV":
        context = order_search(prompt)
    st.write(st.session_state.rag_tool)
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


        with ConversationDatabase() as db:
            db.update_or_insert_sql_record(
                st.session_state.app_name,
                st.session_state.username,
                current_thread_id,
                st.session_state.messages[current_thread_id]
            )


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
                        model=os.getenv("OPENAI_MODEL"),
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
            #with ConversationDatabase() as db:   #cuva konverzaciju i sql bazu i tokene
            #    db.update_sql_record(st.session_state.app_name, st.session_state.username, current_thread_id, st.session_state.messages[current_thread_id])

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