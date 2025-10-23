# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

import sys
from unittest.mock import MagicMock, patch

import pytest

from actions.utils import Action, check_pypi_version, ultralytics_actions_info


@pytest.mark.skipif(sys.version_info < (3, 11), reason="tomllib requires Python 3.11+")
def test_check_pypi_version():
    """Test check_pypi_version function."""
    with patch("tomllib.load", return_value={"project": {"name": "test-package", "version": "1.0.0"}}):
        with patch("requests.get") as mock_get:
            mock_response = MagicMock()
            mock_response.status_code = 200
            mock_response.elapsed.total_seconds.return_value = 0.5
            mock_response.json.return_value = {"info": {"version": "0.9.0"}}
            mock_get.return_value = mock_response

            local_version, online_version, publish = check_pypi_version()

            assert local_version == "1.0.0"
            assert online_version == "0.9.0"
            assert publish is True


def test_action_init():
    """Test Action class initialization with default values."""
    with patch.dict("os.environ", {"GITHUB_TOKEN": "test-token", "GITHUB_EVENT_NAME": "push"}), patch(
        "actions.utils.github_utils.Action._load_event_data",
        return_value={"repository": {"full_name": "test/repo"}},
    ):
        action = Action()
        assert action.token == "test-token"
        assert action.event_name == "push"
        assert action.repository == "test/repo"


def test_action_request_methods():
    """Test Action HTTP request methods."""
    with patch("requests.get") as mock_get:
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.elapsed.total_seconds.return_value = 0.3
        mock_get.return_value = mock_response

        action = Action(token="test-token")
        response = action.get("https://api.github.com/test")

        assert response == mock_response
        mock_get.assert_called_once()


def test_load_event_data():
    """Test loading event data from file."""
    with patch("pathlib.Path.exists", return_value=True):
        with patch("pathlib.Path.read_text", return_value='{"test": "data"}'):
            action = Action()
            data = action._load_event_data("fake_path")
            assert data == {"test": "data"}


def test_ultralytics_actions_info():
    """Test ultralytics_actions_info function."""
    with patch("actions.utils.github_utils.Action.print_info") as mock_print_info:
        ultralytics_actions_info()
        mock_print_info.assert_called_once()
