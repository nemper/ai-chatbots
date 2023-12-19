import streamlit as st
import yaml
from yaml.loader import SafeLoader
import streamlit_authenticator as stauth
from langchain.callbacks.base import BaseCallbackHandler
from io import StringIO, BytesIO
import re
import pandas as pd
import requests
import os
import base64
from PIL import Image
from datetime import datetime
from smtplib import SMTP
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from docx import Document
import io
from docx.enum.text import WD_ALIGN_PARAGRAPH


def show_logo():
    with st.sidebar:
        st.image(
            "https://test.georgemposi.com/wp-content/uploads/2023/05/positive-logo-red.jpg",
            width=150,
        )


class StreamlitRedirect:
    def __init__(self):
        self.output_buffer = StringIO()

    def write(self, text):
        cleaned_text = re.sub(r"\x1b[^m]*m|[^a-zA-Z\s]", "", text)
        self.output_buffer.write(cleaned_text + "\n")  # Store the output

    def get_output(self):
        return self.output_buffer.getvalue()


def tiktoken_len(text):
    import tiktoken

    tokenizer = tiktoken.get_encoding("p50k_base")
    tokens = tokenizer.encode(text, disallowed_special=())
    return len(tokens)


def pinecone_stats(index, index_name):
    import pandas as pd

    index_name = index_name
    index_stats_response = index.describe_index_stats()
    index_stats_dict = index_stats_response.to_dict()
    st.subheader("Status indexa:")
    st.write(index_name)
    flat_index_stats_dict = flatten_dict(index_stats_dict)

    # Extract header and content from the index
    header = [key.split("_")[0] for key in flat_index_stats_dict.keys()]
    content = [
        key.split("_")[1] if len(key.split("_")) > 1 else ""
        for key in flat_index_stats_dict.keys()
    ]

    # Create a DataFrame from the extracted data
    df = pd.DataFrame(
        {
            "Header": header,
            "Content": content,
            "Value": list(flat_index_stats_dict.values()),
        }
    )

    # Set the desired number of decimals for float values
    pd.options.display.float_format = "{:.2f}".format

    # Apply formatting to specific columns using DataFrame.style
    styled_df = df.style.apply(
        lambda x: ["font-weight: bold" if i == 0 else "" for i in range(len(x))], axis=1
    ).format({"Value": "{:.0f}"})

    # Display the styled DataFrame as a table using Streamlit
    st.write(styled_df)


def flatten_dict(d, parent_key="", sep="_"):
    items = []
    for k, v in d.items():
        new_key = f"{parent_key}{sep}{k}" if parent_key else k
        if isinstance(v, dict):
            items.extend(flatten_dict(v, new_key, sep=sep).items())
        else:
            items.append((new_key, v))
    return dict(items)


def def_chunk():
    with st.sidebar:
        st.info("Odaberite velicinu chunka i overlap")
        chunk_size = st.slider(
            "Set chunk size in characters (50 - 8000)",
            50,
            8000,
            1500,
            step=100,
            help="Velicina chunka odredjuje velicinu indeksiranog dokumenta. Veci chunk obezbedjuje bolji kontekst, dok manji chunk omogucava precizniji odgovor.",
        )
        chunk_overlap = st.slider(
            "Set overlap size in characters (0 - 1000), must be less than the chunk size",
            0,
            1000,
            0,
            step=10,
            help="Velicina overlapa odredjuje velicinu preklapanja sardzaja dokumenta. Veci overlap obezbedjuje bolji prenos konteksta.",
        )
        return chunk_size, chunk_overlap


def print_nested_dict_st(d):
    for key, value in d.items():
        if isinstance(value, dict):
            st.write(f"{key}:")
            print_nested_dict_st(value)
        else:
            st.write(f"{key}: {value}")


class StreamHandler(BaseCallbackHandler):
    def __init__(self, container):
        self.container = container
        self.text = ""

    def on_llm_new_token(self, token: str, **kwargs) -> None:
        token = (
            token.replace('"', "").replace("{", "").replace("}", "").replace("_", " ")
        )
        self.text += token
        self.container.success(self.text)

    def reset_text(self):
        self.text = ""

    def clear_text(self):
        self.container.empty()


def open_file(filepath):
    with open(filepath, "r", encoding="utf-8") as infile:
        sadrzaj = infile.read()
        infile.close()
        return sadrzaj


def st_style():
    hide_streamlit_style = """
                <style>
                MainMenu {visibility: hidden;}
                footer {visibility: hidden;}
                </style>
                """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)


def positive_login(main, verzija):
    with open("config.yaml") as file:
        config = yaml.load(file, Loader=SafeLoader)

        authenticator = stauth.Authenticate(
            config["credentials"],
            config["cookie"]["name"],
            config["cookie"]["key"],
            config["cookie"]["expiry_days"],
            config["preauthorized"],
        )

        name, authentication_status, username = authenticator.login(
            "Login to Positive Apps", "main"
        )

        # Get the email based on the name variable
        email = config["credentials"]["usernames"][username]["email"]
        access_level = config["credentials"]["usernames"][username]["access_level"]
        st.session_state["name"] = name
        st.session_state["email"] = email
        st.session_state["access_level"] = access_level

    if st.session_state["authentication_status"]:
        with st.sidebar:
            st.caption(f"Ver 1.0.6")
            authenticator.logout("Logout", "main", key="unique_key")
        # if login success run the program
        main()
    elif st.session_state["authentication_status"] is False:
        st.error("Username/password is incorrect")
    elif st.session_state["authentication_status"] is None:
        st.warning("Please enter your username and password")

    return name, authentication_status, email


# define model and temperature
def init_cond_llm(i=None):
    with st.sidebar:
        st.info("Odaberite Model i temperaturu")
        model = st.selectbox(
            "Odaberite model",
            ("gpt-3.5-turbo", "gpt-3.5-turbo-16k", "gpt-4", "gpt-4-1106-preview"),
            key="model_key" if i is None else f"model_key{i}",
            help="Modeli se razlikuju po kvalitetu, brzini i ceni upotrebe.",
        )
        temp = st.slider(
            "Set temperature (0=strict, 1=creative)",
            0.0,
            2.0,
            step=0.1,
            key="temp_key" if i is None else f"temp_key{i}",
            help="Temperatura utice na kreativnost modela. Sto je veca temperatura, model je kreativniji, ali i manje pouzdan.",
        )
    return model, temp


# error handling on Serbian


def greska(e):
    if "maximum context length" in str(e):
        st.warning(
            f"Nisam u mogucnosti za zavrsim tekst. Pokusajte sa modelom koji ima veci kontekst.")
    elif "Rate limit" in str(e):
        st.warning(
            f"Nisam u mogucnosti za zavrsim tekst. Broj zahteva modelu prevazilazi limite, pokusajte ponovo za nekoliko minuta.")
    else:
        st.warning(
            f"Nisam u mogucnosti za zavrsim tekst. Pokusajte ponovo za nekoliko minuta. Opis greske je:\n {e}")


# NEOCHATBOT
from streamlit_javascript import st_javascript
from ast import literal_eval
from azure.storage.blob import BlobServiceClient
from os import environ
import pinecone
from openai import OpenAI
from pinecone_text.sparse import BM25Encoder
client = OpenAI()
from langchain.prompts.chat import (
    SystemMessagePromptTemplate,
    HumanMessagePromptTemplate,
    ChatPromptTemplate,
    )
from html2docx import html2docx
import markdown
import pdfkit


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



def inner_hybrid(upit):
    alpha = 0.5

    pinecone.init(
        api_key=environ["PINECONE_API_KEY_POS"],
        environment=environ["PINECONE_ENVIRONMENT_POS"],
    )
    index = pinecone.Index("positive")

    def hybrid_query():
        def get_embedding(text, model="text-embedding-ada-002"):
            text = text.replace("\n", " ")
            return client.embeddings.create(input = [text], model=model).data[0].embedding
    
        hybrid_score_norm = (lambda dense, sparse, alpha: 
                                ([v * alpha for v in dense], 
                                {"indices": sparse["indices"], 
                                "values": [v * (1 - alpha) for v in sparse["values"]]}
                                ))
        hdense, hsparse = hybrid_score_norm(
            sparse = BM25Encoder().fit([upit]).encode_queries(upit),
            dense=get_embedding(upit),
            alpha=alpha,
        )
        return index.query(
            top_k=6,
            vector=hdense,
            sparse_vector=hsparse,
            include_metadata=True,
            namespace=st.session_state.namespace,
            ).to_dict()

    tematika = hybrid_query()

    uk_teme = ""
    for _, item in enumerate(tematika["matches"]):
        if item["score"] > 0.05:    # score
            uk_teme += item["metadata"]["context"] + "\n\n"

    system_message = SystemMessagePromptTemplate.from_template(
        template="You are a helpful assistent. You always answer in the Serbian language.").format()

    promptFT = """
    Use the context provided to anwer the question. 

    Context:
    ____________________

    {uk_teme}
    ____________________

    Question: {zahtev} 
    ____________________

    Be sure to use the writing style of {ft_model} 
    """
    human_message = HumanMessagePromptTemplate.from_template(
        template=promptFT.format(
            zahtev=upit,
            uk_teme=uk_teme,
            ft_model="gpt-4-1106-preview",))
    
    return str(ChatPromptTemplate(messages=[system_message, human_message]))


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
                client = OpenAI()
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

    client = OpenAI()
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
    client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    uploaded_text = uploaded_text[0].page_content

    if uploaded_text is not None:
        all_prompts = {
            "p_system_1": "You are a helpful assistant that identifies topics in a provided text.",
            "p_user_1": "Please provide a numerated list of topics described in the text - one topic per line. \
                Be sure not to write anything else.",
            "p_system_2": "You are a helpful assistant that corrects stuctural mistakes in a provided text. \
                You only check if the rules were followed, and then you correct the mistakes if there are any.",
            "p_user_2": f"Please check if the previous assistant generated a response that is inline with the following request: \
                'Please provide a numerated list of topics described in the text - one topic per line. Be sure not to write anything else.' \
                    If there are any mistakes, please correct them; e.g. if there is a short intro before the topic list or similar. \
                        If there are no mistakes, just send the text back.",
            "p_system_3": "You are a helpful assistant that summarizes only parts of the provided text that are related to the requested topic.",
            "p_user_3": "Please summarize the above text focusing only on the topic: {topic}. \
                Add a simple title (don't write hashes or similar) and 2 empty lines before and after the summary. \
                    Be sure to always write in Serbian." + f"{entered_prompt}",
            "p_system_4": "You are a helpful assistant that creates a conclusion of the provided text.",
            "p_user_4": "Please create a conclusion of the above text."
        }
        

        def get_response(p_system, p_user_ext):
            response = client.chat.completions.create(
                model="gpt-4-1106-preview",
                messages=[
                    {"role": "system", "content": all_prompts[p_system]},
                    {"role": "user", "content": uploaded_text},
                    {"role": "user", "content": p_user_ext}
                ]
            )
            return response.choices[0].message.content.strip()


        response = get_response("p_system_1", all_prompts["p_user_1"])
        
        # ovaj double check je veoma moguce bespotreban, no sto reskirati
        # response = get_response("p_system_2", all_prompts["p_user_2"]).split('\n')
        topics = [item for item in response if item != ""]  # just in case - triple check

        final_summary = ""
        i = 0
        imax = len(topics)

        pocetak_summary = "At the begining of the text write the date (dd.mm.yy), topics that vere discussed and participants."

        for topic in topics:
            if i == 0:
                summary = get_response("p_system_3", f"{(pocetak_summary + all_prompts['p_user_3']).format(topic=topic)}")
                i += 1
            else:
                summary = get_response("p_system_3", f"{all_prompts['p_user_3'].format(topic=topic)}")
                i += 1

            st.info(f"Summarizing topic: {topic} - {i}/{imax}")
            final_summary += f"{summary}\n\n"

        final_summary += f"{get_response('p_system_4', all_prompts['p_user_4'])}"
        
        return final_summary
    
    else:
        return "Please upload a text file."


# TEST
def convert_input_to_date(ulazni_datum):
    try:
        date_obj = datetime.strptime(ulazni_datum, "%d.%m.%Y.")
        return date_obj
    except ValueError:
        print("Invalid date format. Please enter a date in the format 'dd.mm.yyyy.'")
        return None
    

def parse_serbian_date(date_string):
    serbian_month_names = {
        "januar": "January",
        "februar": "February",
        "mart": "March",
        "april": "April",
        "maj": "May",
        "jun": "June",
        "jul": "July",
        "avgust": "August",
        "septembar": "September",
        "oktobar": "October",
        "novembar": "November",
        "decembar": "December"
    }

    date_string = date_string.lower()

    for serbian_month, english_month in serbian_month_names.items():
        date_string = date_string.replace(serbian_month, english_month)

    return datetime.strptime(date_string.strip(), "%d. %B %Y")


def send_email(subject, message, from_addr, to_addr, smtp_server, smtp_port, username, password):
    msg = MIMEMultipart()
    msg['From'] = from_addr
    msg['To'] = to_addr
    msg['Subject'] = subject

    msg.attach(MIMEText(message, 'plain'))

    server = SMTP(smtp_server, smtp_port)
    server.starttls()
    server.login(username, password)
    text = msg.as_string()
    server.sendmail(from_addr, to_addr, text)
    server.quit()


def sacuvaj_dokument(content, file_name):
    st.info("Čuva dokument")
    options = {
        "encoding": "UTF-8",  # Set the encoding to UTF-8
        "no-outline": None,
        "quiet": "",
    }
    
    html = markdown.markdown(content)
    buf = html2docx(html, title="Content")
    # Creating a document object
    doc = Document(io.BytesIO(buf.getvalue()))
    # Iterate over the paragraphs and set them to justified
    for paragraph in doc.paragraphs:
        paragraph.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY
    # Creating a byte buffer object
    doc_io = io.BytesIO()
    doc.save(doc_io)
    doc_io.seek(0)  # Rewind the buffer to the beginning

    pdf_data = pdfkit.from_string(html, False, options=options)

    st.download_button(
        "Download as .txt",
        content,
        file_name=f"{file_name}.txt",
        help="Čuvanje dokumenta",
    )
            
    st.download_button(
        label="Download as .docx",
        data=doc_io,
        file_name=f"{file_name}.docx",
        mime="docx",
        help= "Čuvanje dokumenta",
    )
            
    st.download_button(
        label="Download as .pdf",
        data=pdf_data,
        file_name=f"{file_name}.pdf",
        mime="application/octet-stream",
        help= "Čuvanje dokumenta",
    )
    
