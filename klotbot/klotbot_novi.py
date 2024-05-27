import mysql
import os
import streamlit as st
import uuid
import aiohttp
import asyncio
from audiorecorder import audiorecorder 
from openai import OpenAI
import io
import soundfile as sf
import base64
import streamlit.components.v1 as components

from myfunc.embeddings import rag_tool_answer
from myfunc.prompts import ConversationDatabase, PromptDatabase
from myfunc.retrievers import HybridQueryProcessor
from myfunc.various_tools import transcribe_audio_file, play_audio_from_stream, suggest_questions
from myfunc.varvars_dicts import work_vars
from myfunc.pyui_javascript import chat_placeholder_color, ui_features, st_fixed_container

api_key=os.getenv("OPENAI_API_KEY")
client=OpenAI()
processor = HybridQueryProcessor() # namespace moze i iz env

################ ASYNC ################

try:
    x = st.session_state.sys_ragbot
except:
    with PromptDatabase() as db:
        prompt_map = db.get_prompts_by_names(["rag_answer_reformat", "sys_ragbot"],[os.getenv("RAG_ANSWER_REFORMAT"), os.getenv("SYS_RAGBOT")])
        st.session_state.rag_answer_reformat = prompt_map.get("rag_answer_reformat", "You are helpful assistant")
        st.session_state.sys_ragbot = prompt_map.get("sys_ragbot", "You are helpful assistant")

button_color=''

if "button_color" not in st.session_state:
    st.session_state.button_color='color2'


def toggle_button_color():
    if st.session_state.button_color == 'color2':
        st.session_state.button_color = 'color1'
        
    else:
        st.session_state.button_color = 'color2'
        
# Apply custom CSS for button styling
st.markdown(
    f"""
    <style>
    .stButton > button {{
        background-color: {'green' if st.session_state.button_color == 'color1' else 'rgb(57, 58, 71)'};
        color: white;
        border: 1px solid gray;
        text-align: center;
        text-decoration: none;
        display: inline-block;
        font-size: 10px;
        cursor: pointer;
        padding: 0.25rem 1.25rem;
        border-radius: 0.5rem;
        min-height: 37px; 
        margin: 9px;
        line-height: 1.6;
    }}
    </style>
    """,
    unsafe_allow_html=True
)

def suggest_questions_s(prompt): # sync version of suggested questions (async) from myfunc
    
    system_message = {
            "role": "system",
            "content": f"Use only the Serbian language"
        }
    user_message = {
            "role": "user",
            "content": 
                f"""You are an AI language model assistant for a company's chatbot. Your task is to generate 3 different possible continuation sentences that a user might say based on the given context. These continuations should be in the form of questions or statements that naturally follow from the conversation.

                    Your goal is to help guide the user through the Q&A process by predicting their next possible inputs. Ensure these continuations are from the user's perspective and relevant to the context provided.

                    Provide these sentences separated by newlines, without numbering.

                    Original context:
                    {prompt}
                                    """
                }
    response = client.chat.completions.create(
                    model=work_vars["names"]["openai_model"],
                    messages=[system_message, user_message],
                    )
               
    odgovor =  response.choices[0].message.content
    return odgovor

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

async def play_audio_from_stream(audio_data):
    buffer = io.BytesIO(audio_data)
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

async def handle_async_tasks(client, full_response, api_key):
    # Fetch spoken response and suggestions concurrently
    audio_data, odgovor = await asyncio.gather(
        fetch_spoken_response(client, full_response, api_key),
        suggest_questions(full_response, api_key)
    )

    # Play the spoken response
    audio_base64, samplerate = await play_audio_from_stream(audio_data)

    # Generate the HTML to play the audio
    audio_html = f"""
        <audio id="audio" style="display:none;">
          <source src="data:audio/wav;base64,{audio_base64}" type="audio/wav">
          Your browser does not support the audio element.
        </audio>
        <button id="playButton" onclick="document.getElementById('audio').play()">Slušaj odgovor</button>
        <style>
            #playButton {{
                background-color: #495058;
                color: #f1f1f1;
                padding: 0.25rem 0.75rem;
                border: 1px solid rgba(38, 39, 48, 0.1);
                border-radius: 0.25rem;
                font-size: 1rem;
                cursor: pointer;
                transition: background-color 0.3s, box-shadow 0.3s;
            }}
            #playButton:hover {{
                background-color: #353a40;
                box-shadow: 0 0.125rem 0.25rem rgba(0, 0, 0, 0.075);
            }}
            #playButton:active {{
                background-color: #d0d3db;
                box-shadow: 0 0.25rem 0.5rem rgba(0, 0, 0, 0.15) inset;
            }}
        </style>
    """

    st.components.v1.html(audio_html, height=50)

    # Process questions
    try:
        questions = odgovor.split('\n')
    except:
        questions = []

    # Create buttons for each question
    for question in questions:
        if len(question) > 10:
            st.button(question, on_click=handle_question_click, args=(question,), key=uuid.uuid4())

# Function to process the request
def process_request(client, full_response, api_key):
    # Schedule async tasks
    asyncio.run(handle_async_tasks(client, full_response, api_key))




def handle_question_click(question):
    """Set the selected question in the session state."""
    st.session_state.selected_question = question

@st.experimental_fragment
def fragment_function():
        st.button('Slušaj odgovor', on_click=toggle_button_color)  
    
#st.markdown("<style> #root > div:nth-child(1) > div > div > div > div > section > div {padding-top: 0rem;} </style>)", unsafe_allow_html=True)

# Embed the CSS in your Streamlit app
st.markdown(ui_features["aifriend_css"], unsafe_allow_html=True)

def main():
    chat_placeholder_color(color="white")
    global phglob
    phglob=st.empty()
    if "username" not in st.session_state:
        st.session_state.username = "positive"
    if "client" not in st.session_state:
        st.session_state.client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    if "openai_model" not in st.session_state:
        st.session_state["openai_model"] = work_vars["names"]["openai_model"]
    if "azure_filename" not in st.session_state:
        st.session_state.azure_filename = "altass.csv"
    if "messages" not in st.session_state:
        st.session_state.messages = {}
    if "messages" not in st.session_state:
        st.session_state.messages = {}
    if 'selected_question' not in st.session_state:
        st.session_state['selected_question'] = None
    if "app_name" not in st.session_state:
        st.session_state.app_name = "KlotBot"
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
    
    avatar_ai="bot.png" 
    avatar_user = "user.webp"
    avatar_sys = "positivelogo.jpg"
   
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

    custom_streamlit_style = """
    <style>
    div[data-testid="stHorizontalBlock"] {
        display: flex;
        flex-direction: row;
        width: 320px;
        flex-wrap: nowrap;
        align-items: center;
        justify-content: flex-start;
    }
    .horizontal-item {
        margin-right: 5px; /* Adjust spacing as needed */
    }
  
    </style>
"""

    st.markdown(custom_streamlit_style, unsafe_allow_html=True)

    # Use the fixed container and apply the horizontal layout
    with st_fixed_container(mode="fixed", position="bottom", border=False):
        col1, col2 = st.columns([0.5, 0.5])  # Adjust the ratio as needed

        with col1:
            audio = audiorecorder("⏺ Snimi", "⏹ Pošalji")
            if len(audio) > 0:
                audio.export("audio.wav", format="wav")
    
        with col2:
            fragment_function()
    prompt = st.chat_input("Kako vam mogu pomoći?")

    if not prompt : # stavlja transcript audia u prompt ako prompt nije unet
        if os.path.exists("audio.wav"):
            try:
                    prompt = transcribe_audio_file("audio.wav", "sr")
                    if os.path.exists("audio.wav"):
                        os.remove("audio.wav")
            except:
                    prompt = ""
    if st.session_state.selected_question != None:
        prompt = st.session_state['selected_question']
        st.session_state['selected_question'] = None
    # Main conversation UI
    if prompt:
        # Original processing to generate complete_prompt
        result = rag_tool_answer(prompt, phglob)
        if result=="CALENDLY":
            full_response=""
            emb_prompt_tokens=0
            complete_prompt=""
        else:    
            if isinstance(result, tuple) and len(result) == 3:
                context, scores, emb_prompt_tokens = result
            else:
                context, scores, emb_prompt_tokens = result, None, None

            complete_prompt = st.session_state.rag_answer_reformat.format(prompt=prompt, context=context)
            # Append only the user's original prompt to the actual conversation log
            st.session_state.messages[current_thread_id].append({"role": "user", "content": prompt})
    
            # Display user prompt in the chat
            with st.chat_message("user", avatar=avatar_user):
                st.markdown(prompt)
        
            # Prepare a temporary messages list for generating the assistant's response
            temp_messages = st.session_state.messages[current_thread_id].copy()
            temp_messages[-1] = {"role": "user", "content": complete_prompt}  # Replace last message with enriched context
    
            # Generate and display the assistant's response using the temporary messages list
            with st.chat_message("assistant", avatar=avatar_ai):
                message_placeholder = st.empty()
                full_response = ""
                for response in client.chat.completions.create(
                    model=work_vars["names"]["openai_model"],
                    temperature=0,
                    messages=temp_messages,  # Use the temporary list with enriched context
                    stream=True,
                ):
                    full_response += (response.choices[0].delta.content or "")
                    message_placeholder.markdown(full_response + "▌")
            message_placeholder.markdown(full_response)
        
            # Append assistant's response to the conversation
            st.session_state.messages[current_thread_id].append({"role": "assistant", "content": full_response})
            if not st.session_state.pricaj:
                # Process the request with sync handling - only suggested_questions
                odgovor = suggest_questions_s(full_response)
                                
        if st.session_state.pricaj and full_response != "":
            
            # Process the request with async handling
            process_request(client, full_response, api_key)
            
        else:        
            # Process the request with sync handling - only suggested_questions
            try:
                questions = odgovor.split('\n')
            except:
                questions = []

            # Create buttons for each question
            st.write("Predložena pitanja/odgovori:")
            for question in questions:
                if len(question) > 10:
                    st.button(question, on_click=handle_question_click, args=(question,), key=uuid.uuid4())
                # Display the selected question
                prompt = st.session_state.selected_question
                st.session_state['selected_question'] = None

        with ConversationDatabase() as db:
            db.update_sql_record(st.session_state.app_name, st.session_state.username, current_thread_id, st.session_state.messages[current_thread_id])
            db.add_token_record(app_id='klotbot', model_name=st.session_state["openai_model"], embedding_tokens=emb_prompt_tokens, complete_prompt=complete_prompt, full_response=full_response, messages=st.session_state.messages[current_thread_id])
        
            

if __name__ == "__main__":
    main()
