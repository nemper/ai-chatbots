import base64
import io
import mysql
import os
import streamlit as st
import uuid

from openai import OpenAI
from streamlit_mic_recorder import mic_recorder

from myfunc.embeddings import rag_tool_answer
from myfunc.mojafunkcija import initialize_session_state, check_openai_errors, read_file
from myfunc.prompts import ConversationDatabase, get_prompts
from myfunc.pyui_javascript import chat_placeholder_color, st_fixed_container
from myfunc.retrievers import HybridQueryProcessor
from myfunc.various_tools import play_audio_from_stream_s, predlozeni_odgovori, process_request
from myfunc.varvars_dicts import work_vars

default_values = {
    "prozor": st.query_params.get('prozor', "d"),
    "_last_speech_to_text_transcript_id": 0,
    "_last_speech_to_text_transcript": None,
    "success": False,
    "toggle_state": False,
    "button_clicks": False,
    "prompt": '',
    "vrsta": '',
    "messages": {},
    "image_ai": False,
    "thread_id": 'ime',
    "filtered_messages": "",
    "selected_question": None,
    "username": "positive",
    "openai_model": work_vars["names"]["openai_model"],
    "azure_filename": "altass.csv",
    "app_name": "KlotBot",
    "sys_ragbot": "You are helpful assistant",
    "rag_answer_reformat": "You are helpful assistant"
}

initialize_session_state(default_values)

if st.session_state.sys_ragbot == "You are helpful assistant":
#    st.write("Ova poruka bi trebala samo jednom da se pojavi, i to na pocetku >> ako se pojavi vise puta, nesto nije u redu sa ucitanim promptovima iz sql-a")
    get_prompts("rag_answer_reformat", "sys_ragbot")
    
print(st.session_state)
if st.session_state.thread_id not in st.session_state.messages:
    st.session_state.messages[st.session_state.thread_id] = [{'role': 'system', 'content': st.session_state.sys_ragbot}]

api_key=os.getenv("OPENAI_API_KEY")
client=OpenAI()
processor = HybridQueryProcessor() # namespace moze i iz env
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
        @media (max-width: 768px) {
            div[data-testid="stHorizontalBlock"] {
                width: 200px; /* Fixed width for mobile */
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


def main():
    if "thread_id" not in st.session_state:
        def get_thread_ids():
            with ConversationDatabase() as db:
                return db.list_threads(st.session_state.app_name, st.session_state.username)
        new_thread_id = str(uuid.uuid4())
        thread_name = f"Thread_{new_thread_id}"
        conversation_data = [{'role': 'system', 'content': st.session_state.sys_ragbot}]
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
                st.session_state.messages[thread_name].append({'role': 'system', 'content': st.session_state.sys_ragbot})
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
                    st.session_state.messages[thread_name].append({'role': 'system', 'content': st.session_state.sys_ragbot})
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
    col1, col2 = st.columns(2)
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
                    st.session_state.image_ai, st.session_state.vrsta = read_file()
                    
    # main conversation prompt            
    st.session_state.prompt = st.chat_input("Kako vam mogu pomoći?")
    if st.session_state.image_ai:
                        st.info(f"Vaš dokument je ucitan ({st.session_state.vrsta}), postavite pitanje")
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
        result = rag_tool_answer(st.session_state.prompt, phglob)

        if result=="CALENDLY":
            full_prompt=""
            full_response=""
            complete_prompt=""
            temp_full_prompt = {"role": "user", "content": [{"type": "text", "text": st.session_state.prompt}]}
        elif st.session_state.image_ai:

            if st.session_state.vrsta=="tekst":
                pre_prompt=st.session_state.image_ai
                full_prompt = st.session_state.prompt + pre_prompt 
                temp_full_prompt = {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": full_prompt},
            
                    ]
                }
                complete_prompt = full_prompt  # ovo treba proveriti za img tokene
                st.session_state.messages[current_thread_id].append(
                    {"role": "user", "content": st.session_state.prompt}
                )
                with st.chat_message("user", avatar=avatar_user):
                    st.markdown(st.session_state.prompt)
                
            else:   
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
                complete_prompt= full_prompt  # ovo treba proveriti za img tokene
                st.session_state.messages[current_thread_id].append(
                    {"role": "user", "content": st.session_state.prompt}
                )
                with st.chat_message("user", avatar=avatar_user):
                    st.markdown(st.session_state.prompt)
               
        else:    
            temp_full_prompt = {"role": "user", "content": [{"type": "text", "text": st.session_state.prompt}]}
    
            context = result
            complete_prompt = st.session_state.rag_answer_reformat.format(prompt=st.session_state.prompt, context=context)
            # Append only the user's original prompt to the actual conversation log
            st.session_state.messages[current_thread_id].append({"role": "user", "content": st.session_state.prompt})

            # Display user prompt in the chat
            with st.chat_message("user", avatar=avatar_user):
                st.markdown(st.session_state.prompt)
    
            # Prepare a temporary messages list for generating the assistant's response
            temp_messages = st.session_state.messages[current_thread_id].copy()
            temp_messages[-1] = {"role": "user", "content": complete_prompt}  # Replace last message with enriched context
    
        
        
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
    
            # Append assistant's response to the conversation
            st.session_state.messages[current_thread_id].append({"role": "assistant", "content": full_response})
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
    
            with ConversationDatabase() as db:   #cuva konverzaciju i sql bazu i tokene
                db.update_sql_record(st.session_state.app_name, st.session_state.username, current_thread_id, st.session_state.messages[current_thread_id])

            with col2:    # cuva konverzaciju u txt fajl
                with st_fixed_container(mode="fixed", position="bottom", border=False, margin='10px'):                
                    st.download_button(
                        "💾 Sačuvaj", 
                        st.session_state.filtered_messages, 
                        file_name="istorija.txt", 
                        help = "Čuvanje zadatog prompta"
                        )


if __name__ == "__main__":
    check_openai_errors(main())


