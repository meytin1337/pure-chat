import argparse
from rich.markdown import Markdown
from rich.live import Live
from rich.panel import Panel

from prompt_toolkit.formatted_text import HTML

from pure_chat import util
from pure_chat import db_manager
from pure_chat import fs
from pure_chat.console import console
from pure_chat.ai_manager import GeminiAssistant


def main():
    parser = argparse.ArgumentParser(description="Gemini CLI with SQLite & Search")
    parser.add_argument("--name", type=str, help="Start/Continue a specific session")
    args = parser.parse_args()

    db_manager.init_db()
    config = fs.load_config()
    api_key = config.get("gemini_api_key")
    if not api_key:
        api_key = util.ask_for_api_key()
        fs.write_config("gemini_api_key", api_key)
        config["gemini_api_key"] = api_key
    model_id = config.get("default_model")
    if not model_id:
        model_id = util.select_model(api_key)

    ai = GeminiAssistant(config, model_id)

    # Initial Session Setup
    session_id, session_name = db_manager.get_or_create_session(args.name)
    input_history = util.load_input_history()

    util.print_help(session_name)

    while True:
        try:
            # Styled prompt using prompt_toolkit
            user_input = input_history.prompt(
                HTML(
                    f"<b><lightgreen>{session_name}</lightgreen><ansicyan> - You > </ansicyan></b>"
                )
            )

            if not user_input.strip():
                continue

            # --- COMMANDS ---
            if user_input.lower() == "/exit":
                console.print("[yellow]Goodbye![/yellow]")
                break

            if user_input.lower() == "/help":
                util.print_help(session_name)
                continue

            if user_input.lower() == "/new":
                session_id, session_name = db_manager.get_or_create_session()
                input_history = util.load_input_history()
                continue

            if user_input.lower().startswith("/search "):
                query = user_input[8:]  # Remove "/search "
                if not query.strip():
                    console.print(
                        "[yellow]Usage: /search <query> (use quotes for exact phrases)[/yellow]"
                    )
                    continue

                results = db_manager.search_messages(query, limit=10)

                if not results:
                    console.print("[yellow]No matches found.[/yellow]")
                    continue

                console.print(
                    f"\n[bold cyan]Found {len(results)} results for:[/bold cyan] {query}\n"
                )

                for idx, result in enumerate(results, 1):
                    role_label = "You" if result["role"] == "user" else "Gemini"
                    console.print(
                        f"[bold white][{idx}][/bold white] [bold green]{result['session_name']}[/bold green]"
                    )
                    console.print(f"[dim]{result['timestamp']} | {role_label}[/dim]")
                    safe_snippet = (
                        result["snippet"]
                        .replace("[bold green]", "\x01")
                        .replace("[/bold green]", "\x02")
                    )
                    safe_snippet = safe_snippet.replace("[", "\\[")
                    safe_snippet = safe_snippet.replace("\x01", "[bold green]").replace(
                        "\x02", "[/bold green]"
                    )
                    console.print(safe_snippet)
                    console.print()

                search_choices = [
                    f"{r['session_name']} ({r['timestamp']} | {'You' if r['role'] == 'user' else 'Gemini'})"
                    for r in results
                ]
                search_choices.append("Cancel")

                selected = util.pick_from_list("Jump to session:", search_choices)

                if selected is None or selected == "Cancel":
                    console.print("[dim]Search cancelled.[/dim]\n")
                else:
                    selected_name = selected.rsplit(" (", 1)[0]
                    session_id, session_name = db_manager.get_or_create_session(
                        selected_name
                    )
                    chat_history = db_manager.get_chat_history(
                        session_id, window_size=12
                    )
                    ai = GeminiAssistant(config, model_id, history=chat_history)
                    console.print(
                        Panel(
                            f"Switched to: [bold green]{session_name}[/bold green]",
                            expand=False,
                        )
                    )
                    util.print_session_tail(session_id)

                continue

            if user_input.lower() == "/conversations":
                result = util.select_session_interactive(current_session_id=session_id)
                if result is not None:
                    session_id, session_name = result
                    chat_history = db_manager.get_chat_history(session_id, window_size=12)
                    ai = GeminiAssistant(config, model_id, history=chat_history)
                    console.print(
                        Panel(
                            f"Switched to: [bold green]{session_name}[/bold green]",
                            expand=False,
                        )
                    )
                    util.print_session_tail(session_id)
                continue

            if user_input.lower() == "/model":
                util.select_model(api_key)
                continue

            if user_input.startswith("/"):
                console.print(f"Unknown command {user_input.split(' ')[0]}")
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
