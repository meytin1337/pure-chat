import argparse
import sys
import questionary
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live
from rich.panel import Panel

# Terminal-style input imports
from prompt_toolkit import PromptSession
from prompt_toolkit.history import InMemoryHistory
from prompt_toolkit.formatted_text import HTML

import db_manager
from ai_manager import GeminiAssistant

load_dotenv()
console = Console()


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


def main():
    parser = argparse.ArgumentParser(description="Gemini CLI with SQLite & Search")
    parser.add_argument("--name", type=str, help="Start/Continue a specific session")
    args = parser.parse_args()

    db_manager.init_db()

    # Initial Session Setup
    session_id, session_name = db_manager.get_or_create_session(args.name)
    ai, input_session = setup_chat_session(session_id)

    console.print(
        Panel(
            f"Active Session: [bold green]{session_name}[/bold green]\n"
            "[dim]• Use UP/DOWN arrows for question history\n"
            "• Type /conversations to switch sessions\n"
            "• Type /exit to quit[/dim]",
            title="Gemini CLI",
            expand=False,
        )
    )

    while True:
        try:
            # Styled prompt using prompt_toolkit
            user_input = input_session.prompt(
                HTML("<ansicyan><b>You > </b></ansicyan>")
            )

            if not user_input.strip():
                continue

            # --- COMMANDS ---
            if user_input.lower() in ["/exit"]:
                console.print("[yellow]Goodbye![/yellow]")
                break

            if user_input.lower() == "/conversations":
                # Call the function directly (no weird import needed)
                new_id, new_name = select_session_interactive()
                session_id, session_name = new_id, new_name
                ai, input_session = setup_chat_session(session_id)
                console.print(
                    Panel(
                        f"Switched to: [bold green]{session_name}[/bold green]",
                        expand=False,
                    )
                )
                print_session_tail(session_id)
                continue

            # --- PROCESS CHAT ---
            db_manager.save_message(session_id, "user", user_input)

            full_res = ""
            console.print("\n[bold magenta]Gemini:[/bold magenta]")

            # Streaming with Rich Live display
            with Live(Markdown(""), console=console, refresh_per_second=10) as live:
                try:
                    for chunk in ai.send_stream(user_input):
                        if chunk.text:
                            full_res += chunk.text
                            live.update(Markdown(full_res))
                except Exception as e:
                    console.print(f"[bold red]API Error:[/bold red] {e}")

            db_manager.save_message(session_id, "model", full_res)
            print()  # Spacer

        except KeyboardInterrupt:
            # Standard terminal behavior: Ctrl+C clears the current line
            continue
        except EOFError:
            # Ctrl+D exits
            break


if __name__ == "__main__":
    main()
