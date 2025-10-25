# Krembot: A Streamlit-based Conversational Assistant

Welcome to the **Krembot** repository! This project houses a set of Python scripts and Streamlit application code designed to implement a conversational, AI-assisted chatbot interface. The chatbot integrates multiple services and APIs, including OpenAI, Pinecone, Neo4j, and a MSSQL database, to provide a robust, dynamic conversational experience. Whether you are building a FAQ assistant, an e-commerce helper, or a specialized domain-specific support bot, the modules here offer an adaptable codebase for your needs.

---

## Table of Contents

1. [Overview](#overview)  
2. [Features](#features)  
3. [Project Structure](#project-structure)  
4. [Setup and Installation](#setup-and-installation)  
5. [Environment Variables](#environment-variables)  
6. [Usage](#usage)  
    - [Running the Streamlit App](#running-the-streamlit-app)  
    - [Configuration and Customization](#configuration-and-customization)  
    - [Adding New Clients](#adding-new-clients)  
    - [Extending the Bot with Tools](#extending-the-bot-with-tools)  
7. [Detailed Modules Explanation](#detailed-modules-explanation)  
    - [1. Main Streamlit Files](#1-main-streamlit-files)  
    - [2. Database Modules (`krembot_db`, `prompt_db`)](#2-database-modules)  
    - [3. Auxiliary Functions and Configuration (`krembot_auxiliary`)](#3-auxiliary-functions-and-configuration)  
    - [4. Conversational Logic and Tools (`krembot_tools`)](#4-conversational-logic-and-tools)  
    - [5. Streamlit UI Utilities (`krembot_stui`)](#5-streamlit-ui-utilities)  
8. [APIs and Integrations](#apis-and-integrations)  
9. [Contributing](#contributing)  
10. [License](#license)

---

## Overview

**Krembot** leverages:
- **[OpenAI](https://openai.com/)** for text (GPT-like) and speech models.
- **[Streamlit](https://streamlit.io/)** for a rapid web interface.
- **[Pinecone](https://www.pinecone.io/)** for vector database (embeddings).
- **[Neo4j](https://neo4j.com/)** for graph-based queries and advanced relationships.
- **MSSQL** for storing conversation history, prompt templates, user feedback, and other data.

It supports:
- Prompt engineering and prompt templates.
- GPT-4-level conversation flows with system, user, tool, assistant roles.
- Automatic retrieval-augmented generation (RAG) via Pinecone or custom DB queries.
- Audio input (speech-to-text) and audio output (text-to-speech).
- Feedback collection for user interactions.

---

## Features

- **Conversation Logging**: Automatically stores user conversations in an MSSQL database to keep track of conversation flows and user questions.
- **Prompt Templates**: Dynamically load and manage system or user prompts via an external MSSQL database or JSON configurations.
- **Retrieval-Augmented Generation**: Query external knowledge bases (Pinecone, Neo4j, custom REST APIs) to provide the most relevant context or answers.
- **Speech-to-Text and Text-to-Speech**: Options to record user questions via microphone and respond with synthesized speech (via OpenAI’s Whisper-like APIs and TTS endpoints).
- **Multi-Client Configuration**: Easily switch “clients” (e.g., `Delfi`, `DentyR`, `ECD`...) by loading environment variables from dedicated JSON files located in `clients/`.
- **UI Components**: Includes custom Streamlit widgets, toggles, feedback forms, chat-based conversation elements with user and assistant avatars.

---

## Project Structure

```
.
├── clients/
│   ├── client_configs.json    # Stores environment settings for multiple clients
│   ├── all_tools.json         # Definitions of Tools used in RAG or specialized tasks
│   └── <client_assets>/       # Images, logos, backgrounds, etc.
│
├── krembot_db.py              # Handles conversation, feedback, prompt logs in MSSQL
├── prompt_db.py               # Additional MSSQL queries for prompt management
├── krembot_auxiliary.py       # Loads env variables, categories, session resets, etc.
├── krembot_tools.py           # Tools for RAG, calling external APIs, Pinecone, Neo4j, etc.
├── krembot_funcs.py           # Utility functions for voice, suggestions, prompts
├── krembot_stui.py            # Streamlit UI utilities (fixed containers, styling)
├── main_app.py (example name) # Streamlit main application script, or 'app.py'
└── ...
```

You’ll see multiple modules targeting different aspects: database interactions, AI logic, prompt management, external API calls, and so on.

---

## Setup and Installation

1. **Clone the repository**:

   ```bash
   git clone https://github.com/yourusername/krembot.git
   cd krembot
   ```

2. **Create and activate a virtual environment**:

   ```bash
   python -m venv venv
   source venv/bin/activate   # Linux/Mac
   # or
   .\venv\Scripts\activate    # Windows
   ```

3. **Install dependencies**:

   ```bash
   pip install -r requirements.txt
   ```
   
   > **Note**: `requirements.txt` should contain all needed packages like `streamlit`, `openai`, `pyodbc`, `neo4j`, `pinecone-client`, `langchain`, etc.

4. **Set up your local MSSQL or remote DB** if you plan to persist conversations. If you prefer, you can comment out certain DB calls in the code, though the conversation flow is best preserved with a DB.

---

## Environment Variables

Krembot depends on multiple environment variables. These can be stored in a `.env` file (loaded manually) or configured on your deployment platform (e.g., Heroku, Docker, etc.). Some key environment variables:

- **OPENAI_API_KEY**: Your OpenAI API key for GPT models.  
- **OPENAI_MODEL**: The GPT model name (e.g., `gpt-3.5-turbo`, `gpt-4`, or an internal variant).  
- **PINECONE_API_KEY**: Pinecone API key for vector DB operations.  
- **PINECONE_HOST**: Pinecone endpoint host.  
- **MSSQL_HOST**, **MSSQL_USER**, **MSSQL_PASS**, **MSSQL_DB**: MSSQL server details.  
- **NEO4J_URI**, **NEO4J_USER**, **NEO4J_PASS**: Neo4j credentials.  
- **CLIENT_FOLDER**: A subfolder under `clients/` for client-specific images and branding.  
- **APP_ID**: App name for selecting different conversation logic or knowledge bases (e.g., `DentyBot`, `ECD`, `Delfi`).  

Additionally, each “client” might have specialized environment variables loaded from `client_configs.json`.

---

## Usage

### Running the Streamlit App

1. **Activate your venv** (if not already):  
   ```bash
   source venv/bin/activate
   ```
2. **Launch Streamlit**:  
   ```bash
   streamlit run main_app.py
   ```
   or whichever script (like `app.py`) contains the Streamlit entry point (`if __name__ == "__main__": main()`).

3. **Open your browser** and navigate to the URL displayed in the console (usually `http://localhost:8501`).

### Configuration and Customization

- In `krembot_auxiliary.py`, there is a `load_config` function that sets environment variables for a chosen client (e.g., `"Delfi"`, `"ECD"`, etc.). Change the line:
  ```python
  which_client_locally = "Delfi"
  ```
  to your desired client, or pass it dynamically via environment variables.

- `initialize_session_state` can be edited to add or remove default session keys.

- `Category_Device_Mapping` in `krembot_auxiliary.py` can be expanded or replaced if your chatbot sorts data by category & device.

### Adding New Clients

To add a new client (e.g., a brand or specialized domain with unique environment variables):

1. Add an entry to `client_configs.json` inside `clients/` with all keys relevant to your new client.  
2. Place any images/logos in `clients/<NewClientName>/`.  
3. Set `CLIENT_FOLDER=<NewClientName>` in your `.env` or environment variable.  
4. Edit any references in the code to handle new categories, prompts, or branding if needed.

### Extending the Bot with Tools

- Tools are stored in `all_tools.json` (see `clients/` folder).  
- You define them in JSON for usage in the “OpenAI function calling” style.  
- Extend `krembot_tools.py` or `krembot_funcs.py` with new logic to handle your tool calls (like shipping tracking, knowledge base searching, booking appointments, etc.).

---

## Detailed Modules Explanation

### 1. Main Streamlit Files

Often, you have a file like `main_app.py`:

```python
# main_app.py

import streamlit as st
import uuid
from openai import OpenAI
from krembot_auxiliary import load_config, initialize_session_state, CATEGORY_DEVICE_MAPPING
from krembot_tools import rag_tool_answer
from krembot_db import ConversationDatabase
# ...

# Load environment variables for a chosen client
which_client_locally = "Delfi"
load_config(which_client_locally)

# Initialize session
default_values = {
    "thread_id": str(uuid.uuid4()),
    "messages": {},
    "app_name": "Krembot",
    # ...
}
initialize_session_state(default_values)

def main():
    st.title("Krembot - Streamlit Chat Assistant")
    # ...
    # Conversation logic, prompt input, calls to rag_tool_answer, etc.
    # ...
    
if __name__ == "__main__":
    main()
```

Key points:
- **Load config** from a chosen client.  
- **Initialize session**.  
- Provide a Streamlit UI for user conversation (`st.chat_message`, `st.chat_input`, etc.).
- Query your RAG functions (like `rag_tool_answer`) to supply context.

### 2. Database Modules

#### `krembot_db.py`
- Manages conversation logs in the `conversations` table.
- **Key functions**:
  - `create_sql_table()`: Creates a table (if non-existent) for storing conversation logs.
  - `add_sql_record()`, `update_sql_record()`, `update_or_insert_sql_record()`: Insert or update conversation data.
  - `query_sql_record()`: Retrieve existing conversation for a thread.
  - `insert_feedback()`: Logs user feedback (thumbs up/down, text, etc.).

#### `prompt_db.py`
- Manages prompt templates, variables, and user records in MSSQL.
- Functions to query or update prompt text, delete or modify prompt records, and get user-based relationships.

### 3. Auxiliary Functions and Configuration

#### `krembot_auxiliary.py`
- **`load_config`**: Reads `client_configs.json` to set environment variables for a chosen client (like “Delfi,” “ECD,” etc.).
- **`initialize_session_state`**: Helper function to add default keys to `st.session_state`.
- **Constants**:
  - `CATEGORY_DEVICE_MAPPING`: Example dictionary for “DentyBot” to map categories to devices.
  - `reset_memory`: Clears conversation context from session.

### 4. Conversational Logic and Tools

#### `krembot_tools.py`
- Houses the main logic for **RAG** (retrieval-augmented generation).  
- Contains classes like `GraphQueryProcessor`, `HybridQueryProcessor`, and `TopListFetcher` to query Neo4j, Pinecone, or other REST endpoints.  
- Example: `rag_tool_answer` decides which “tool” to call (like Pinecone for searching or a direct function for shipping updates).

#### `krembot_funcs.py`
- Utility functions to handle audio (callback, fetch_spoken_response), question suggestions, TTS, etc.  
- Integrates asynchronous tasks for speech generation, so that the system can speak the answer while also suggesting next user queries.

### 5. Streamlit UI Utilities

#### `krembot_stui.py`
- Defines custom CSS, styling, and “fixed containers” for Streamlit.  
- Contains `st_fixed_container`, which keeps a UI element pinned to the top or bottom.  
- Handy if you want a persistent toolbar in Streamlit.

---

## APIs and Integrations

1. **OpenAI**:  
   - *Embeddings*: Generating vector embeddings for text.  
   - *Chat Completions*: GPT-3.5 or GPT-4 to produce chat-based responses.  
   - *Audio (Whisper / TTS)*: For user speech input or text-to-speech responses.  

2. **Pinecone**:  
   - *Indexing and Searching*: Provides vector search for relevant documents, combining dense (GPT embeddings) and sparse (BM25).  

3. **Neo4j**:  
   - *Graph Queries*: For domain knowledge linking, e.g., searching related nodes for book or device details.  

4. **MSSQL**:  
   - *Conversation Logging, Prompt Storage, Feedback Logging*: Everything is stored, including user questions and tool responses.  

5. **External REST**:  
   - *Custom Endpoints*: E.g., `delfi_api_orders` for checking order status, `delfi_api_products` to fetch product details, or `akskurir` for shipping info.

---

## Contributing

Contributions are welcome! If you find a bug or want to add a new feature:

1. Fork the repository.  
2. Create a branch for your new feature (`git checkout -b feature/newTool`).  
3. Push to your branch and open a pull request.  

We appreciate issues, PRs, and suggestions.

---

## License

This project is licensed under the [MIT License](LICENSE). See the `LICENSE` file for details. 

Happy coding and enjoy building your very own conversational assistant with **Krembot**!
