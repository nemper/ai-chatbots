# in myfunc.pyui_javascript.py
from typing import Literal
import streamlit as st
from streamlit.components.v1 import html

# in myfunc.pyui_javascript.py
ui_features = {
"FIXED_CONTAINER_CSS" : """
:root {{
    --background-color: #ffffff; /* Default background color */
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
}
,
"custom_streamlit_style" : """
    <style>
    MainMenu {visibility: hidden;}
    footer {visibility: hidden;}
    #root > div:nth-child(1) > div > div > div > div > \
    section > div {padding-top: 1rem;}

    [data-testid="stSidebar"] { 
        background: linear-gradient(to right, #E3C4FF, #D9ADFF); 
        box-shadow: 15px 15px 10px rgba(0,0,0,0.1);
        border-radius: 10px;

    }   
    [data-testid="stSidebarNav"] {
        background-color: #ffffff;
        font-weight: bold;
        margin-top: -6rem;
        border-style: solid;
        border-width: 20px;
        border-image: linear-gradient(to right, #f5f5f5, #f0f0f0) 1;
    }

    .stSlider {
        background-color: #faf5ff;
        border: 3px solid #c893fc; 
        border-radius: 10px;
        padding: 25px;
        box-shadow: 5px 5px 10px rgba(0,0,0,0.4);
    }
    .stSlider:hover {
        background-color: #ede2ff;
        border: 3px solid #9e70f5; 
    }

    [data-testid="stWidgetLabel"] p {
        font-weight: bold;
        font-size: 16px;
    }

    [data-testid="stDownloadButton"] button {
        border: 3px solid #B3A2E9; 
        background-color: #ECE6FC;
        box-shadow: 3px 3px 10px rgba(0,0,0,0.4);
    }
    [data-testid="stDownloadButton"] button:hover {
        border: 3px solid #8F78CD;
        background-color: #CFC8F2;
    }

    [data-testid="stFormSubmitButton"] button {
        border: 3px solid #B3A2E9; 
        background-color: #ECE6FC;
        box-shadow: 3px 3px 10px rgba(0,0,0,0.4);
    }
    [data-testid="stFormSubmitButton"] button:hover {
        border: 3px solid #8F78CD;
        background-color: #CFC8F2;
    }

    [data-testid="stFileUploader"] {
        border: 3px solid #72B6FC; 
        background-color: #eff6ff;
        padding: 10px;
        border-radius: 10px;
    }
    [data-testid="stFileUploader"]:hover {
        border: 3px solid #4D8FD6;
        background-color: #DCE4F7;
    }

    [data-testid="stCaptionContainer"] {
        textColor: white;
    }
    
    [data-testid="baseButton-header"] {
        background-color: #DCE4F7;
    }
    
    [data-testid="stFileUploader"] {
        border: 3px solid #72B6FC; 
        background-color: #eff6ff;
        padding: 10px;
        border-radius: 10px;
        box-shadow: 5px 5px 4px rgba(0,0,0,0.2);
    }
    [data-testid="stFileUploader"]:hover {
        border: 3px solid #4D8FD6;
        background-color: #DCE4F7;
    }

    [data-testid="stFileUploader"] button {
        border: 3px solid #B3A2E9; 
        background-color: #ECE6FC;
        box-shadow: 3px 3px 10px rgba(0,0,0,0.4);
    }
    [data-testid="stFileUploader"] button:hover {
        border: 3px solid #8F78CD;
        background-color: #CFC8F2;
    }

    [data-testid="stForm"] {
        border: 3px solid #4ac9a2; 
        background-color: #ecfdf5; 
        box-shadow: 5px 5px 4px rgba(0,0,0,0.2);
    }
    [data-testid="stForm"]:hover {
        border: 3px solid #51B391;
        background-color: #c5f2e1;
    }

    [data-baseweb="select"] {
        font-weight: bold;
        font-size: 16px;
        box-shadow: 5px 5px 4px rgba(0,0,0,0.5);
    }
    [data-testid="stWidgetLabel"] [data-baseweb="textarea"] {
        border: 3px solid #51B391;
        box-shadow: 5px 5px 4px rgba(0,0,0,0.2);
    }
    [data-testid="stExpander"] {
        border: 2px solid #7EB6F6; 
        border-radius: 10px;
        box-shadow: 5px 5px 10px rgba(0,0,0,0.4);
    }
    
    [data-baseweb="select"] [data-baseweb="icon"] {
        border: 3px solid #eff6ff;
        background-color: #eff6ff; 
        box-shadow: 2px 2px 4px rgba(0,0,0,0.4);
    }

    [data-baseweb="select"] [data-baseweb="icon"]:hover {
        border: 3px solid #d8e3f3;
        background-color: #d8e3f3; 
        box-shadow: 2px 2px 4px rgba(0,0,0,0.4);
    }

    </style>
    """
,
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

# in myfunc.pyui_javascript.py
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
        html(f"<script>{ui_features['FIXED_CONTAINER_JS']}</script>", scrolling=False, height=0)
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


# in myfunc.pyui_javascript.py
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
