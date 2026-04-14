import os
from google import genai
from google.genai import types
import tomllib
from pure_chat.fs import config_path
from pure_chat.util import select_model


class GeminiAssistant:
    def __init__(
        self,
        config,
        model_id,
        history=None,
    ):
        self.config = config
        api_key = self.config.get("gemini_api_key")
        self.model_id = model_id or self.config.get("default_model")

        self.client = genai.Client(api_key=api_key)

        instr = "You are a helpful assistant."
        if config_path("GEMINI.md"):
            with open("GEMINI.md", "r") as f:
                instr = f.read()

        # 2. Configure Tools and Token Caps
        search_tool = types.Tool(google_search=types.GoogleSearch())
        self.config = types.GenerateContentConfig(
            tools=[search_tool],
            system_instruction=instr,
            max_output_tokens=1000,  # Measure to reduce output token cost
            temperature=0.7,
        )

        self.chat = self.client.chats.create(
            model=self.model_id, config=self.config, history=history or []
        )

    def send_stream(self, text):
        return self.chat.send_message_stream(text)
