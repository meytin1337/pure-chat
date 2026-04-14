from rich.console import Console

console = Console()


def print_error(error):
    console.print(error, style="bold red")
