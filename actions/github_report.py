# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license
"""Generate GitHub organization reports."""

from actions import failed_scheduled_actions, scan_prs


def enabled(value):
    """Return whether a string environment-style value is enabled."""
    return str(value).lower() == "true"


def run():
    """Run enabled GitHub report sections."""
    import os

    if enabled(os.getenv("REPORT_PRS", "true")):
        scan_prs.run()
    if enabled(os.getenv("REPORT_FAILED_SCHEDULED_ACTIONS", "true")):
        failed_scheduled_actions.run()


if __name__ == "__main__":
    run()
