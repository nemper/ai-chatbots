# Chatbot Using OpenAI GPT-3.5 Turbo and Various Tools

This Python code defines a chatbot application that utilizes the OpenAI GPT-3.5 Turbo model along with several other tools. Let's break down the key components and functionalities of this code:

## Import Statements

The code begins with a series of import statements. These statements import necessary libraries and modules for the chatbot application, including:

- `pinecone`: A module used for working with Pinecone, an embedding index database.
- `streamlit`: The Streamlit library for creating web-based user interfaces.
- Custom functions and classes, such as `StreamHandler`, `StreamlitRedirect`, and `RelevanceEvaluator`.

## Environment Variables

Next, the code sets several environment variables that are essential for the chatbot and related tools to function correctly. These environment variables include:

- `LANGCHAIN_PROJECT`: A project identifier for LangSmith.
- `LANGCHAIN_TRACING_V2`: A flag indicating the use of LangSmith's tracing version.
- `LANGCHAIN_ENDPOINT`: The endpoint URL for the LangSmith API.
- `LANGCHAIN_API_KEY`: An API key for LangSmith (retrieved using `os.environ.get`).

## Streamlit Configuration

The code configures the Streamlit application with specific settings:

- `st.set_page_config`: Configures the page title, icon, and layout of the Streamlit app.

## Function Definitions

The code defines several functions, including:

- `whoimi(input="")`: A function that provides a positive AI assistant's description.

- `new_chat()`: A function to initialize a new chat session by clearing previous messages and state.

- `main()`: The main function that contains the core logic of the chatbot application. This function initializes and configures various tools and APIs, handles user input, interacts with the GPT-3.5 Turbo model, and manages feedback and evaluations.

## Tool Initialization

The code initializes various tools and APIs that the chatbot uses, including:

- Pinecone for embeddings lookup.
- Google Search API for internet searches.
- A custom tool for answering questions about Positive AI Assistant.

## Chat Interaction

Within the `main()` function, the code handles user interactions:

- It waits for user input using Streamlit's `st.chat_input`.

- It formats and sends the user's input to the GPT-3.5 Turbo model for processing.

- It captures and displays the model's response and any system messages or intermediate results.

- It allows users to provide feedback and ratings for the chatbot's responses.

## Feedback Handling

The code handles user feedback, including rating the chatbot's responses and providing comments. It uses emoji-based feedback for user ratings.

## Streamlit Application

Finally, the code applies Streamlit styling and checks the deployment environment. If the environment is Streamlit, it initiates the chatbot by calling the `positive_login()` function.

In summary, this code defines a comprehensive chatbot application that incorporates OpenAI's GPT-3.5 Turbo model, Pinecone for embeddings lookup, Google Search for internet searches, and a custom tool for answering questions. It provides a user-friendly interface for interacting with the chatbot, rating its responses, and providing feedback.
