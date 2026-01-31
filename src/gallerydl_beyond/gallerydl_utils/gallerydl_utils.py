import logging
import subprocess

import requests
from packaging import version


logger = logging.getLogger(__name__)


def get_installed_version(gallerydl_cmd):
    """Runs gallery-dl --version and parses the output."""
    try:
        if isinstance(gallerydl_cmd, str):
            cmd = [gallerydl_cmd]
        else:
            cmd = list(gallerydl_cmd)
        # Use text=True for automatic decoding, capture_output=True for stdout/stderr
        result = subprocess.run(
            [*cmd, "--version"],
            capture_output=True,
            text=True,
            check=True,  # Raise CalledProcessError if return code is non-zero
            timeout=10,  # Add a timeout
        )
        # Output might be like "gallery-dl 1.25.0\n" or just "1.25.0\n"
        output_lines = result.stdout.strip().splitlines()
        if not output_lines:
            return None
        # Assume the version is the last word on the first line
        version_str = output_lines[0].split()[-1]
        # Basic validation
        if version.parse(version_str):
            return version_str
        return None  # Return None if parsing fails
    except (subprocess.CalledProcessError, subprocess.TimeoutExpired, FileNotFoundError, version.InvalidVersion) as e:
        logger.error(f"Error getting installed version: {e}")
        return None
    except Exception as e:  # Catch unexpected errors
        logger.error(f"Unexpected error getting installed version: {e}")
        return None


def get_latest_version():
    """Fetches the latest version from PyPI."""
    try:
        response = requests.get("https://pypi.org/pypi/gallery-dl/json", timeout=10)
        response.raise_for_status()  # Raise HTTPError for bad responses (4xx or 5xx)
        data = response.json()
        latest_version_str = data.get("info", {}).get("version")
        if latest_version_str and version.parse(latest_version_str):
            return latest_version_str
        return None  # Return None if parsing fails or version not found
    except requests.exceptions.RequestException as e:
        logger.error(f"Network error fetching latest version: {e}")
        return None
    except (KeyError, ValueError, version.InvalidVersion) as e:  # Handle JSON parsing errors or missing keys
        logger.error(f"Error parsing PyPI data: {e}")
        return None
    except Exception as e:  # Catch unexpected errors
        logger.error(f"Unexpected error fetching latest version: {e}")
        return None
