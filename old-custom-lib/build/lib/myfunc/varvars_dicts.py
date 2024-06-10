# in myfunc.varvars_dicts.py
import os
import streamlit as st

from myfunc.prompts import PromptDatabase


# in myfunc.varvars_dicts.py
work_vars = {     
    "names" : {
        "openai_model": "gpt-4o",   # rucno izmeniti u myfunc.prompts (nisam ovo tamo pozivao da bih izbegao error usled cirkularne zavisnosti)
        },

    }


# in myfunc.varvars_dicts.py
@st.cache_data
def work_prompts():
    default_prompt = "You are a helpful assistant that always writes in Serbian."

    all_prompts = {
        # asistenti.py
        "text_from_image": default_prompt ,
        "text_from_audio": default_prompt ,

        # embeddings.py
        "contextual_compression": default_prompt ,
        "self_query": default_prompt ,
        
        # various_tools.py
        "hyde_rag": default_prompt ,
        "choose_rag": default_prompt ,

        # klotbot
        "sys_ragbot": default_prompt,
        "rag_answer_reformat": default_prompt,
        "rag_self_query": default_prompt,

        # upitnik
        "gap_ba_expert" : default_prompt,
        "gap_dt_consultant" : default_prompt,
        "gap_service_suggestion" : default_prompt,
        "gap_write_report" : default_prompt,

        # zapisnik
        "summary_end": default_prompt,
        "summary_begin": default_prompt,
        "intro_summary": default_prompt,
        "topic_list_summary": default_prompt,
        "date_participants_summary": default_prompt,
        "topic_summary": default_prompt,
        "conclusion_summary": default_prompt,

        # pravnik
        "new_law_email": default_prompt,
        }

    prompt_names = list(all_prompts.keys())

    with PromptDatabase() as db:
        env_vars = [os.getenv(name.upper()) for name in prompt_names]
        prompt_map = db.get_prompts_by_names(prompt_names, env_vars)

        for name in prompt_names:
            all_prompts[name] = prompt_map.get(name, default_prompt)
    
    return all_prompts