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
            "• Type /search <query> to search conversations\n"
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

            if user_input.lower().startswith("/search "):
                query = user_input[8:]  # Remove "/search "
                if not query.strip():
                    console.print("[yellow]Usage: /search <query> (use quotes for exact phrases)[/yellow]")
                    continue
                
                results = db_manager.search_messages(query, limit=10)
                
                if not results:
                    console.print("[yellow]No matches found.[/yellow]")
                    continue
                
                console.print(f"\n[bold cyan]Found {len(results)} results for:[/bold cyan] {query}\n")
                
                for idx, result in enumerate(results, 1):
                    role_label = "You" if result["role"] == "user" else "Gemini"
                    console.print(f"[bold white][{idx}][/bold white] [bold green]{result['session_name']}[/bold green]")
                    console.print(f"[dim]{result['timestamp']} | {role_label}[/dim]")
                    # Escape Rich markup in snippet, then restore our highlight tags
                    safe_snippet = result["snippet"].replace("[bold green]", "\x01").replace("[/bold green]", "\x02")
                    safe_snippet = safe_snippet.replace("[", "\\[")
                    safe_snippet = safe_snippet.replace("\x01", "[bold green]").replace("\x02", "[/bold green]")
                    console.print(safe_snippet)
                    console.print()
                
                # Arrow-key selection (consistent with /conversations)
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
                    session_id, session_name = db_manager.get_or_create_session(selected_name)
                    ai, input_session = util.setup_chat_session(session_id)
                    console.print(
                        Panel(
                            f"Switched to: [bold green]{session_name}[/bold green]",
                            expand=False,
                        )
                    )
                    util.print_session_tail(session_id)
                
                continue

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
