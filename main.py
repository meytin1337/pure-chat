import argparse
from dotenv import load_dotenv
from rich.console import Console
from rich.markdown import Markdown
from rich.live import Live
from rich.panel import Panel

# Terminal-style input imports
from prompt_toolkit.formatted_text import HTML

import util
import db_manager

load_dotenv()
console = Console()


def main():
    parser = argparse.ArgumentParser(description="Gemini CLI with SQLite & Search")
    parser.add_argument("--name", type=str, help="Start/Continue a specific session")
    args = parser.parse_args()

    db_manager.init_db()

    # Initial Session Setup
    session_id, session_name = db_manager.get_or_create_session(args.name)
    ai, input_session = util.setup_chat_session(session_id)

    console.print(
        Panel(
            f"Active Session: [bold green]{session_name}[/bold green]\n"
            "[dim]• Use UP/DOWN arrows for question history\n"
            "• Type /conversations to switch sessions\n"
            "• Type /model to switch active model\n"
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
                new_id, new_name = util.select_session_interactive()
                session_id, session_name = new_id, new_name
                ai, input_session = util.setup_chat_session(session_id)
                console.print(
                    Panel(
                        f"Switched to: [bold green]{session_name}[/bold green]",
                        expand=False,
                    )
                )
                util.print_session_tail(session_id)
                continue

            if user_input.lower() == "/model":
                util.select_model(session_id)
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
