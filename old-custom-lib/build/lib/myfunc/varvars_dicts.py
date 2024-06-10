# in myfunc.varvars_dicts.py
import os
import streamlit as st

from myfunc.prompts import PromptDatabase


# in myfunc.varvars_dicts.py
work_vars = {     
    "names" : {
        "openai_model": "gpt-4o",
        },

    }


# in myfunc.varvars_dicts.py
@st.cache_data
def work_prompts():
    default_prompt = "You are a helpful assistant that always writes in Serbian."

    myfunc_prompts = {
        # asistenti.py
        "text_from_image": default_prompt ,
        "text_from_audio": default_prompt ,

        # embeddings.py
        "contextual_compression": default_prompt ,
        "self_query": default_prompt ,
        
        # various_tools.py
        "hyde_rag": default_prompt ,
        "choose_rag": default_prompt ,
        }

    prompt_names = list(myfunc_prompts.keys())

    with PromptDatabase() as db:
        env_vars = [os.getenv(name.upper()) for name in prompt_names]
        prompt_map = db.get_prompts_by_names(prompt_names, env_vars)

        for name in prompt_names:
            myfunc_prompts[name] = prompt_map.get(name, default_prompt)
    
    return myfunc_prompts