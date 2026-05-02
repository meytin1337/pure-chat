import questionary
from pure_chat import db_manager
from rich.markdown import Markdown
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.application import Application
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.keys import Keys
from prompt_toolkit.layout import Layout, Window, HSplit, FormattedTextControl
from prompt_toolkit.styles import Style as PtStyle
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


def select_session_interactive(current_session_id=None):
    """Interactive session browser with hotkeys D=delete, R=rename.

    Returns (session_id, session_name) on selection, or None if cancelled.
    If the current session was deleted and the user cancels, a new session is returned.
    """
    deleted_ids = set()
    selected_idx = 0

    while True:
        sessions = db_manager.list_all_sessions()
        total = len(sessions) + 1  # +1 for "Create New Session"
        selected_idx = min(selected_idx, total - 1)
        selected = [selected_idx]

        def get_header():
            return [
                ("class:qmark", "? "),
                ("class:question", "Choose a conversation "),
                ("class:instruction", "(↑↓ navigate, Enter=select, D=delete, R=rename, Esc=cancel)"),
            ]

        def get_body():
            tokens = []
            for i, (name, date) in enumerate(sessions):
                short_date = date[:16] if date else ""
                if i == selected[0]:
                    tokens.append(("class:selected", f"  » {name} ({short_date})\n"))
                else:
                    tokens.append(("", f"    {name} ({short_date})\n"))
            idx = len(sessions)
            if idx == selected[0]:
                tokens.append(("class:selected", "  » Create New Session\n"))
            else:
                tokens.append(("", "    Create New Session\n"))
            return tokens

        header_ctrl = FormattedTextControl(get_header)
        body_ctrl = FormattedTextControl(get_body)

        layout = Layout(HSplit([
            Window(content=header_ctrl, height=1),
            Window(content=body_ctrl),
        ]))

        bindings = KeyBindings()
        action = [None]

        @bindings.add(Keys.Up, eager=True)
        def move_up(event):
            if selected[0] > 0:
                selected[0] -= 1

        @bindings.add(Keys.Down, eager=True)
        def move_down(event):
            if selected[0] < total - 1:
                selected[0] += 1

        @bindings.add(Keys.ControlM, eager=True)
        def select_item(event):
            if selected[0] == len(sessions):
                action[0] = ("select_new",)
            else:
                action[0] = ("select", sessions[selected[0]][0])
            event.app.exit()

        @bindings.add(Keys.Escape, eager=True)
        def cancel(event):
            action[0] = ("cancel",)
            event.app.exit()

        @bindings.add("d", eager=True)
        @bindings.add("D", eager=True)
        def delete_item(event):
            if selected[0] < len(sessions):
                action[0] = ("delete", sessions[selected[0]][0])
                event.app.exit()

        @bindings.add("r", eager=True)
        @bindings.add("R", eager=True)
        def rename_item(event):
            if selected[0] < len(sessions):
                action[0] = ("rename", sessions[selected[0]][0])
                event.app.exit()

        @bindings.add(Keys.ControlC, eager=True)
        @bindings.add(Keys.ControlQ, eager=True)
        def abort(event):
            action[0] = ("cancel",)
            event.app.exit()

        @bindings.add(Keys.Any)
        def _(event):
            """Ignore unbound keys."""

        style = PtStyle.from_dict({
            "qmark": "#00ff00 bold",
            "question": "bold",
            "instruction": "#888888",
            "selected": "#00ff00 bold",
        })

        app = Application(
            layout=layout, key_bindings=bindings, style=style, full_screen=False
        )
        app.run()

        act = action[0]

        if act is None or act[0] == "cancel":
            if current_session_id is not None and current_session_id in deleted_ids:
                return db_manager.get_or_create_session()
            return None

        if act[0] == "select":
            return db_manager.get_or_create_session(act[1])

        if act[0] == "select_new":
            return db_manager.get_or_create_session()

        if act[0] == "delete":
            session_name = act[1]
            target_id, _ = db_manager.get_or_create_session(session_name)
            confirm = questionary.confirm(
                f"Permanently delete '{session_name}' and all its messages?",
                default=False,
            ).ask()
            if confirm:
                db_manager.delete_session(target_id)
                deleted_ids.add(target_id)
                console.print(f"[green]Deleted session:[/green] [bold]{session_name}[/bold]")
            selected_idx = selected[0]
            continue

        if act[0] == "rename":
            session_name = act[1]
            target_id, _ = db_manager.get_or_create_session(session_name)
            new_name = questionary.text(f"Rename '{session_name}' to:").ask()
            if new_name and new_name.strip():
                new_name = new_name.strip()
                result = db_manager.rename_session(target_id, new_name)
                if result:
                    console.print(f"[green]Renamed to:[/green] [bold]{new_name}[/bold]")
                else:
                    console.print(
                        f"[red]Could not rename. Name '{new_name}' may already be taken.[/red]"
                    )
            selected_idx = selected[0]
            continue

    return None


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


COMMANDS = ["/exit", "/help", "/new", "/search", "/conversations", "/model"]


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
            "• Type /search <query> to search conversations\n"
            "• Type /conversations to browse, rename (R), or delete (D) sessions\n"
            "• Type /model to switch active model\n"
            "• Type /exit to quit\n"
            "• Type /help to print this message[/dim]",
            title="PureChat",
            expand=False,
        )
    )
