# Positive custom functions

Welcome to the Positive custom function Toolkit! This repository contains a collection of custom classes and functions designed to streamline and simplify the process for OpenAI, LangChain and Streamlit.

## Overview

This toolkit includes several Python scripts, each serving a specific purpose in the fine-tuning workflow. Below is an overview of the key components. Streamlit is a powerful tool for creating interactive web applications with minimal effort. However, as your applications grow in complexity, you may need additional functionality and customization. This script serves as a utility library for enhancing your Streamlit projects.

## Here's a description of each function and class in the provided code for myfunc.mojafunkcija:

1. **show_logo()** :
   - Displays an image in the Streamlit sidebar. It fetches the image from a specified URL and sets its width to 150 pixels.

2. **class StreamlitRedirect**:
   - A class for redirecting output to a Streamlit interface. It cleans and stores text output, and can return the stored output.

3. **tiktoken_len(text)**:
   - Uses the `tiktoken` library to tokenize the given text and returns the number of tokens.

4. **pinecone_stats(index, index_name)**:
   - Retrieves and displays statistics about a Pinecone index in Streamlit. It formats and shows these statistics as a DataFrame.

5. **flatten_dict(d, parent_key="", sep="_")**:
   - A utility function to flatten a nested dictionary, combining keys with a separator.

6. **def_chunk()**:
   - Provides a Streamlit interface to select chunk size and overlap for text processing, returning the selected values.

7. **print_nested_dict_st(d)**:
   - Recursively prints the contents of a nested dictionary in Streamlit.

8. **class StreamHandler(BaseCallbackHandler)**:
   - A callback handler class for Streamlit that handles new tokens from a language model, formats them, and updates the Streamlit container with the text.

9. **open_file(filepath)**:
   - Opens a file and returns its content as a string.

10. **st_style()**:
   - Applies CSS styles to hide certain Streamlit default interface elements.

11. **positive_login(main, verzija)**:
    - Handles user authentication using Streamlit Authenticator and YAML configuration, then runs the main program if authentication is successful.

12. **init_cond_llm(i=None)**:
    - Provides a Streamlit interface for selecting a language model and temperature setting.

13. **greska(e)**:
    - Handles different error scenarios in Streamlit and displays appropriate warnings.

14. **convert_input_to_date(ulazni_datum)**:
Converts a given date string in the format 'dd.mm.yyyy.' to a Python `datetime` object. If the input string is not in the correct format, it prints an error message and returns `None`.

15. **parse_serbian_date(date_string)**;
Converts a date string with Serbian month names to a Python `datetime` object. It first translates Serbian month names to English and then parses the date.

16. **send_email(subject, message, from_addr, to_addr, smtp_server, smtp_port, username, password)**:
Sends an email with the specified subject and message from `from_addr` to `to_addr` using the specified SMTP server. It uses the provided username and password for authentication.

17. **sacuvaj_dokument(content, file_name)**:
Saves the given `content` in three different formats: `.txt`, `.docx`, and `.pdf`. It provides download buttons for each format using Streamlit's `download_button` function. The function takes care of encoding, formatting, and conversion to ensure compatibility across different formats.

## Here's a description of each function and class in the provided code for myfunc.asistenti:

1. **HybridQueryProcessor Class**
The HybridQueryProcessor class is a versatile tool for performing advanced queries in text-based applications. It's designed to integrate with Pinecone and supports a range of functionalities from initializing the Pinecone connection, embedding text, to executing and processing hybrid queries            .

    ***Methods***
    1. init_pinecone(): Initializes the Pinecone connection and index.
    2. get_embedding(text, model): Retrieves the embedding for the given text using the specified model.
    3. hybrid_score_norm(dense, sparse): Normalizes the scores from dense and sparse vectors using the alpha value.
    4. hybrid_query(upit, top_k): Executes a hybrid query on the Pinecone index using the provided query text.
    5. process_query_results(upit, score): Processes the query results and formats them for a chat or dialogue system.

    ***Features***
    Easy integration with Pinecone for executing complex text queries.
    Supports both dense and sparse vector searches.
    Customizable query processing and result formatting for chat or dialogue systems.

2. **read_aad_username()**:
    - Fetches the username from Azure Active Directory using JavaScript.

3. **load_data_from_azure(bsc)**:
    - Loads data from an Azure blob storage container.

4. **upload_data_to_azure(z)**:
    - Uploads data to an Azure blob storage container.

5. **audio_izlaz(content)**:
    - Converts text to speech using OpenAI's API and plays it back in Streamlit.

6. **priprema()**:
    - Provides a Streamlit interface for selecting different preparatory actions, such as transcribing audio files or reading text from images.

7. **transkript()**:
    - Handles the transcription of audio files and subsequent text correction using OpenAI's Whisper model and Streamlit.

8. **read_local_image()**:
    - Reads and interprets text from a locally uploaded image in Streamlit.

9. **read_url_image()**:
    - Reads and interprets text from an image located at a specified URL in Streamlit.

10. **generate_corrected_transcript(client, system_prompt, audio_file, jezik)**:
    - Generates a corrected transcript from an audio file, chunking the transcript and applying language model corrections.

11. **dugacki_iz_kratkih(uploaded_file, entered_prompt)**:
    - Processes an uploaded file and an entered prompt to produce a detailed response, using a series of language model interactions.

    
## Getting Started

To use this script in your Streamlit application, follow these steps:

1. Clone this repository or download the `mojafunkcija.py` and `asistenti.py` file.
    You can also install by putting `git+https://github.com/djordjethai/myfunc.git` in the requirements.txt

    to upgrade local version run: pip install myfunc `git+https://github.com/djordjethai/myfunc.git --upgrade`

2. Import the necessary functions and classes from the script into your Streamlit application.

3. Utilize these utilities and callbacks to enhance your app's functionality.

4. Customize the script as needed to suit your specific requirements.

## Usage Guidelines

Refer to the documentation within the script and the comments provided for each function to understand how to use them effectively. You can also modify and extend these utilities to fit your project's needs.

## Script Details

- **Author**: Positive
- **Date**: 27.12.2023
- **License**: MIT

## How to update

1. After updating from this folder run `python setup.py sdist bdist_wheel`
2. Synchronize with GitHub
3. Upgrade the library `pip install git+https://github.com/djordjethai/myfunc.git --upgrade`
