import os
from google import genai
from google.genai import types


class GeminiAssistant:
    def __init__(self, history=None):
        api_key = os.getenv("GEMINI_API_KEY")
        model_id = os.getenv("GEMINI_MODEL", "gemini-3-flash-preview")

        self.client = genai.Client(api_key=api_key)
        self.model_id = model_id

        # 1. Load instructions from GEMINI.md
        instr = "You are a helpful assistant."
        if os.path.exists("GEMINI.md"):
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
