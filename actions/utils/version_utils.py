# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

# from actions.utils.version_utils import check_pypi_version
# check_pypi_version()

from __future__ import annotations

import re
from pathlib import Path

import requests


def should_publish(local_version, remote_version):
    """Determine if version should be published based on semver rules."""
    if remote_version:
        local_ver, remote_ver = [tuple(map(int, v.split("."))) for v in [local_version, remote_version]]
        major_diff, minor_diff, patch_diff = [local - remote for local, remote in zip(local_ver, remote_ver)]
        return (
            (major_diff == 0 and minor_diff == 0 and 0 < patch_diff <= 2)  # patch diff <=2
            or (major_diff == 0 and minor_diff == 1 and local_ver[2] == 0)  # new minor version
            or (major_diff == 1 and local_ver[1] == 0 and local_ver[2] == 0)  # new major version
        )  # should publish an update
    else:
        return True  # possible first release


def check_pypi_version(pyproject_toml="pyproject.toml"):
    """Compare local and PyPI package versions to determine if a new version should be published."""
    import tomllib  # scope for Python 3.11+

    with open(pyproject_toml, "rb") as f:
        pyproject = tomllib.load(f)

    package_name = pyproject["project"]["name"]
    local_version = pyproject["project"].get("version", "dynamic")

    if local_version == "dynamic":
        attr = pyproject["tool"]["setuptools"]["dynamic"]["version"]["attr"]
        module_path, attr_name = attr.rsplit(".", 1)
        init_file = Path(module_path.replace(".", "/")) / "__init__.py"
        local_version = next(
            line.split("=")[1].strip().strip("'\"")
            for line in init_file.read_text().splitlines()
            if line.startswith(attr_name)
        )

    if not re.match(r"^\d+\.\d+\.\d+$", local_version):
        print(f"WARNING: Incorrect version pattern: {local_version}")
        return local_version, None, False

    response = requests.get(f"https://pypi.org/pypi/{package_name}/json")
    remote_version = response.json()["info"]["version"] if response.status_code == 200 else None
    print(f"Local: {local_version}, PyPI: {remote_version or 'Not Found'}")

    return local_version, remote_version, should_publish(local_version, remote_version)


def check_pubdev_version(pubspec_yaml="pubspec.yaml"):
    """Compare local and pub.dev package versions to determine if a new version should be published."""
    content = Path(pubspec_yaml).read_text()
    package_name = re.search(r"^name:\s*(.+)$", content, re.MULTILINE).group(1).strip()
    local_version = re.search(r"^version:\s*(.+)$", content, re.MULTILINE).group(1).strip()

    if not re.match(r"^\d+\.\d+\.\d+$", local_version):
        print(f"WARNING: Incorrect version pattern: {local_version}")
        return local_version, None, False

    response = requests.get(f"https://pub.dev/api/packages/{package_name}")
    remote_version = response.json()["latest"]["version"] if response.status_code == 200 else None
    print(f"Local: {local_version}, pub.dev: {remote_version or 'Not Found'}")

    return local_version, remote_version, should_publish(local_version, remote_version)
