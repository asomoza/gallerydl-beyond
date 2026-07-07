from __future__ import annotations

import logging
import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Iterator, Literal

from PyQt6.QtCore import QSettings

from gallerydl_beyond.common.constants import SettingsKeys


logger = logging.getLogger(__name__)


def is_frozen() -> bool:
    """Check if running as a PyInstaller frozen executable."""
    return getattr(sys, "frozen", False) or hasattr(sys, "_MEIPASS")


GalleryDLMode = Literal["auto", "system", "python", "external_python", "custom"]
_VALID_MODES: frozenset[str] = frozenset({"auto", "system", "python", "external_python", "custom"})


@dataclass(frozen=True)
class GalleryDLResolution:
    mode: GalleryDLMode
    command: list[str]
    display: str


@dataclass(frozen=True)
class DiscoveredEnv:
    """A Python environment that has gallery-dl available."""

    interp: Path
    version: str
    source: str  # human-readable label: "pipx", "uv tools", ".venv", "~/.virtualenvs/<name>"


def _venv_python(venv_root: Path) -> Path:
    """Return the path to a venv's Python interpreter, regardless of platform."""
    if sys.platform == "win32":
        return venv_root / "Scripts" / "python.exe"
    return venv_root / "bin" / "python"


class GalleryDLManager:
    def __init__(self, settings: QSettings):
        self._settings = settings

    def get_mode(self) -> GalleryDLMode:
        mode = self._settings.value(SettingsKeys.GALLERYDL_MODE)
        if mode in _VALID_MODES:
            return mode  # type: ignore[return-value]
        return "auto"

    def set_mode(self, mode: GalleryDLMode) -> None:
        self._settings.setValue(SettingsKeys.GALLERYDL_MODE, mode)

    def get_custom_path(self) -> str | None:
        value = self._settings.value(SettingsKeys.GALLERYDL_PATH)
        if value is None:
            value = self._settings.value(SettingsKeys.GALLERYDL_CUSTOM_PATH)
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def set_custom_path(self, path: str | None) -> None:
        if path and path.strip():
            self._settings.setValue(SettingsKeys.GALLERYDL_CUSTOM_PATH, path.strip())
            # Back-compat: older code reads GALLERYDL_PATH
            self._settings.setValue(SettingsKeys.GALLERYDL_PATH, path.strip())
        else:
            self._settings.remove(SettingsKeys.GALLERYDL_CUSTOM_PATH)
            self._settings.remove(SettingsKeys.GALLERYDL_PATH)

    def get_external_interp(self) -> str | None:
        value = self._settings.value(SettingsKeys.GALLERYDL_EXTERNAL_INTERP)
        if isinstance(value, str) and value.strip():
            return value.strip()
        return None

    def set_external_interp(self, path: str | None) -> None:
        if path and path.strip():
            self._settings.setValue(SettingsKeys.GALLERYDL_EXTERNAL_INTERP, path.strip())
        else:
            self._settings.remove(SettingsKeys.GALLERYDL_EXTERNAL_INTERP)

    def detect_system(self) -> str | None:
        return shutil.which("gallery-dl")

    def detect_python_module(self, timeout_s: float = 5.0) -> bool:
        # When frozen (PyInstaller), sys.executable is the bundled app, not Python
        if is_frozen():
            return False
        return self.probe_interpreter(sys.executable, timeout_s=timeout_s) is not None

    @staticmethod
    def probe_interpreter(interp: str | Path, timeout_s: float = 5.0) -> str | None:
        """Run `<interp> -m gallery_dl --version`. Returns the version string, or None.

        Works for any Python interpreter — current process, a discovered venv,
        a pipx-managed env, anything. Returning a version (rather than a bool)
        lets callers display it in the UI without a second probe.
        """
        interp_path = Path(interp)
        if not interp_path.exists() or not interp_path.is_file():
            return None
        # On POSIX, ensure it's executable. On Windows, os.access(X_OK) is unreliable
        # so skip the check there.
        if sys.platform != "win32" and not os.access(interp_path, os.X_OK):
            return None
        try:
            result = subprocess.run(
                [str(interp_path), "-m", "gallery_dl", "--version"],
                capture_output=True,
                text=True,
                timeout=timeout_s,
            )
        except (subprocess.TimeoutExpired, OSError) as exc:
            logger.debug("probe_interpreter %s failed: %s", interp_path, exc)
            return None
        if result.returncode != 0:
            return None
        version = result.stdout.strip()
        return version or "unknown"

    def discover_environments(self, timeout_s: float = 3.0) -> list[DiscoveredEnv]:
        """Scan well-known venv layouts for one that has gallery-dl available.

        Best-effort and side-effect-free: we only invoke `<interp> -m gallery_dl
        --version` on candidates that exist on disk. The list of locations is
        intentionally short — broader env discovery (uv project envs, conda,
        arbitrary user-named venvs) belongs in a follow-up.
        """
        seen: set[Path] = set()
        results: list[DiscoveredEnv] = []
        for interp, source in _iter_candidate_interpreters():
            try:
                resolved = interp.resolve()
            except OSError:
                continue
            if resolved in seen:
                continue
            seen.add(resolved)
            version = self.probe_interpreter(resolved, timeout_s=timeout_s)
            if version is not None:
                results.append(DiscoveredEnv(interp=resolved, version=version, source=source))
        return results

    def resolve(self) -> GalleryDLResolution | None:
        mode = self.get_mode()

        if mode == "system":
            system_path = self.detect_system()
            if system_path:
                return GalleryDLResolution(mode="system", command=[system_path], display=system_path)
            return None

        if mode == "python":
            if self.detect_python_module():
                return GalleryDLResolution(
                    mode="python", command=[sys.executable, "-m", "gallery_dl"], display="python -m gallery_dl"
                )
            return None

        if mode == "external_python":
            interp = self.get_external_interp()
            if not interp:
                return None
            if self.probe_interpreter(interp) is None:
                return None
            return GalleryDLResolution(
                mode="external_python",
                command=[interp, "-m", "gallery_dl"],
                display=f"{interp} -m gallery_dl",
            )

        if mode == "custom":
            custom_path = self.get_custom_path()
            if not custom_path:
                return None
            path = Path(custom_path)
            if not path.exists() or not path.is_file():
                return None
            return GalleryDLResolution(mode="custom", command=[str(path)], display=str(path))

        # auto
        system_path = self.detect_system()
        if system_path:
            return GalleryDLResolution(mode="system", command=[system_path], display=system_path)
        if self.detect_python_module():
            return GalleryDLResolution(
                mode="python", command=[sys.executable, "-m", "gallery_dl"], display="python -m gallery_dl"
            )
        return None

    def can_self_update(self, resolved: GalleryDLResolution) -> bool:
        """Check if we can safely auto-update gallery-dl.

        Safe to update when:
        - mode is 'python' (using python -m gallery_dl in the host env)
        - mode is 'external_python' (we own the target interpreter, so
          `<interp> -m pip install -U` / `uv sync` against its project both
          work)
        - the resolved path is inside the current venv (`sys.prefix`)

        Never safe when running as a frozen PyInstaller executable.
        """
        if is_frozen():
            return False
        if resolved.mode == "python":
            return True
        if resolved.mode == "external_python":
            return True
        # Check if resolved path is inside current venv
        if resolved.command:
            try:
                resolved_path = Path(resolved.command[0]).resolve()
                venv_prefix = Path(sys.prefix).resolve()
                if str(resolved_path).startswith(str(venv_prefix)):
                    return True
            except Exception:
                pass
        return False

    def try_update(self) -> tuple[bool, str]:
        """Update gallery-dl using the right strategy for the current mode.

        Mode dispatch:
        - `external_python`: target the interpreter the user pointed at. The
          host venv has nothing to do with the gallery-dl install in this
          mode — running `<sys.executable> -m pip install -U` would update
          the *wrong* env entirely.
        - everything else (`auto` / `system` / `python` / `custom`): target
          the host interpreter. For `system` / `custom` resolutions inside
          the current venv this is correct; for paths *outside* the venv
          (e.g. pipx) the upgrade either no-ops or fails — the dialog gates
          the button on `can_self_update()` to avoid that case.

        Returns: (ok, message)
        """
        if is_frozen():
            return False, "Cannot update gallery-dl from frozen executable"

        if self.get_mode() == "external_python":
            interp = self.get_external_interp()
            if not interp:
                return False, "External Python: no interpreter is configured"
            return _upgrade_with_interp(interp)

        return _upgrade_with_interp(sys.executable)

    def try_update_in_current_env(self) -> tuple[bool, str]:
        """Update gallery-dl in the host Python environment.

        Kept as a thin alias for `_upgrade_with_interp(sys.executable)` so
        existing callers (and tests) keep working. New code should use
        `try_update()`, which dispatches by mode.
        """
        if is_frozen():
            return False, "Cannot update gallery-dl from frozen executable"
        return _upgrade_with_interp(sys.executable)


def _find_uv_project_root(start: str | Path | None = None) -> Path | None:
    """Walk up from `start` looking for a uv-managed project root.

    A uv project is identified by the pair `pyproject.toml` + `uv.lock`. The
    default start point is `sys.prefix` (the running app's venv), but callers
    that want to detect a project around a different interpreter — e.g. the
    one selected in `external_python` mode — pass in that interpreter's
    location instead, so the answer reflects the *target* environment, not
    the host.

    Starting from a known interpreter location (rather than `os.getcwd()`)
    keeps detection deterministic regardless of how the app was launched.
    Frozen builds always return None: there is no editable project to sync.
    """
    if is_frozen():
        return None
    try:
        start_path = Path(start if start is not None else sys.prefix).resolve()
    except OSError:
        return None
    for candidate in (start_path, *start_path.parents):
        if (candidate / "uv.lock").is_file() and (candidate / "pyproject.toml").is_file():
            return candidate
    return None


def _upgrade_with_interp(interp: str | Path) -> tuple[bool, str]:
    """Upgrade gallery-dl in the environment owned by `interp`.

    Strategy mirrors `try_update_in_current_env`, but parameterised on a
    target interpreter so it works for both the host venv (`sys.executable`)
    and an `external_python` interpreter the user pointed at:

    1. If `interp` lives inside a uv-managed project, run `uv sync
       --upgrade-package gallery-dl` with `cwd=<project>`. That updates
       `uv.lock` too, so a subsequent `uv run` won't revert the upgrade.
       On non-zero exit we surface the failure rather than falling through —
       silently doing a venv-only `uv pip install` would hide a
       lockfile-relevant error from the user.
    2. Otherwise, fall back to `uv pip install --python <interp> --upgrade
       gallery-dl`, then `<interp> -m pip install --upgrade gallery-dl`.
       `--python` is what makes uv install into the *target* env when we're
       not running with that interpreter ourselves.

    Returns: (ok, message)
    """
    interp_str = str(interp)
    project_root = _find_uv_project_root(Path(interp).parent)

    if project_root is not None:
        try:
            process = subprocess.run(
                ["uv", "sync", "--upgrade-package", "gallery-dl"],
                capture_output=True,
                text=True,
                cwd=str(project_root),
            )
        except FileNotFoundError:
            # uv is not installed — fall through to the pip path.
            pass
        except Exception as exc:
            return False, str(exc)
        else:
            output = process.stderr.strip() or process.stdout.strip()
            if process.returncode == 0:
                return True, output or f"gallery-dl updated in {project_root}"
            return False, output or f"uv sync failed (exit {process.returncode})"

    for update_cmd in (
        ["uv", "pip", "install", "--python", interp_str, "--upgrade", "gallery-dl"],
        [interp_str, "-m", "pip", "install", "--upgrade", "gallery-dl"],
    ):
        try:
            process = subprocess.run(update_cmd, capture_output=True, text=True)
            if process.returncode == 0:
                return True, process.stdout.strip() or "gallery-dl updated"
            stderr = process.stderr.strip()
            stdout = process.stdout.strip()
            return False, stderr or stdout or f"Update failed (exit {process.returncode})"
        except FileNotFoundError:
            continue
        except Exception as exc:
            return False, str(exc)
    return False, "Neither uv nor pip was available to update gallery-dl"


def _iter_candidate_interpreters() -> Iterator[tuple[Path, str]]:
    """Yield (interpreter_path, source_label) for likely venv locations.

    Order matters: most-specific (pipx, uv tools) first, then general locations.
    The caller deduplicates by resolved path, so symlinks pointing to the same
    interpreter only appear once.
    """
    home = Path.home()

    # pipx — `pipx install gallery-dl` is the most common user install path
    yield _venv_python(home / ".local" / "share" / "pipx" / "venvs" / "gallery-dl"), "pipx"
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            yield _venv_python(Path(appdata) / "pipx" / "venvs" / "gallery-dl"), "pipx"

    # uv tools — `uv tool install gallery-dl`
    yield _venv_python(home / ".local" / "share" / "uv" / "tools" / "gallery-dl"), "uv tools"
    if sys.platform == "win32":
        appdata = os.environ.get("APPDATA")
        if appdata:
            yield _venv_python(Path(appdata) / "uv" / "tools" / "gallery-dl"), "uv tools"

    # Project-local .venv next to the current working directory
    cwd_venv = Path.cwd() / ".venv"
    if cwd_venv.is_dir():
        yield _venv_python(cwd_venv), ".venv (cwd)"

    # Classic ~/.virtualenvs/<name>/
    virtualenvs = home / ".virtualenvs"
    if virtualenvs.is_dir():
        for entry in sorted(virtualenvs.iterdir()):
            if entry.is_dir():
                yield _venv_python(entry), f"~/.virtualenvs/{entry.name}"
