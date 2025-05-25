# Ultralytics 🚀 AGPL-3.0 License - https://ultralytics.com/license

# from actions.utils.version_utils import check_pypi_version
# check_pypi_version()

import re
from pathlib import Path

import requests
import tomllib
import yaml


def should_publish(local_version, remote_version):
    """Determine if version should be published based on semver rules."""
    if not remote_version:
        return True
    local_ver, remote_ver = [tuple(map(int, v.split("."))) for v in [local_version, remote_version]]
    maj, min, patch = [l - r for l, r in zip(local_ver, remote_ver)]
    return (
        (maj == 0 and min == 0 and 0 < patch <= 2)
        or (maj == 0 and min == 1 and patch == 0)
        or (maj == 1 and min == 0 and patch == 0)
    )


def check_pypi_version(pyproject_toml="pyproject.toml"):
    """Compare local and PyPI package versions to determine if a new version should be published."""
    pyproject = tomllib.loads(str(Path(pyproject_toml).read_bytes()))
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
    config = yaml.safe_load(Path(pubspec_yaml).read_text())
    package_name, local_version = config["name"], config["version"]

    if not re.match(r"^\d+\.\d+\.\d+$", local_version):
        print(f"WARNING: Incorrect version pattern: {local_version}")
        return local_version, None, False

    response = requests.get(f"https://pub.dev/api/packages/{package_name}")
    remote_version = response.json()["latest"]["version"] if response.status_code == 200 else None
    print(f"Local: {local_version}, pub.dev: {remote_version or 'Not Found'}")

    return local_version, remote_version, should_publish(local_version, remote_version)
