# in myfunc.asistenti.py
import base64
import openai
import os
import pandas as pd
import requests
import streamlit as st

from ast import literal_eval
from azure.storage.blob import BlobServiceClient
from io import BytesIO, StringIO
from json import loads as json_loads
from os import environ
from PIL import Image
from streamlit_javascript import st_javascript
import glob
from pydub import AudioSegment

from myfunc.denti import work_prompts

mprompts = work_prompts()


# in myfunc.asistenti.py
def read_aad_username():
    """ Read username from Azure Active Directory. """
    
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


# in myfunc.asistenti.py
def load_prompts_from_azure(bsc, inner_dict, key):
    blob_client = bsc.get_container_client("positive-user").get_blob_client("positive_prompts.json")
    prompts = json_loads(blob_client.download_blob().readall().decode('utf-8'))
    
    return prompts["POSITIVE"][inner_dict][key]


# in myfunc.asistenti.py
def load_data_from_azure(bsc, filename, username=None, is_from_altass=False):
    """ Load data from Azure Blob Storage. """
    try:
        blob_service_client = bsc
        container_client = blob_service_client.get_container_client("positive-user")
        blob_client = container_client.get_blob_client(filename)

        streamdownloader = blob_client.download_blob()
        if is_from_altass:
            df = pd.read_csv(StringIO(streamdownloader.readall().decode("utf-8")))
            if username:
                df = df[df['Username'] == username]
        else:
            df = pd.read_csv(StringIO(streamdownloader.readall().decode("utf-8")), usecols=["user", "chat", "ID", "assistant", "fajlovi"])
            df["fajlovi"] = df["fajlovi"].apply(literal_eval)
        return df.dropna(how="all")
    
    except FileNotFoundError:
        return pd.DataFrame(columns=['Username', 'Thread ID', 'Thread Name', 'Conversation']) if is_from_altass else {"Nisam pronasao fajl"}
    except Exception as e:
        return pd.DataFrame(columns=['Username', 'Thread ID', 'Thread Name', 'Conversation']) if is_from_altass else {f"An error occurred: {e}"}
    

# in myfunc.asistenti.py
def upload_data_to_azure(z, filename):
    """ Upload data to Azure Blob Storage. """
    if "fajlovi" in z.columns:
        z["fajlovi"] = z["fajlovi"].apply(lambda z: str(z))
    blob_client = BlobServiceClient.from_connection_string(
        environ.get("AZ_BLOB_API_KEY")).get_blob_client("positive-user", filename)
    blob_client.upload_blob(z.to_csv(index=False), overwrite=True)


# in myfunc.asistenti.py
def audio_izlaz(content):
    """ Convert text to speech and save the audio file. 
        Parameters: content (str): The text to be converted to speech.
    """
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

    # Save AudioSegment as MP3 file
    mp3_data = BytesIO(audio)
    #audio_segment.export(mp3_data, format="mp3")
    mp3_data.seek(0)

    # Display the audio using st.audio
    st.caption("mp3 fajl možete download-ovati odabirom tri tačke ne desoj strani audio plejera")
    st.audio(mp3_data.read(), format="audio/mp3")


# in myfunc.asistenti.py
# in myfunc.asistenti.py
def priprema():
    """ Prepare the data for the assistant. """    
    
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


# in myfunc.asistenti.py
def transkript():
    """This function does transcription of the audio file and then corrects the transcript.
    It calls the function transcribe and generate_corrected_transcript
    Convert mp3 to text. """
    
    # Read OpenAI API key from env
    with st.sidebar:  # App start
        st.info("Konvertujte audio/video u TXT")
        audio_file = st.file_uploader(
            "Odaberite audio/video fajl",
            key="audio_",
            help="Odabir dokumenta",
        )
        transcript = ""
        
        if audio_file is not None:
            st.audio(audio_file.getvalue(), format="audio/mp3")
            placeholder = st.empty()

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
                        system_prompt=mprompts["text_from_audio"]
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
                delete_mp3_files(".")


# in myfunc.asistenti.py
def read_local_image():
    """ Describe the image from a local file. """

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

        with placeholder.form(key="my_image", clear_on_submit=False):
            default_text = mprompts["text_from_image"]
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
                      "model": os.getenv("OPENAI_MODEL"),
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


# in myfunc.asistenti.py
def read_url_image():
    """ Describe the image from a URL. """    
    # version url

    client = openai
    
    st.info("Čita sa slike sa URL")
    content = ""
    
    #with placeholder.form(key="my_image_url_name", clear_on_submit=False):
    img_url = st.text_input("Unesite URL slike ")
    #submit_btt = st.form_submit_button(label="Submit")
    image_f = os.path.basename(img_url)   
    if img_url !="":
        st.image(img_url, width=150)
        placeholder = st.empty()    
    #if submit_btt:        
        with placeholder.form(key="my_image_url", clear_on_submit=False):
            default_text = mprompts["text_from_image"]
        
            upit = st.text_area("Unesite uputstvo ", default_text)
            submit_button = st.form_submit_button(label="Submit")
            if submit_button:
                with st.spinner("Sačekajte trenutak..."):         
                    
                    response = client.chat.completions.create(
                      model=os.getenv("OPENAI_MODEL"),
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


# in myfunc.asistenti.py
def generate_corrected_transcript(client, system_prompt, audio_file, jezik):
    """ Generate corrected transcript. 
        Parameters: 
            client (openai): The OpenAI client.
            system_prompt (str): The system prompt.
            audio_file (str): The audio file.
            jezik (str): The language of the audio file.
        """    
    client= openai
        

    def convert_to_mp3(file_path, output_path):
        # Load the audio file
        audio = AudioSegment.from_file(file_path)
        # Set parameters: mono, 16000Hz
        audio = audio.set_channels(1).set_frame_rate(16000)
        # Export as mp3
        audio.export(output_path, format="mp3", bitrate="128k")

    def transcribe_audio(file_path, jezik):
        with open(file_path, "rb") as audio_file:
            transcript = client.audio.transcriptions.create(
            model="whisper-1", 
            file=audio_file, 
            language=jezik,
            response_format="text"
            )
        return transcript
            

    def split_mp3_file(input_path, output_directory, max_file_size_mb=20, max_duration_minutes=45, jezik=jezik):
        # Load the mp3 file
        audio = AudioSegment.from_file(input_path, format="mp3")
        
        # Calculate the duration limit for the file size (in seconds)
        max_file_size_bytes = max_file_size_mb * 1024 * 1024
        bitrate_kbps = 128  # Assuming a bitrate of 128 kbps
        
        max_duration_seconds_file_size = (max_file_size_bytes * 8) / (bitrate_kbps * 1000)
        
        # Duration limit in seconds
        max_duration_seconds_time = max_duration_minutes * 60
        
        # Use the smaller of the two duration limits
        max_duration_seconds = min(max_duration_seconds_file_size, max_duration_seconds_time)
        
        # Split the audio file
        parts = []
        for i in range(0, len(audio), int(max_duration_seconds * 1000)):
            part = audio[i:i + int(max_duration_seconds * 1000)]
            parts.append(part)
        
        # Export each part and transcribe
        all_transcripts = []
        for idx, part in enumerate(parts):
            part_path = os.path.join(output_directory, f"{os.path.splitext(os.path.basename(input_path))[0]}_part{idx + 1}.mp3")
            part.export(part_path, format="mp3", bitrate="128k")
            st.caption(f"Kreiram transkript {part_path}")
            transcript = transcribe_audio(part_path, jezik)
            all_transcripts.append(transcript)
        combined_transcript = " ".join(all_transcripts)
        return combined_transcript
    
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

    convert_to_mp3(audio_file, "output.mp3")
    transcript = split_mp3_file("output.mp3", ".", jezik=jezik)
    
    st.caption("delim u delove po 1000 reci")
    chunks = chunk_transcript(transcript, 1000)
    broj_delova = len(chunks)
    st.caption (f"Broj delova je: {broj_delova}")
    corrected_transcript = ""

    # Loop through the token chunks
    for i, chunk in enumerate(chunks):
        
        st.caption(f"Obradjujem {i + 1}. deo...")
          
        response = client.chat.completions.create(
            model=os.getenv("OPENAI_MODEL"),
            temperature=0,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": chunk}])
    
        corrected_transcript += " " + response.choices[0].message.content.strip()

    return corrected_transcript

def delete_mp3_files(directory):
    mp3_files = glob.glob(os.path.join(directory, "*.mp3"))
    for mp3_file in mp3_files:
        try:
            os.remove(mp3_file)
        except Exception as e:
            st.info(f"Error deleting {mp3_file}: {e}")




