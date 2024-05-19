import mysql
import os
import streamlit as st
import uuid

from audiorecorder import audiorecorder 
from openai import OpenAI

from myfunc.embeddings import rag_tool_answer
from myfunc.prompts import ConversationDatabase, PromptDatabase
from myfunc.retrievers import HybridQueryProcessor
from myfunc.various_tools import transcribe_audio_file, play_audio_from_stream, suggest_questions
from myfunc.varvars_dicts import work_vars
from myfunc.pyui_javascript import chat_placeholder_color, st_fixed_container, ui_features


client=OpenAI()
processor = HybridQueryProcessor() # namespace moze i iz env

try:
    x = st.session_state.sys_ragbot
except:
    with PromptDatabase() as db:
        prompt_map = db.get_prompts_by_names(["rag_answer_reformat", "sys_ragbot"],[os.getenv("RAG_ANSWER_REFORMAT"), os.getenv("SYS_RAGBOT")])
        st.session_state.rag_answer_reformat = prompt_map.get("rag_answer_reformat", "You are helpful assistant")
        st.session_state.sys_ragbot = prompt_map.get("sys_ragbot", "You are helpful assistant")

def handle_question_click(question):
    """Set the selected question in the session state."""
    st.session_state.selected_question = question

@st.experimental_fragment
def fragment_function():
        st.session_state.pricaj = st.toggle("Da li da pričam? (levo - Ne, desno - Da)")  
    
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

   
    with st_fixed_container(mode="fixed", position="top", border=False): # snima audio za pitanje
            audio = audiorecorder("⏺ Snimi pitanje", "⏹ Zaustavi snimanje", "⏸ Pauza") # mozda ce biti zamenjeno ka 4o bude razumeo audio
            if len(audio) > 0:
                audio.export("audio.wav", format="wav")    
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
        if result=="Do not answer to this question, just say Hvala":
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
            odgovor = suggest_questions(full_response)
        try:
            questions = odgovor.split('\n')
        except:
            pass

        # Create buttons for each question
        try:
            for question in questions:
                if len(question)>10:
                    st.button(question, on_click=handle_question_click, args=(question,), key=uuid.uuid4())
        except:
            pass
        
        # Display the selected question
        prompt = st.session_state.selected_question
        st.session_state['selected_question'] = None

        with ConversationDatabase() as db:
            db.update_sql_record(st.session_state.app_name, st.session_state.username, current_thread_id, st.session_state.messages[current_thread_id])
            db.add_token_record(app_id='klotbot', model_name=st.session_state["openai_model"], embedding_tokens=emb_prompt_tokens, complete_prompt=complete_prompt, full_response=full_response, messages=st.session_state.messages[current_thread_id])
        if st.session_state.pricaj and full_response !="":
            # cita odgovor
            spoken_response = client.audio.speech.create(
                model="tts-1-hd",
                voice="nova",
                input=full_response,
            )
            play_audio_from_stream(spoken_response)
            audio_base64, samplerate = play_audio_from_stream(spoken_response)

            # Generate the HTML to play the audio - ovo ce biti zamenjeno kada 4o bude sam radio audio...
            audio_html = f"""
                <audio id="audio" autoplay style="display:none;">
                  <source src="data:audio/wav;base64,{audio_base64}" type="audio/wav">
                  Your browser does not support the audio element.
                </audio>
                <script>
                    var audioElement = document.getElementById('audio');
                    audioElement.play();
                </script>
            """

            st.components.v1.html(audio_html, height=0)

if __name__ == "__main__":
    main()
