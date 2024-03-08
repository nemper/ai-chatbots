# Vazno !!!! za deploy zajedno sa .stremlit podesavanjima promeniti:
Navigate to your repo on Github.
Go to the folder .github/workflows
Open the .yml file
I found that line 35: “run: zip release.zip ./* -r” should be changed to “run: zip release.zip ./* .streamlit -r”. 
This includes the .streamlit folder (including the config.toml file)

# Vazno !!!! requirements
Iz requirements.txt izbaciti torch i sve sto ima veze sa win

```markdown
# Streamlit Chat Application with OpenAI Integration

This repository contains a Streamlit application that leverages the OpenAI API to generate conversational responses. The application uses a custom hybrid query processor for refining prompts and a SQL database for managing conversation prompts. It's designed to create an interactive chat interface where users can receive responses in Serbian, showcasing an example of a multilingual AI assistant.

## Features

- **Streamlit Interface**: An easy-to-use web interface for user interactions.
- **OpenAI Integration**: Leverages OpenAI's powerful GPT models for generating conversational AI responses.
- **Hybrid Query Processor**: A custom-built query processor for enhancing the quality of prompts sent to the AI.
- **SQL Prompt Database**: Manages predefined conversation prompts and responses to ensure relevancy and coherence in interactions.

## Installation

To run this application, you will need Python installed on your system. The application dependencies are listed in `requirements.txt`. Follow these steps to get started:

1. Clone this repository:
```bash
git clone <repository-url>
```

2. Navigate to the project directory:
```bash
cd <repository-name>
```

3. Install the required Python packages:
```bash
pip install -r requirements.txt
```

4. Run the Streamlit application:
```bash
streamlit run app.py
```

## Usage

After starting the application, you will be directed to a web interface powered by Streamlit. Here, you can interact with the chat application. The application is preloaded with an initial system prompt in Serbian, but it can dynamically process user inputs to generate coherent and contextually relevant responses using the OpenAI API.

- **Interacting with the Chat**: Simply type your message in the chat input box and press enter. The application will process your input and display a response.
- **Understanding the Workflow**: The application uses a hybrid approach combining direct SQL queries for prompt retrieval and a custom query processor for enhancing input before sending it to OpenAI's GPT models.

## Customization

- **Environment Variables**: Some aspects of the application, such as the OpenAI API key and database connection details, should be set through environment variables or a `.env` file for security reasons.
- **Extending Functionality**: You can extend the application by modifying the `HybridQueryProcessor` or integrating additional models and databases.

## Contributing

Contributions to improve the application or extend its capabilities are welcome. Please follow the standard fork-and-pull request workflow.

## License

This project is licensed under the MIT License - see the LICENSE file for details.

## Acknowledgments

- OpenAI for providing the API used in this project.
- The Streamlit team for creating an amazing tool for building web applications.

For any questions or contributions, please feel free to open an issue or submit a pull request.


