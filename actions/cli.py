# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

"""
Ultralytics Actions CLI.

This module provides a unified command-line interface for all Ultralytics Actions tools.
"""

import argparse
import sys


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
    subparsers.add_parser(
        "update-markdown-code-blocks",
        help="Update markdown code blocks",
    )
    
    # Update headers
    subparsers.add_parser(
        "headers",
        help="Update file headers",
    )
    
    # Format Python docstrings
    subparsers.add_parser(
        "format-python-docstrings",
        help="Format Python docstrings",
    )
    
    # Info
    subparsers.add_parser(
        "info",
        help="Display package information",
    )
    
    args = parser.parse_args()
    
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
    elif args.command == "headers":
        from actions.update_file_headers import main as cmd_main
    elif args.command == "format-python-docstrings":
        from actions.format_python_docstrings import main as cmd_main
    elif args.command == "info":
        from actions.utils import ultralytics_actions_info as cmd_main
    else:
        parser.print_help()
        sys.exit(1)
    
    cmd_main()


def get_version():
    """Get package version."""
    from actions import __version__
    return __version__


if __name__ == "__main__":
    main()
