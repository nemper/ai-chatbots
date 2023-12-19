# Positive custom functions

Welcome to the Positive custom function Toolkit! This repository contains a collection of custom classes and functions designed to streamline and simplify the process for OpenAI LangChain and Streamlit.

## Overview

This toolkit includes several Python scripts, each serving a specific purpose in the fine-tuning workflow. Below is an overview of the key components. Streamlit is a powerful tool for creating interactive web applications with minimal effort. However, as your applications grow in complexity, you may need additional functionality and customization. This script serves as a utility library for enhancing your Streamlit projects.

Here's a description of each function and class in the provided code:

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

14. **read_aad_username()**:
    - Fetches the username from Azure Active Directory using JavaScript.

15. **load_data_from_azure(bsc)**:
    - Loads data from an Azure blob storage container.

16. **upload_data_to_azure(z)**:
    - Uploads data to an Azure blob storage container.

17. **inner_hybrid(upit)**:
    - Performs a hybrid query using Pinecone and a language model, combining dense and sparse vectors for querying.

18. **audio_izlaz(content)**:
    - Converts text to speech using OpenAI's API and plays it back in Streamlit.

19. **priprema()**:
    - Provides a Streamlit interface for selecting different preparatory actions, such as transcribing audio files or reading text from images.

20. **transkript()**:
    - Handles the transcription of audio files and subsequent text correction using OpenAI's Whisper model and Streamlit.

21. **read_local_image()**:
    - Reads and interprets text from a locally uploaded image in Streamlit.

22. **read_url_image()**:
    - Reads and interprets text from an image located at a specified URL in Streamlit.

23. **generate_corrected_transcript(client, system_prompt, audio_file, jezik)**:
    - Generates a corrected transcript from an audio file, chunking the transcript and applying language model corrections.

24. **dugacki_iz_kratkih(uploaded_file, entered_prompt)**:
    - Processes an uploaded file and an entered prompt to produce a detailed response, using a series of language model interactions.

25. **convert_input_to_date(ulazni_datum)**:
    - Converts a date string in a specific format to a datetime object.

26. **parse_serbian_date(date_string)**:
    - Parses Serbian-formatted dates into datetime objects.

27. **send_email(subject, message, from_addr, to_addr, smtp_server, smtp_port, username, password)**:
    - Sends an email using SMTP with the specified parameters.

## Getting Started

To use this script in your Streamlit application, follow these steps:

1. Clone this repository or download the `mojafunkcija.py` file.
    You can also install by putting `git+https://github.com/djordjethai/myfunc.git` in the requirements.txt

    to upgrade local version run: pip install myfunc `git+https://github.com/djordjethai/myfunc.git --upgrade`

2. Import the necessary functions and classes from the script into your Streamlit application.

3. Utilize these utilities and callbacks to enhance your app's functionality.

4. Customize the script as needed to suit your specific requirements.

## Usage Guidelines

Refer to the documentation within the script and the comments provided for each function to understand how to use them effectively. You can also modify and extend these utilities to fit your project's needs.

## Script Details

- **Author**: Positive
- **Date**: 19.12.2023
- **License**: MIT

For additional information and updates, please refer to the [Streamlit documentation](https://docs.streamlit.io/) and the relevant libraries used in this script.

## How to update

1. After updating the `mojafunkcija.py` from this folder run `python setup.py sdist bdist_wheel`
2. Synchronize with GitHub
3. Upgrade the library `pip install git+https://github.com/djordjethai/myfunc.git --upgrade`
