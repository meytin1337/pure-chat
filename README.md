# PureChat

A high-performance Terminal User Interface (TUI) designed to replicate the experience of gemini.google.com directly in your terminal. This tool provides persistent conversation memory, real-time streaming, and interactive session management.

## 💡 Motivation

Most modern AI CLI tools have become heavily "agentic." While powerful for automation, they often force massive context windows, auto-execute commands, and prioritize task completion over simple conversation. This results in high token consumption, slower response times, and a lack of control over what data is being sent.

Gemini CLI Vault was built to fill the gap for a "regular" chat app in the terminal. It provides a familiar web-like experience for discussing complicated topics in a controlled environment where you don't want the tool to send excessive context or execute commands autonomously.

## ✨ Key Features

- Persistent Memory: Conversations are stored in a local SQLite database (gemini_vault.db), allowing you to resume any chat session at any time.
- Live Streaming & Markdown: Responses stream in real-time with full Markdown rendering, including syntax-highlighted code blocks, tables, and lists.
- Intelligent Context Window: Automatically manages token usage using a sliding window of the last 12 messages to maintain context without exceeding limits.
- Interactive Session Switcher: Use the /conversations command to browse, search, and switch between previous chat sessions using an arrow-key menu.
- Global Command History: Navigate your previous prompts across all sessions using the UP and DOWN arrows (powered by prompt_toolkit).
- Google Search Integration: The assistant is equipped with the Google Search tool to provide up-to-date information on current events.
- Dynamic Personalities: Load custom system instructions from a GEMINI.md file to change the AI's behavior and tone.

## 🛠️ Installation (using uv)

1. Clone the repository:

```
git clone https://github.com/yourusername/gemini-cli-vault.git
cd gemini-cli-vault
```

2. Create a virtual environment and install dependencies:

```
uv venv
source .venv/bin/activate  # On Windows use: .venv\Scripts\activate
uv pip install google-genai python-dotenv rich prompt_toolkit questionary
```

3. Configure Environment Variables:

```
Create a .env file in the project root:
GEMINI_API_KEY=your_google_api_key_here
GEMINI_MODEL=gemini-2.0-flash-exp
```

4. (Optional) Define System Instructions:
   Create a GEMINI.md file to set the AI's System Prompt:
   You are an expert software architect. Provide concise, high-level advice and always include code snippets in Python or Rust.

## 🚀 Usage

Start a new or default session:

```
uv run main.py
```

Start or resume a specific session by name:

```
python main.py --name Project-Alpha
```

### ⌨️ In-Chat Commands

/conversations : Opens the interactive session manager to switch or create chats.
exit or quit : Safely saves and exits the application.
UP / DOWN : Cycle through your entire history of user prompts.
Ctrl+C : Interrupt the current input line.

## 🏗️ Project Architecture

- main.py: The entry point and TUI controller. Handles the input loop and rich live display.
- db_manager.py: The data layer. Manages SQLite tables, message logging, and session retrieval.
- ai_manager.py: The AI integration layer. Configures the google-genai client, tools, and system instructions.
- gemini_vault.db: The local database generated on first run.

## 📝 Technical Details

- Random Session Naming: If no name is provided, the tool generates a friendly random ID (e.g., sparkling-nebula-742).
- Sliding Window: To prevent API context overflow, the tool only fetches the most recent parts of the conversation for the AI's memory.
- Rich Live Display: Uses Live blocks to update the terminal window dynamically as the AI streams chunks of text.

## 🤖 AI Disclosure

This project was primarily developed with the assistance of AI. While the core logic, architecture, and feature set were human-directed, the majority of the code implementation and boilerplate was generated and refined using Large Language Models.
