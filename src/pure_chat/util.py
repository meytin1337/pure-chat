import questionary
from pure_chat import db_manager
from rich.markdown import Markdown
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.completion import WordCompleter
from google import genai
from pure_chat.console import console
from rich.panel import Panel

QUESTIONARY_STYLE = questionary.Style(
    [
        ("pointer", "fg:#00ff00 bold"),
        ("highlighted", "fg:#00ff00 bold"),
        ("selected", "fg:#00ff00"),
    ]
)


def pick_from_list(prompt, choices):
    """Shared arrow-key selection using questionary."""
    return questionary.select(
        prompt,
        choices=choices,
        style=QUESTIONARY_STYLE,
    ).ask()


def select_session_interactive():
    """Fetches sessions and lets user pick one with arrow keys."""
    sessions = db_manager.list_all_sessions()
    # We add an option to create a new one
    choices = [f"{s[0]} ({s[1]})" for s in sessions]
    choices.append("Create New Session")

    selected = pick_from_list("Choose a conversation:", choices)

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
        console.print("")  # Spacer console.print("[dim]--- End of history ---\n[/dim]")


COMMANDS = ["/exit", "/help", "/new", "/rename", "/delete", "/search", "/conversations", "/model"]


def load_input_history():
    """Initializes history and the AI assistant."""
    past_user_prompts = db_manager.get_all_user_messages_global()
    terminal_history = InMemoryHistory()
    for prompt in past_user_prompts:
        terminal_history.append_string(prompt)

    completer = WordCompleter(COMMANDS, sentence=True)
    input_history = PromptSession(history=terminal_history, completer=completer)

    return input_history


def select_model(api_key):
    """
    Lists available Gemini models that support content generation
    and allows the user to select one via a CLI menu.
    """
    try:
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

        selected_model_id = pick_from_list(
            "Select the Gemini model you wish to use \n(you can set a default model by setting default_model in the config.toml):",
            choices,
        )

        return selected_model_id

    except Exception as e:
        print(f"Error fetching models: {e}")
        return None


def ask_for_api_key():
    api_key = questionary.password("Please enter your API key:").ask()

    if not api_key:
        raise Exception("API key is required")

    return api_key


def print_help(session_name):
    console.print(
        Panel(
            f"Active Session: [bold green]{session_name}[/bold green]\n"
            "[dim]• Use UP/DOWN arrows for question history\n"
            "• Type /new to start a new conversation\n"
            "• Type /rename <name> to rename the current session\n"
            "• Type /delete to delete a session\n"
            "• Type /search <query> to search conversations\n"
            "• Type /conversations to switch to an old conversation\n"
            "• Type /model to switch active model\n"
            "• Type /exit to quit\n"
            "• Type /help to print this message[/dim]",
            title="PureChat",
            expand=False,
        )
    )
