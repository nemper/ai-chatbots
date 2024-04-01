import streamlit as st
import threading
import queue
from openai import OpenAI
from typing_extensions import override
from openai import AssistantEventHandler
from openai.types.beta.threads import Message
from openai.types.beta.threads.runs import ToolCall, RunStep
import json
import os

# Set your OpenAI API key and Assistant ID here
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
ASSISTANT_ID = "asst_1YAl3U9XJTOnfYUJrStFO1nH"

client = OpenAI(api_key=OPENAI_API_KEY)

_ = """
class EventHandler(AssistantEventHandler):    
  @override
  def on_text_created(self, text) -> None:
    # print(f"assistant > ", end="", flush=True)
    st.write(text.value)
      
  @override
  def on_text_delta(self, delta, snapshot):
    print(delta.value, end="", flush=True)
    #  st.write(delta.value)
      
  def on_tool_call_created(self, tool_call):
    print(f"assistant > {tool_call.type}", flush=True)
    # st.write(f"assistant > {tool_call.type}")
  
  def on_tool_call_delta(self, delta, snapshot):
    if delta.type == 'code_interpreter':
      if delta.code_interpreter.input:
        print(delta.code_interpreter.input, end="", flush=True)
        # st.write(delta.code_interpreter.input)
      if delta.code_interpreter.outputs:
        print(f"output >", flush=True)
        # st.write(f"output >")
        for output in delta.code_interpreter.outputs:
          if output.type == "logs":
            print(f"{output.logs}", flush=True)
            # st.write(f"{output.logs}")
"""
st.title("💬 Chatbot")
st.caption("🚀 A streamlit chatbot powered by x")


prompt = st.text_input("Enter your message")
if prompt:
  st.markdown("----")
  res_box = st.empty()
  report = []
  stream = client.beta.threads.create_and_run(
    assistant_id=ASSISTANT_ID,
    thread={"messages": [{"role": "user", "content": prompt}]},
    stream=True)
  for event in stream:
    if event.data.object == "thread.message.delta":
      for content in event.data.delta.content:
        if content.type == "text":
          report.append(content.text.value)
          result = "".join(report).strip()
          res_box.markdown(f"*{result}*")
          