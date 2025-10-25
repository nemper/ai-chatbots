import base64
import html
import streamlit as st
import streamlit.components.v1 as components

import os
from streamlit.components.v1 import html as st_html
from typing import Literal


ui_features = {
"FIXED_CONTAINER_CSS" : """
:root {{
    --background-color: #343541; /* Default background color */
}}
div[data-testid="stVerticalBlockBorderWrapper"]:has(div.fixed-container-{id}):not(:has(div.not-fixed-container)) {{
    position: {mode};
    width: inherit;
    background-color: inherit;
    {position}: {margin};
    z-index: 999;
}}
div[data-testid="stVerticalBlockBorderWrapper"]:has(div.fixed-container-{id}):not(:has(div.not-fixed-container)) div[data-testid="stVerticalBlock"]:has(div.fixed-container-{id}):not(:has(div.not-fixed-container)) > div[data-testid="stVerticalBlockBorderWrapper"] {{
    background-color: transparent;
    width: 100%;
}}
div[data-testid="stVerticalBlockBorderWrapper"]:has(div.fixed-container-{id}):not(:has(div.not-fixed-container)) div[data-testid="stVerticalBlock"]:has(div.fixed-container-{id}):not(:has(div.not-fixed-container)) > div[data-testid="stVerticalBlockBorderWrapper"] div[data-testid="stVerticalBlockBorderWrapper"] {{
    background-color: var(--background-color);
}}
div[data-testid="stVerticalBlockBorderWrapper"]:has(div.fixed-container-{id}):not(:has(div.not-fixed-container)) div[data-testid="stVerticalBlock"]:has(div.fixed-container-{id}):not(:has(div.not-fixed-container)) > div[data-testid="element-container"] {{
    display: none;
}}
div[data-testid="stVerticalBlockBorderWrapper"]:has(div.not-fixed-container):not(:has(div[class^='fixed-container-'])) {{
    display: none;
}}
""".strip()
,
"FIXED_CONTAINER_JS" : """
const root = parent.document.querySelector('.stApp');
let lastBackgroundColor = null;
function updateContainerBackground(currentBackground) {
    parent.document.documentElement.style.setProperty('--background-color', currentBackground);
    ;
}
function checkForBackgroundColorChange() {
    const style = window.getComputedStyle(root);
    const currentBackgroundColor = style.backgroundColor;
    if (currentBackgroundColor !== lastBackgroundColor) {
        lastBackgroundColor = currentBackgroundColor; // Update the last known value
        updateContainerBackground(lastBackgroundColor);
    }
}
const observerCallback = (mutationsList, observer) => {
    for(let mutation of mutationsList) {
        if (mutation.type === 'attributes' && (mutation.attributeName === 'class' || mutation.attributeName === 'style')) {
            checkForBackgroundColorChange();
        }
    }
};
const main = () => {
    checkForBackgroundColorChange();
    const observer = new MutationObserver(observerCallback);
    observer.observe(root, { attributes: true, childList: false, subtree: false });
}
// main();
document.addEventListener("DOMContentLoaded", main);
""".strip()
,
"MARGINS" : {
    "top": "2.875rem",
    "bottom": "0",
},
"aifriend_css" : """
<div data-testid="column" class="st-emotion-cache-ocqkz7">
<style>
.st-emotion-cache-ocqkz7 {
    display: flex;
    flex-wrap: wrap;
    -webkit-box-flex: 1;
    flex-grow: 1;
    -webkit-box-align: stretch;
    align-items: stretch;
    gap: 0;
}
</style>
</div>
"""
}


counter = 0
def st_fixed_container(
    *,
    height: int | None = None,
    border: bool | None = None,
    mode: Literal["fixed", "sticky"] = "fixed",
    position: Literal["top", "bottom"] = "top",
    margin: str | None = None,
    transparent: bool = False,
):
    """
    Creates a fixed or sticky container in a Streamlit app.

    This function sets up a container in a Streamlit app that remains fixed or sticky at the top or bottom
    of the viewport. It includes options for setting the height, border, margin, and transparency of the container.
    
    Parameters:
    - height: The height of the container (default is None).
    - border: Whether to include a border around the container (default is None).
    - mode: The mode of the container, either "fixed" or "sticky" (default is "fixed").
    - position: The position of the container, either "top" or "bottom" (default is "top").
    - margin: The margin around the container (default is None).
    - transparent: Whether the container should be transparent (default is False).

    Returns:
    - A Streamlit container object with the specified fixed or sticky properties.
    """
    if margin is None:
        margin = ui_features["MARGINS"][position]
    global counter

    fixed_container = st.container()
    non_fixed_container = st.container()
    css = ui_features["FIXED_CONTAINER_CSS"].format(
        mode=mode,
        position=position,
        margin=margin,
        id=counter,
    )
    with fixed_container:
        st_html(f"<script>{ui_features['FIXED_CONTAINER_JS']}</script>", scrolling=False, height=0)
        st.markdown(f"<style>{css}</style>", unsafe_allow_html=True)
        st.markdown(
            f"<div class='fixed-container-{counter}'></div>",
            unsafe_allow_html=True,
        )
    with non_fixed_container:
        st.markdown(
            f"<div class='not-fixed-container'></div>",
            unsafe_allow_html=True,
        )
    counter += 1

    parent_container = fixed_container if transparent else fixed_container.container()
    return parent_container.container(height=height, border=border)


def chat_placeholder_color(color: str):
    '''
    Sets placeholder color in the st.chat_input()
    '''
    st.markdown(
        f"""
        <style>
        div[data-testid="stChatInput"] textarea::placeholder {{
            color: {color}; /* Change this to your desired color */
        }}
        </style>
        """,
        unsafe_allow_html=True
    )


def copy_to_clipboard(message):
    sanitized_message = html.escape(message)  # Escape the message to handle special HTML characters
    # Create an HTML button with embedded JavaScript for clipboard functionality and custom CSS
    html_content = f"""
    <html>
    <head>
        <style>
            #copyButton {{
                background-color: #454654;  /* Dark gray background */
                color: #f1f1f1;            /* Our white text color */
                border: none;           /* No border */
                border-radius: 8px;     /* Rounded corners */
                cursor: pointer;        /* Pointer cursor on hover */
                outline: none;          /* No focus outline */
                font-size: 20px;        /* Size */
            }}
            #textArea {{
                opacity: 0; 
                position: absolute; 
                pointer-events: none;
            }}
        </style>
    </head>
    <body>
    <textarea id="textArea">{sanitized_message}</textarea>
    <textarea id="textArea" style="opacity: 0; position: absolute; pointer-events: none;">{sanitized_message}</textarea>
    <button id="copyButton" onclick='copyTextToClipboard()'>📄</button>
    <script>
    function copyTextToClipboard() {{
        var textArea = document.getElementById("textArea");
        var copyButton = document.getElementById("copyButton");
        textArea.style.opacity = 1;
        textArea.select();
        try {{
            var successful = document.execCommand('copy');
            var msg = successful ? '✔️' : '❌';
            copyButton.innerText = msg;
        }} catch (err) {{
            copyButton.innerText = 'Failed!';
        }}
        textArea.style.opacity = 0;
        setTimeout(function() {{ copyButton.innerText = "📄"; }}, 3000);  // Change back after 3 seconds
    }}
    </script>
    </body>
    </html>
    """
    components.html(html_content, height=50)

chat_placeholder_color("#f1f1f1")

client_folder = os.getenv("CLIENT_FOLDER")
# avatar_bg = os.path.join("Clients", client_folder, "bg.png")
avatar_ai = os.path.join("Clients", client_folder, "avatar.png")
avatar_user = os.path.join("Clients", client_folder, "user.webp")
avatar_sys = os.path.join("Clients", client_folder, "logo.png")

# global phglob
# phglob=st.empty()

@st.cache_data
def get_img_as_base64(file):
    with open(file, "rb") as f:
        data = f.read()
    return base64.b64encode(data).decode()

# Apply background image
def apply_background_image(img_path):
    img = get_img_as_base64(img_path)
    page_bg_img = f"""
    <style>
    [data-testid="stAppViewContainer"] > .main {{
    background-image: url("data:image/png;base64,{img}");
    background-size: auto;
    background-position: center;
    background-repeat: no-repeat;
    background-attachment: fixed;
    }}
    </style>
    """
    st.markdown(page_bg_img, unsafe_allow_html=True)


def custom_streamlit_style():   
    custom_streamlit_style = """
        <style>
        div[data-testid="stHorizontalBlock"] {
            display: flex;
            flex-direction: row;
            width: 100%x;
            flex-wrap: nowrap;
            align-items: center;
            justify-content: flex-start;
        }
        .horizontal-item {
            margin-right: 5px; /* Adjust spacing as needed */
        }
        /* Mobile styles */
        @media (max-width: 640px) {
            div[data-testid="stHorizontalBlock"] {
                width: 160px; /* Fixed width for mobile */
            }
        }
        </style>
    """
    st.markdown(custom_streamlit_style, unsafe_allow_html=True)
