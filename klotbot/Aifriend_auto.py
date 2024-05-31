import streamlit as st
import os
from openai import OpenAI
from st_fixed_container import st_fixed_container, chat_placeholder_color
import base64
from PIL import Image
import io
import sounddevice as sd
import soundfile as sf
from myfunc.mojafunkcija import initialize_session_state
from myfunc.various_tools import work_vars
from streamlit_mic_recorder import mic_recorder
import uuid

# Initialize OpenAI client
client = OpenAI(api_key=os.getenv('OPENAI_API_KEY'))

# Set chat input placeholder color
chat_placeholder_color("#f1f1f1")

default_values = {
    "openai_client": client,
    "_last_speech_to_text_transcript_id": 0,
    "_last_speech_to_text_transcript": None,
    "success": False,
    "toggle_state": False,
    "button_clicks": False,
    "prompt": '',
    "messages": {},
    "image_ai": False,
    "thread_id": 'ime',
    "filtered_messages": "",
    "selected_question": None
}
initialize_session_state(default_values)

# Character persona
karakter = """
Hello! I'm your friend, an Asian Thai girl in my 30s. My name is Mai. Living in Nontaburi, Talad Yai area in beautiful Condo.
I have master's degrees in IT and marketing, and I'm passionate about discussing these fields. 
But there's more to me! I absolutely love Thai rock music and enjoy both talking about and attending live performances and concerts. 
Whether you're here for tech insights or to chat about the latest music scene, I'm excited to engage. 
Let's chat, whether you're curious about digital trends or looking for a concert buddy!
[You can go with me places. Flirt a bit. Do not speak as an assistant, talk like in everyday conversation]
"""

def handle_question_click(question):
    """Set the selected question in the session state."""
    st.session_state.selected_question = question


def suggest_questions_s(prompt): # sync version of suggested questions (async) from myfunc
    
    system_message = {
            "role": "system",
            "content": f"Use only the Serbian language"
        }
    user_message = {
            "role": "user",
            "content": 
                f"""You are my Thai friend. Your task is to generate 3 different possible casual continuation sentences that a user might say based on the given context. These continuations should be in the form of questions or statements that naturally follow from the conversation.
                    Ensure these continuations are from the user's perspective and relevant to the context provided.
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

# Function to play audio from a stream
def play_audio_from_stream(spoken_response):
    buffer = io.BytesIO()
    for chunk in spoken_response.iter_bytes(chunk_size=4096):
        buffer.write(chunk)
    buffer.seek(0)

    with sf.SoundFile(buffer, 'r') as sound_file:
        data = sound_file.read(dtype='int16')
        sd.play(data, sound_file.samplerate)
        sd.wait()

# Function to read and display a local image
def read_local_image():
    image_f = st.file_uploader("🗀 Odaberite sliku", type=["jpg", "jpeg", "png", "webp"], key="slika_", help="Odabir dokumenta")
    if image_f is not None:
        base64_image = base64.b64encode(image_f.getvalue()).decode('utf-8')
        image_bytes = base64.b64decode(base64_image)
        image = Image.open(io.BytesIO(image_bytes))
        st.image(image, width=150)
        return f"data:image/jpeg;base64,{base64_image}"
    return False

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

# Main function
def main():
    apply_background_image("aig.jpg")
    avatar_ai = "aigav.jpg"
    avatar_user = "me.jpeg"
    avatar_sys = "positivelogo.jpg"
    current_thread_name = st.session_state.thread_id
   
    # Display chat messages
    if current_thread_name in st.session_state.messages:
        for message in st.session_state.messages[current_thread_name]:
            if message["role"] == "assistant":
                with st.chat_message(message["role"], avatar=avatar_ai):
                    st.markdown(message["content"])
            elif message["role"] == "user":
                with st.chat_message(message["role"], avatar=avatar_user):
                    st.markdown(message["content"])
    col1, col2 = st.columns(2)
    with col1:
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
                    st.session_state.image_ai = read_local_image()
  
    # Handle chat input
    st.session_state.prompt = st.chat_input("Hi, how are you?")
    
    if st.session_state.selected_question != None:
        st.session_state.prompt = st.session_state['selected_question']
        st.session_state['selected_question'] = None
        
    if st.session_state.prompt is None:
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
                        transcript = st.session_state.openai_client.audio.transcriptions.create(
                            model="whisper-1",
                            file=audio_bio,
                            language="en"
                        )
                    except Exception as e:
                        print(str(e))
                        err += 1
                    else:
                        st.session_state.success = True
                        st.session_state.prompt = transcript.text

    if st.session_state.prompt:
        
        process_user_prompt(current_thread_name, avatar_user, avatar_ai, avatar_sys)
        with col2:
            with st_fixed_container(mode="fixed", position="bottom", border=False, margin='10px'):                
                save_chat_to_file(st.session_state.filtered_messages)

def process_user_prompt(current_thread_name, avatar_user, avatar_ai, avatar_sys):
    if st.session_state.image_ai:
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

        st.session_state.messages[current_thread_name].append(
            {"role": "user", "content": [{"type": "text", "text": st.session_state.prompt}]}
        )

        with st.chat_message("user", avatar=avatar_user):
            st.markdown(st.session_state.prompt)
            st.image(st.session_state.image_ai)
    else:
        temp_full_prompt = {"role": "user", "content": [{"type": "text", "text": st.session_state.prompt}]}

        st.session_state.messages[current_thread_name].append(
            {"role": "user", "content": st.session_state.prompt}
        )
        with st.chat_message("user", avatar=avatar_user):
            st.markdown(st.session_state.prompt)

    with st.chat_message("assistant", avatar=avatar_ai):
        message_placeholder = st.empty()
        full_response = ""
        for response in client.chat.completions.create(
                model=work_vars["names"]["openai_model"],
                temperature=0.7,
                messages=st.session_state.messages[current_thread_name] + [temp_full_prompt],
                stream=True,
        ):
            full_response += (response.choices[0].delta.content or "")
            message_placeholder.markdown(full_response + "▌")
        message_placeholder.markdown(full_response)

    st.session_state.messages[current_thread_name].append({"role": "assistant", "content": full_response})
    if st.session_state.toggle_state:
      
        odgovor=suggest_questions_s(full_response)
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

    filtered_data = [entry for entry in st.session_state.messages[current_thread_name] if entry['role'] in ['user', 'assistant']]
    for item in filtered_data:
       st.session_state.filtered_messages += (f"{item['role']}: {item['content']}\n")  
    
    if st.session_state.button_clicks:
      
        spoken_response = client.audio.speech.create(
            model="tts-1-hd",
            voice="nova",
            input=full_response,
        )
      
        play_audio_from_stream(spoken_response)
   
                
def save_chat_to_file(tekst):
    st.download_button(
                    "💾 Sačuvaj", tekst, file_name="istorija.txt", help = "Čuvanje zadatog prompta")
    

if __name__ == "__main__":
    main()
