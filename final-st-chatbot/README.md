# Overview

This Python script is used to create a chatbot application with Streamlit, powered by OpenAI's API and enhanced by additional tools for handling conversations, file inputs, and feedback collection. The script enables the chatbot to respond to user inputs and manage the conversation history, including storing feedback in a database.

## Key Features

1. **Session State Initialization**: 
   - The script initializes session variables like conversation history, thread ID, and feedback storage using Streamlit's `session_state`.
   
2. **OpenAI API Integration**:
   - Utilizes OpenAI’s API (like `gpt-4o` model) to generate responses based on user inputs, including handling audio transcription via OpenAI’s Whisper model.
   
3. **Microphone Recorder**:
   - Captures voice inputs through a microphone using `streamlit_mic_recorder`. It transcribes audio input into text using OpenAI's Whisper and sends it as a query to the chatbot.

4. **Conversation Handling**:
   - The script handles multi-threaded conversations where each thread has its own conversation history. It stores and retrieves conversations from a database using the `ConversationDatabase` class.

5. **Feedback Mechanism**:
   - After receiving a response from the assistant, users can provide feedback using thumbs up/down and an optional text input. The feedback is stored in the database.

6. **File Input**:
   - Users can upload files (e.g., images) to be used in the conversation. This information is appended to the chat log and integrated into the conversation.

7. **Chat Display**:
   - The user and assistant messages are displayed in a chat-style interface. The script also supports avatars for users, assistants, and system messages.

8. **Real-Time Streaming**:
   - The assistant's responses are streamed in real-time, creating an interactive user experience. Additionally, users can enable audio playback of responses.

9. **Utilities**:
   - The script includes utilities like conversation history download, conversation reset, and feedback collection, enhancing user interaction.

## How It Works

1. **Session State Initialization**:
   - Session variables like `thread_id`, `messages`, `feedback`, and `prompt` are initialized using `initialize_session_state()`.
   
2. **Main Function**:
   - The `main()` function manages the conversation flow:
     - If a thread ID is missing, a new one is generated.
     - Conversation history is loaded from the database and displayed in the chat interface.
     - User inputs are processed, and the assistant’s responses are fetched from OpenAI.
     - Responses are displayed, and users can provide feedback or download the conversation history.

3. **Feedback Handling**:
   - The `handle_feedback()` function collects and stores feedback in the `ConversationDatabase`.

4. **File Upload and Audio Recording**:
   - File uploads (e.g., images) and audio recordings are supported as inputs, enriching the conversation flow.

5. **Streamlit User Interface**:
   - Streamlit components such as chat messages, buttons, and columns are used to build the UI.
   - A fixed container at the bottom of the interface provides options like submitting audio recordings or downloading conversation history.

**Tools Include**:
   - Database Connections: It connects to a Neo4j graph database, Pinecone vector database, and Microsoft SQL Server.
   - Natural Language Queries: Converts user queries into Cypher queries to fetch data from Neo4j or executes dense and sparse vector searches in Pinecone using OpenAI models.
   - Query Processing: Depending on the query type, different tools and methods are used, such as HybridQueryProcessor, SelfQueryDelfi, and intelisale.
   - OpenAI Integration: Uses GPT-4 models to handle natural language processing, query formulation, and even generate structured decisions about which tool to use for different tasks.
   - Hybrid Querying: Combines dense (semantic) and sparse (keyword) search techniques using Pinecone's BM25 encoder for hybrid vector searches.
   - Customer Reporting: Integrates with Microsoft SQL Server to generate customer reports, processes customer-related queries, and retrieves detailed information about customers from the database.
   - API Integrations: To retrieve additional information related to orders, books, or products.
   - ...

## Setup Instructions

1. Install dependencies:

2. Set up environment variables (you can add these to a `.env` file or export them directly in your environment):
   ```bash
   export OPENAI_API_KEY="your-openai-api-key"
   export PINECONE_HOST="your-pinecone-host"
   export APP_ID="DelfiBot"
   ```

3. Run the application via streamlit run krembot.py

This will launch the chatbot interface in your browser where you can interact with it via text, audio, and files.
