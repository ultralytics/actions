# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

"""
Ultralytics Actions CLI.

This module provides a unified command-line interface for all Ultralytics Actions tools.
"""

import argparse
import sys

try:
    import argcomplete
    ARGCOMPLETE_AVAILABLE = True
except ImportError:
    ARGCOMPLETE_AVAILABLE = False


def main():
    """Main CLI entry point for ultralytics-actions."""
    parser = argparse.ArgumentParser(
        prog="ultralytics-actions",
        description="Ultralytics Actions - GitHub automation and PR management tools",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    
    parser.add_argument(
        "--version",
        action="version",
        version=f"%(prog)s {get_version()}",
    )
    
    subparsers = parser.add_subparsers(dest="command", help="Available commands")
    
    # First interaction
    subparsers.add_parser(
        "first-interaction",
        help="Handle first-time contributor interactions",
    )
    
    # Review PR
    subparsers.add_parser(
        "review-pr",
        help="Review pull requests",
    )
    
    # Summarize PR
    subparsers.add_parser(
        "summarize-pr",
        help="Generate pull request summaries",
    )
    
    # Summarize release
    subparsers.add_parser(
        "summarize-release",
        help="Generate release summaries",
    )
    
    # Update markdown code blocks
    update_markdown_parser = subparsers.add_parser(
        "update-markdown-code-blocks",
        help="Update markdown code blocks",
    )
    update_markdown_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to directory or file to process (default: current directory)",
    )
    
    # Update headers
    headers_parser = subparsers.add_parser(
        "headers",
        help="Update file headers",
    )
    headers_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to directory or file to update (default: current directory)",
    )
    
    # Format Python docstrings
    format_docstrings_parser = subparsers.add_parser(
        "format-python-docstrings",
        help="Format Python docstrings",
    )
    format_docstrings_parser.add_argument(
        "path",
        nargs="?",
        default=".",
        help="Path to directory or file to format (default: current directory)",
    )
    
    # Info
    subparsers.add_parser(
        "info",
        help="Display package information",
    )
    
    # Completion
    completion_parser = subparsers.add_parser(
        "completion",
        help="Generate shell completion script",
    )
    completion_parser.add_argument(
        "shell",
        choices=["bash", "zsh", "fish"],
        help="Shell type for completion script",
    )
    
    # Enable argcomplete if available
    if ARGCOMPLETE_AVAILABLE:
        argcomplete.autocomplete(parser)
    
    args, unknown = parser.parse_known_args()
    
    if not args.command:
        parser.print_help()
        sys.exit(1)
    
    # Import and execute the appropriate command
    if args.command == "first-interaction":
        from actions.first_interaction import main as cmd_main
    elif args.command == "review-pr":
        from actions.review_pr import main as cmd_main
    elif args.command == "summarize-pr":
        from actions.summarize_pr import main as cmd_main
    elif args.command == "summarize-release":
        from actions.summarize_release import main as cmd_main
    elif args.command == "update-markdown-code-blocks":
        from actions.update_markdown_code_blocks import main as cmd_main
        # Pass the path argument using sys.argv manipulation
        sys.argv = [sys.argv[0], args.path]
    elif args.command == "headers":
        from actions.update_file_headers import main as cmd_main
        # Pass the path argument using sys.argv manipulation
        sys.argv = [sys.argv[0], args.path]
    elif args.command == "format-python-docstrings":
        from actions.format_python_docstrings import main as cmd_main
        # Pass the path argument using sys.argv manipulation
        import sys
        sys.argv = [sys.argv[0], args.path]
    elif args.command == "info":
        from actions.utils import ultralytics_actions_info as cmd_main
    elif args.command == "completion":
        generate_completion(args.shell)
        return
    else:
        parser.print_help()
        sys.exit(1)
    
    cmd_main()


def get_version():
    """Get package version."""
    from actions import __version__
    return __version__


def generate_completion(shell):
    """Generate shell completion script."""
    if not ARGCOMPLETE_AVAILABLE:
        print("Error: argcomplete is not installed. Install with: pip install argcomplete")
        sys.exit(1)
    
    if shell == "bash":
        print("""
# Bash completion for ultralytics-actions
# Add this to ~/.bashrc or ~/.bash_profile:
#   eval "$(register-python-argcomplete ultralytics-actions)"
# Or run: activate-global-python-argcomplete (one-time setup)

eval "$(register-python-argcomplete ultralytics-actions)"
""")
    elif shell == "zsh":
        print("""
# Zsh completion for ultralytics-actions
# Add this to ~/.zshrc:
#   autoload -U bashcompinit
#   bashcompinit
#   eval "$(register-python-argcomplete ultralytics-actions)"

autoload -U bashcompinit
bashcompinit
eval "$(register-python-argcomplete ultralytics-actions)"
""")
    elif shell == "fish":
        print("""
# Fish completion for ultralytics-actions
# Add this to ~/.config/fish/config.fish:
#   register-python-argcomplete --shell fish ultralytics-actions | source

register-python-argcomplete --shell fish ultralytics-actions | source
""")


if __name__ == "__main__":
    main()
