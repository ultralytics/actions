# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

from datetime import datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from actions import update_file_headers

AGPL = "Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license"
YEAR = datetime.now(timezone.utc).year


@pytest.mark.parametrize(
    ("name", "text", "expected"),
    [
        ("a.py", "import os\n", f"# {AGPL}\n\nimport os\n"),
        ("b.py", '"""Doc."""\n', f'# {AGPL}\n"""Doc."""\n'),
        (
            "c.py",
            "#!/usr/bin/env python\n# -*- coding: utf-8 -*-\nx = 1\n",
            f"#!/usr/bin/env python\n# -*- coding: utf-8 -*-\n# {AGPL}\n\nx = 1\n",
        ),
        ("d.py", "# Ultralytics 🚀 AGPL-3.0 License - old\n\nx = 1\n", f"# {AGPL}\n\nx = 1\n"),
        ("e.py", "# © 2014-2020 Ultralytics Inc. 🚀 old\nx = 1\n", f"# {AGPL}\n\nx = 1\n"),
        ("f.css", "body {}\n", f"/* {AGPL} */\n\nbody {{}}\n"),
        ("g.html", "<!DOCTYPE html>\n<html></html>\n", f"<!DOCTYPE html>\n<!-- {AGPL} -->\n\n<html></html>\n"),
        ("h.py", f"# {AGPL}\n\nimport os\n", None),
        ("i.py", "", None),
        ("missing.py", None, None),
    ],
)
def test_update_file(tmp_path, name, text, expected):
    """Test headers are inserted, replaced, or left alone for each supported file shape."""
    path = tmp_path / name
    if text is not None:
        path.write_text(text, encoding="utf-8")
    prefix, start, end = update_file_headers.COMMENT_MAP[path.suffix]
    assert update_file_headers.update_file(path, prefix, start, end, AGPL) is (expected is not None)
    if text is not None:
        assert path.read_text(encoding="utf-8") == (expected or text)


def test_main_selects_header_by_repository(tmp_path, monkeypatch, capsys):
    """Test main picks the confidential, AGPL, or custom header and skips ignored paths."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / "a.py").write_text("x = 1\n")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "b.js").write_text("x\n")
    event = MagicMock(repository="ultralytics/repo")
    with patch("actions.update_file_headers.Action", return_value=event):
        event.is_repo_private.return_value = True
        update_file_headers.main()
        assert f"# © 2014-{YEAR} Ultralytics Inc. 🚀 All rights reserved." in (tmp_path / "a.py").read_text()
        assert "Headers: 1, Updated: 1, Unchanged: 0" in capsys.readouterr().out

        event.is_repo_private.return_value = False
        update_file_headers.main()
        assert f"# {AGPL}\n\nx = 1\n" == (tmp_path / "a.py").read_text()

        event.repository = "other/repo"
        monkeypatch.setattr(update_file_headers, "HEADER", "true")
        update_file_headers.main()
        assert capsys.readouterr().out.count("Headers:") == 1

        monkeypatch.setattr(update_file_headers, "HEADER", "© 2014-2020 Custom")
        update_file_headers.main()
        assert f"# © 2014-{YEAR} Custom\n\nx = 1\n" == (tmp_path / "a.py").read_text()
        update_file_headers.main()
        assert "Headers: 1, Updated: 0, Unchanged: 1" in capsys.readouterr().out
    assert (tmp_path / "node_modules" / "b.js").read_text() == "x\n"
