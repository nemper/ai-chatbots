import streamlit as st
import yaml
from yaml.loader import SafeLoader
import streamlit as st
import streamlit_authenticator as stauth
from langchain.callbacks.base import BaseCallbackHandler
from io import StringIO
import re


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
            f"Nisam u mogucnosti za zavrsim tekst. Pokusajte sa modelom koji ima veci kontekst."
        )
    elif "Rate limit" in str(e):
        st.warning(
            f"Nisam u mogucnosti za zavrsim tekst. Broj zahteva modelu prevazilazi limite, pokusajte ponovo za nekoliko minuta."
        )
    else:
        st.warning(
            f"Nisam u mogucnosti za zavrsim tekst. Pokusajte ponovo za nekoliko minuta. Opis greske je:\n {e}"
        )


# NEOCHATBOT
from streamlit_javascript import st_javascript
import streamlit as st
import pandas as pd
from io import StringIO
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


