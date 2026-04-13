import questionary
import db_manager
from main import console
from rich.markdown import Markdown
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from ai_manager import GeminiAssistant


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


def setup_chat_session(session_id):
    """Initializes history and the AI assistant."""
    # 1. Load context history for Gemini (Sliding Window)
    history = db_manager.get_chat_history(session_id, window_size=12)
    ai = GeminiAssistant(history=history)

    # 2. Setup UP-ARROW history for the terminal input
    past_user_prompts = db_manager.get_all_user_messages_global()
    terminal_history = InMemoryHistory()
    for prompt in past_user_prompts:
        terminal_history.append_string(prompt)

    input_session = PromptSession(history=terminal_history)

    return ai, input_session
