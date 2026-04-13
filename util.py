import questionary
import os
import db_manager
from main import console
from rich.markdown import Markdown
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from ai_manager import GeminiAssistant
from google import genai


def select_session_interactive():
    """Fetches sessions and lets user pick one with arrow keys."""
    sessions = db_manager.list_all_sessions()

    # We add an option to create a new one
    choices = [f"{s[0]} ({s[1]})" for s in sessions]
    choices.append("Create New Session")

    selected = questionary.select(
        "Choose a conversation:",
        choices=choices,
        style=questionary.Style(
            [
                ("pointer", "fg:#00ff00 bold"),
                ("highlighted", "fg:#00ff00 bold"),
                ("selected", "fg:#00ff00"),
            ]
        ),
    ).ask()

    if selected == "Create New Session" or selected is None:
        return db_manager.get_or_create_session()

    # Extract the name back out (before the date in parentheses)
    session_name = selected.rsplit(" (", 1)[0]
    return db_manager.get_or_create_session(session_name)


def print_session_tail(session_id):
    """Prints the last 50 messages to the console with Rich formatting."""
    tail = db_manager.get_last_n_messages(session_id)
    if not tail:
        return

    for role, content in tail:
        color = "blue" if role == "user" else "magenta"
        label = "You" if role == "user" else "Gemini"
        console.print(f"[bold {color}]{label}:[/bold {color}]")
        console.print(Markdown(content))
        console.print("")  # Spacer
    console.print("[dim]--- End of history ---\n[/dim]")


def setup_chat_session(session_id, model_id=None):
    """Initializes history and the AI assistant."""
    # 1. Load context history for Gemini (Sliding Window)
    history = db_manager.get_chat_history(session_id, window_size=12)
    ai = GeminiAssistant(history=history, model_id=model_id)

    # 2. Setup UP-ARROW history for the terminal input
    past_user_prompts = db_manager.get_all_user_messages_global()
    terminal_history = InMemoryHistory()
    for prompt in past_user_prompts:
        terminal_history.append_string(prompt)

    input_session = PromptSession(history=terminal_history)

    return ai, input_session


def select_model(session_id):
    """
    Lists available Gemini models that support content generation
    and allows the user to select one via a CLI menu.
    """
    try:
        api_key = os.getenv("GEMINI_API_KEY")
        client = genai.Client(api_key=api_key)
        available_models = [
            m
            for m in client.models.list()
            if m.supported_actions and "generateContent" in m.supported_actions
        ]

        choices = [
            {"name": f"{m.display_name} ({m.name})", "value": m.name}
            for m in available_models
        ]

        selected_model_id = questionary.select(
            "Select the Gemini model you wish to use:",
            choices=choices,
            style=questionary.Style(
                [
                    ("pointer", "fg:#00ff00 bold"),
                    ("highlighted", "fg:#00ff00 bold"),
                    ("selected", "fg:#00ff00"),
                    ("separator", "fg:#666666"),
                ]
            ),
        ).ask()

        return setup_chat_session(session_id, selected_model_id)

    except Exception as e:
        print(f"Error fetching models: {e}")
        return None
