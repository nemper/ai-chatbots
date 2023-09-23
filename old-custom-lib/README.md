# Positive custom functions

Welcome to the Positive custom function Toolkit! This repository contains a collection of custom classes and functions designed to streamline and simplify the process for OpenAI LangChain and Streamlit.

## Overview

This toolkit includes several Python scripts, each serving a specific purpose in the fine-tuning workflow. Below is an overview of the key components. Streamlit is a powerful tool for creating interactive web applications with minimal effort. However, as your applications grow in complexity, you may need additional functionality and customization. This script serves as a utility library for enhancing your Streamlit projects.

## Streamlit Utilities and Callbacks - `mojafunkcija.py`

This Python script, `mojafunkcija.py`, is a collection of Streamlit utilities and callback functions designed to enhance your Streamlit applications. These utilities and callbacks simplify common tasks, such as handling user interactions, displaying information, and integrating with other libraries.

## Key Features

Here are some key features and functions provided by this script:

- **Streamlit Style Customization**: Customize the style of your Streamlit app, including hiding the main menu and footer for a cleaner interface.

- **Positive Authentication**: Implement user authentication using the `streamlit-authenticator` library. Control access levels and user privileges based on predefined credentials.

- **Text File Handling**: Read text files from your local file system, which can be useful for loading data or configurations.

- **Streamlit Redirect**: Redirect the standard output of your Python code to Streamlit's interface. This can be handy for displaying real-time updates or logs.

- **Token Length Calculator**: Calculate the token length of a given text using the `tiktoken` library.

- **Pinecone Statistics**: Display statistics and information about a Pinecone index for embedding retrieval.

- **Data Flattening**: Flatten nested dictionaries into a more accessible format.

- **Streamlit Callbacks**: Implement Streamlit callbacks for handling user interactions and providing dynamic updates.

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
- **Date**: 07.09.2023
- **License**: MIT

For additional information and updates, please refer to the [Streamlit documentation](https://docs.streamlit.io/) and the relevant libraries used in this script.

## How to update

1. After updating the `mojafunkcija.py` from this folder run `python setup.py sdist bdist_wheel`
2. Synchronize with GitHub
3. Upgrade the library `pip install git+https://github.com/djordjethai/myfunc.git --upgrade`
