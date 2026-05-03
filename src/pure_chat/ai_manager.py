import os
from google import genai
from google.genai import types
from pure_chat.fs import config_path


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
        instr_file = config_path("GEMINI.md")
        if instr_file.exists():
            with open(instr_file, "r") as f:
                instr = f.read()

        # 2. Configure Tools and Token Caps
        search_tool = types.Tool(google_search=types.GoogleSearch())
        self.config = types.GenerateContentConfig(
            tools=[search_tool],
            system_instruction=instr,
            temperature=0.2,
        )

        self.chat = self.client.chats.create(
            model=self.model_id, config=self.config, history=history or []
        )

    def send_stream(self, text):
        return self.chat.send_message_stream(text)

    def summarize_session(self, messages):
        response = self.client.models.generate_content(
            model="gemini-flash-latest",
            contents=f"Summarize the following conversation, maximum is 7 words: {messages}",
        )
        if response.text:
            return response.text.strip()
