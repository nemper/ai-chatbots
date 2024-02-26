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
import openai


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
    

def upload_data_to_azure(z, filename):
    """ Upload data to Azure Blob Storage. """    
    z["fajlovi"] = z["fajlovi"].apply(lambda z: str(z))
    blob_client = BlobServiceClient.from_connection_string(
        environ.get("AZ_BLOB_API_KEY")).get_blob_client("positive-user", filename)
    blob_client.upload_blob(z.to_csv(index=False), overwrite=True)

# ZAPISNIK
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



# This function does transcription of the audio file and then corrects the transcript. 
# It calls the function transcribe and generate_corrected_transcript
def transkript():
    """ Convert mp3 to text. """
    
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
                        You are the Serbian language expert. You must fix grammar and spelling errors and create paragraphs based on context but otherwise keep the text as is, in the Serbian language. \
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
    """ Describe the image from a URL. """    
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
    """ Generate corrected transcript. 
        Parameters: 
            client (openai): The OpenAI client.
            system_prompt (str): The system prompt.
            audio_file (str): The audio file.
            jezik (str): The language of the audio file.
        """    
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
            model="gpt-4-turbo-preview",
            temperature=0,
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": chunk}])
    
        corrected_transcript += " " + response.choices[0].message.content.strip()

    return corrected_transcript


def dugacki_iz_kratkih(uploaded_text, entered_prompt):
    """ Generate a summary of a long text. 
        Parameters: 
            uploaded_text (str): The long text.
            entered_prompt (str): The prompt.
        """    
   
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
                model="gpt-4-turbo-preview",
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

