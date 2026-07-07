"""Tests for GalleryDLManager."""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

from gallerydl_beyond.common.constants import SettingsKeys
from gallerydl_beyond.gallerydl_utils.gallerydl_manager import (
    GalleryDLManager,
    GalleryDLResolution,
)


class TestGetMode:
    """Test mode retrieval from settings."""

    def test_get_mode_default_auto(self, mock_qsettings):
        """get_mode() should return 'auto' by default."""
        manager = GalleryDLManager(mock_qsettings)

        mode = manager.get_mode()

        assert mode == "auto"

    def test_get_mode_returns_stored_value(self, mock_qsettings):
        """get_mode() should return stored mode."""
        mock_qsettings._store[SettingsKeys.GALLERYDL_MODE] = "system"
        manager = GalleryDLManager(mock_qsettings)

        mode = manager.get_mode()

        assert mode == "system"

    def test_get_mode_invalid_returns_auto(self, mock_qsettings):
        """get_mode() should return 'auto' for invalid stored value."""
        mock_qsettings._store[SettingsKeys.GALLERYDL_MODE] = "invalid"
        manager = GalleryDLManager(mock_qsettings)

        mode = manager.get_mode()

        assert mode == "auto"


class TestSetMode:
    """Test mode persistence to settings."""

    def test_set_mode_stores_value(self, mock_qsettings):
        """set_mode() should store mode in settings."""
        manager = GalleryDLManager(mock_qsettings)

        manager.set_mode("python")

        assert mock_qsettings._store[SettingsKeys.GALLERYDL_MODE] == "python"


class TestGetCustomPath:
    """Test custom path retrieval."""

    def test_get_custom_path_none_by_default(self, mock_qsettings):
        """get_custom_path() should return None by default."""
        manager = GalleryDLManager(mock_qsettings)

        path = manager.get_custom_path()

        assert path is None

    def test_get_custom_path_returns_stored(self, mock_qsettings):
        """get_custom_path() should return stored path."""
        mock_qsettings._store[SettingsKeys.GALLERYDL_CUSTOM_PATH] = "/usr/bin/gallery-dl"
        manager = GalleryDLManager(mock_qsettings)

        path = manager.get_custom_path()

        assert path == "/usr/bin/gallery-dl"

    def test_get_custom_path_falls_back_to_legacy(self, mock_qsettings):
        """get_custom_path() should fall back to legacy GALLERYDL_PATH."""
        mock_qsettings._store[SettingsKeys.GALLERYDL_PATH] = "/legacy/path"
        manager = GalleryDLManager(mock_qsettings)

        path = manager.get_custom_path()

        assert path == "/legacy/path"

    def test_get_custom_path_strips_whitespace(self, mock_qsettings):
        """get_custom_path() should strip whitespace."""
        mock_qsettings._store[SettingsKeys.GALLERYDL_CUSTOM_PATH] = "  /path/to/binary  "
        manager = GalleryDLManager(mock_qsettings)

        path = manager.get_custom_path()

        assert path == "/path/to/binary"

    def test_get_custom_path_empty_returns_none(self, mock_qsettings):
        """get_custom_path() should return None for empty string."""
        mock_qsettings._store[SettingsKeys.GALLERYDL_CUSTOM_PATH] = "   "
        manager = GalleryDLManager(mock_qsettings)

        path = manager.get_custom_path()

        assert path is None


class TestSetCustomPath:
    """Test custom path persistence."""

    def test_set_custom_path_stores_value(self, mock_qsettings):
        """set_custom_path() should store path in settings."""
        manager = GalleryDLManager(mock_qsettings)

        manager.set_custom_path("/custom/gallery-dl")

        assert mock_qsettings._store[SettingsKeys.GALLERYDL_CUSTOM_PATH] == "/custom/gallery-dl"
        # Should also set legacy key for back-compat
        assert mock_qsettings._store[SettingsKeys.GALLERYDL_PATH] == "/custom/gallery-dl"

    def test_set_custom_path_strips_whitespace(self, mock_qsettings):
        """set_custom_path() should strip whitespace."""
        manager = GalleryDLManager(mock_qsettings)

        manager.set_custom_path("  /path/to/binary  ")

        assert mock_qsettings._store[SettingsKeys.GALLERYDL_CUSTOM_PATH] == "/path/to/binary"

    def test_set_custom_path_none_removes(self, mock_qsettings):
        """set_custom_path(None) should remove keys."""
        mock_qsettings._store[SettingsKeys.GALLERYDL_CUSTOM_PATH] = "/old/path"
        mock_qsettings._store[SettingsKeys.GALLERYDL_PATH] = "/old/path"
        manager = GalleryDLManager(mock_qsettings)

        manager.set_custom_path(None)

        assert SettingsKeys.GALLERYDL_CUSTOM_PATH not in mock_qsettings._store
        assert SettingsKeys.GALLERYDL_PATH not in mock_qsettings._store

    def test_set_custom_path_empty_removes(self, mock_qsettings):
        """set_custom_path('') should remove keys."""
        mock_qsettings._store[SettingsKeys.GALLERYDL_CUSTOM_PATH] = "/old/path"
        manager = GalleryDLManager(mock_qsettings)

        manager.set_custom_path("")

        assert SettingsKeys.GALLERYDL_CUSTOM_PATH not in mock_qsettings._store


class TestDetectSystem:
    """Test system gallery-dl detection."""

    def test_detect_system_found(self, mock_qsettings):
        """detect_system() should return path when found."""
        manager = GalleryDLManager(mock_qsettings)

        with patch("shutil.which", return_value="/usr/bin/gallery-dl"):
            result = manager.detect_system()

        assert result == "/usr/bin/gallery-dl"

    def test_detect_system_not_found(self, mock_qsettings):
        """detect_system() should return None when not found."""
        manager = GalleryDLManager(mock_qsettings)

        with patch("shutil.which", return_value=None):
            result = manager.detect_system()

        assert result is None


class TestDetectPythonModule:
    """Test Python module gallery-dl detection."""

    def test_detect_python_module_success(self, mock_qsettings):
        """detect_python_module() should return True on success."""
        manager = GalleryDLManager(mock_qsettings)

        mock_result = MagicMock()
        mock_result.returncode = 0

        with patch("subprocess.run", return_value=mock_result):
            result = manager.detect_python_module()

        assert result is True

    def test_detect_python_module_failure(self, mock_qsettings):
        """detect_python_module() should return False on failure."""
        manager = GalleryDLManager(mock_qsettings)

        mock_result = MagicMock()
        mock_result.returncode = 1

        with patch("subprocess.run", return_value=mock_result):
            result = manager.detect_python_module()

        assert result is False

    def test_detect_python_module_exception(self, mock_qsettings):
        """detect_python_module() should return False on exception."""
        manager = GalleryDLManager(mock_qsettings)

        with patch("subprocess.run", side_effect=FileNotFoundError):
            result = manager.detect_python_module()

        assert result is False


class TestResolve:
    """Test gallery-dl resolution based on mode."""

    def test_resolve_system_mode_found(self, mock_qsettings):
        """resolve() in system mode should return system path."""
        mock_qsettings._store[SettingsKeys.GALLERYDL_MODE] = "system"
        manager = GalleryDLManager(mock_qsettings)

        with patch.object(manager, "detect_system", return_value="/usr/bin/gallery-dl"):
            result = manager.resolve()

        assert result is not None
        assert result.mode == "system"
        assert result.command == ["/usr/bin/gallery-dl"]

    def test_resolve_system_mode_not_found(self, mock_qsettings):
        """resolve() in system mode should return None if not found."""
        mock_qsettings._store[SettingsKeys.GALLERYDL_MODE] = "system"
        manager = GalleryDLManager(mock_qsettings)

        with patch.object(manager, "detect_system", return_value=None):
            result = manager.resolve()

        assert result is None

    def test_resolve_python_mode_found(self, mock_qsettings):
        """resolve() in python mode should return python -m command."""
        mock_qsettings._store[SettingsKeys.GALLERYDL_MODE] = "python"
        manager = GalleryDLManager(mock_qsettings)

        with patch.object(manager, "detect_python_module", return_value=True):
            result = manager.resolve()

        assert result is not None
        assert result.mode == "python"
        assert result.command == [sys.executable, "-m", "gallery_dl"]

    def test_resolve_python_mode_not_found(self, mock_qsettings):
        """resolve() in python mode should return None if not available."""
        mock_qsettings._store[SettingsKeys.GALLERYDL_MODE] = "python"
        manager = GalleryDLManager(mock_qsettings)

        with patch.object(manager, "detect_python_module", return_value=False):
            result = manager.resolve()

        assert result is None

    def test_resolve_custom_mode_valid_path(self, mock_qsettings, tmp_path: Path):
        """resolve() in custom mode should return custom path if valid."""
        custom_bin = tmp_path / "gallery-dl"
        custom_bin.touch()

        mock_qsettings._store[SettingsKeys.GALLERYDL_MODE] = "custom"
        mock_qsettings._store[SettingsKeys.GALLERYDL_CUSTOM_PATH] = str(custom_bin)
        manager = GalleryDLManager(mock_qsettings)

        result = manager.resolve()

        assert result is not None
        assert result.mode == "custom"
        assert result.command == [str(custom_bin)]

    def test_resolve_custom_mode_no_path(self, mock_qsettings):
        """resolve() in custom mode should return None if no path set."""
        mock_qsettings._store[SettingsKeys.GALLERYDL_MODE] = "custom"
        manager = GalleryDLManager(mock_qsettings)

        result = manager.resolve()

        assert result is None

    def test_resolve_custom_mode_invalid_path(self, mock_qsettings, tmp_path: Path):
        """resolve() in custom mode should return None for non-existent path."""
        mock_qsettings._store[SettingsKeys.GALLERYDL_MODE] = "custom"
        mock_qsettings._store[SettingsKeys.GALLERYDL_CUSTOM_PATH] = str(tmp_path / "nonexistent")
        manager = GalleryDLManager(mock_qsettings)

        result = manager.resolve()

        assert result is None

    def test_resolve_auto_mode_prefers_system(self, mock_qsettings):
        """resolve() in auto mode should prefer system over python."""
        mock_qsettings._store[SettingsKeys.GALLERYDL_MODE] = "auto"
        manager = GalleryDLManager(mock_qsettings)

        with (
            patch.object(manager, "detect_system", return_value="/usr/bin/gallery-dl"),
            patch.object(manager, "detect_python_module", return_value=True),
        ):
            result = manager.resolve()

        assert result is not None
        assert result.mode == "system"

    def test_resolve_auto_mode_falls_back_to_python(self, mock_qsettings):
        """resolve() in auto mode should fall back to python if no system."""
        mock_qsettings._store[SettingsKeys.GALLERYDL_MODE] = "auto"
        manager = GalleryDLManager(mock_qsettings)

        with (
            patch.object(manager, "detect_system", return_value=None),
            patch.object(manager, "detect_python_module", return_value=True),
        ):
            result = manager.resolve()

        assert result is not None
        assert result.mode == "python"

    def test_resolve_auto_mode_nothing_found(self, mock_qsettings):
        """resolve() in auto mode should return None if nothing found."""
        mock_qsettings._store[SettingsKeys.GALLERYDL_MODE] = "auto"
        manager = GalleryDLManager(mock_qsettings)

        with (
            patch.object(manager, "detect_system", return_value=None),
            patch.object(manager, "detect_python_module", return_value=False),
        ):
            result = manager.resolve()

        assert result is None


class TestCanSelfUpdate:
    """Test self-update capability check."""

    def test_can_self_update_python_mode(self, mock_qsettings):
        """can_self_update() should return True for python mode."""
        manager = GalleryDLManager(mock_qsettings)
        resolution = GalleryDLResolution(
            mode="python",
            command=[sys.executable, "-m", "gallery_dl"],
            display="python -m gallery_dl",
        )

        assert manager.can_self_update(resolution) is True

    def test_can_self_update_auto_mode_system_path(self, mock_qsettings):
        """can_self_update() should return False for auto mode with system path."""
        manager = GalleryDLManager(mock_qsettings)
        resolution = GalleryDLResolution(
            mode="auto",
            command=["/usr/bin/gallery-dl"],
            display="/usr/bin/gallery-dl",
        )

        # System path outside venv should not be updatable
        assert manager.can_self_update(resolution) is False

    def test_can_self_update_auto_mode_venv_path(self, mock_qsettings):
        """can_self_update() should return True for auto mode with venv path."""
        import sys

        manager = GalleryDLManager(mock_qsettings)
        # Path inside current venv should be updatable
        venv_path = f"{sys.prefix}/bin/gallery-dl"
        resolution = GalleryDLResolution(
            mode="auto",
            command=[venv_path],
            display=venv_path,
        )

        assert manager.can_self_update(resolution) is True

    def test_can_self_update_system_mode_different_python(self, mock_qsettings):
        """can_self_update() should return False for system mode with external binary."""
        manager = GalleryDLManager(mock_qsettings)
        resolution = GalleryDLResolution(
            mode="system",
            command=["/usr/bin/gallery-dl"],
            display="/usr/bin/gallery-dl",
        )

        assert manager.can_self_update(resolution) is False

    def test_can_self_update_custom_mode(self, mock_qsettings):
        """can_self_update() should return False for custom mode."""
        manager = GalleryDLManager(mock_qsettings)
        resolution = GalleryDLResolution(
            mode="custom",
            command=["/custom/gallery-dl"],
            display="/custom/gallery-dl",
        )

        assert manager.can_self_update(resolution) is False


class TestTryUpdateInCurrentEnv:
    """Test gallery-dl update functionality."""

    def test_try_update_success_uv(self, mock_qsettings):
        """try_update_in_current_env() should succeed with uv."""
        manager = GalleryDLManager(mock_qsettings)

        mock_result = MagicMock()
        mock_result.returncode = 0
        # When running inside a uv-managed project, the chosen command is
        # `uv sync --upgrade-package` and uv writes its output to stderr.
        mock_result.stderr = "Resolved 50 packages\nInstalled gallery-dl"
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            ok, message = manager.try_update_in_current_env()

        assert ok is True
        assert "gallery-dl" in message

    def test_try_update_failure(self, mock_qsettings):
        """try_update_in_current_env() should return failure on error."""
        manager = GalleryDLManager(mock_qsettings)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Permission denied"
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            ok, message = manager.try_update_in_current_env()

        assert ok is False
        assert "Permission denied" in message

    def test_try_update_no_pip_no_uv(self, mock_qsettings):
        """try_update_in_current_env() should handle missing pip and uv."""
        manager = GalleryDLManager(mock_qsettings)

        with patch("subprocess.run", side_effect=FileNotFoundError):
            ok, message = manager.try_update_in_current_env()

        assert ok is False
        assert "uv" in message.lower() or "pip" in message.lower()


class TestGetMode_ExternalPython:
    """The new external_python mode round-trips through QSettings."""

    def test_get_mode_external_python(self, mock_qsettings):
        mock_qsettings._store[SettingsKeys.GALLERYDL_MODE] = "external_python"
        manager = GalleryDLManager(mock_qsettings)

        assert manager.get_mode() == "external_python"

    def test_set_mode_external_python(self, mock_qsettings):
        manager = GalleryDLManager(mock_qsettings)

        manager.set_mode("external_python")

        assert mock_qsettings._store[SettingsKeys.GALLERYDL_MODE] == "external_python"


class TestExternalInterp:
    """get/set for the external interpreter path."""

    def test_get_external_interp_none_by_default(self, mock_qsettings):
        manager = GalleryDLManager(mock_qsettings)
        assert manager.get_external_interp() is None

    def test_get_external_interp_returns_stored(self, mock_qsettings):
        mock_qsettings._store[SettingsKeys.GALLERYDL_EXTERNAL_INTERP] = "/opt/venv/bin/python"
        manager = GalleryDLManager(mock_qsettings)
        assert manager.get_external_interp() == "/opt/venv/bin/python"

    def test_get_external_interp_strips_whitespace(self, mock_qsettings):
        mock_qsettings._store[SettingsKeys.GALLERYDL_EXTERNAL_INTERP] = "  /a/b/python  "
        manager = GalleryDLManager(mock_qsettings)
        assert manager.get_external_interp() == "/a/b/python"

    def test_set_external_interp_stores(self, mock_qsettings):
        manager = GalleryDLManager(mock_qsettings)
        manager.set_external_interp("/x/python")
        assert mock_qsettings._store[SettingsKeys.GALLERYDL_EXTERNAL_INTERP] == "/x/python"

    def test_set_external_interp_empty_removes(self, mock_qsettings):
        mock_qsettings._store[SettingsKeys.GALLERYDL_EXTERNAL_INTERP] = "/x/python"
        manager = GalleryDLManager(mock_qsettings)
        manager.set_external_interp("")
        assert SettingsKeys.GALLERYDL_EXTERNAL_INTERP not in mock_qsettings._store

    def test_set_external_interp_none_removes(self, mock_qsettings):
        mock_qsettings._store[SettingsKeys.GALLERYDL_EXTERNAL_INTERP] = "/x/python"
        manager = GalleryDLManager(mock_qsettings)
        manager.set_external_interp(None)
        assert SettingsKeys.GALLERYDL_EXTERNAL_INTERP not in mock_qsettings._store


class TestProbeInterpreter:
    """probe_interpreter shells out and parses --version output."""

    def test_probe_returns_version_on_success(self, tmp_path: Path):
        # The interpreter file just needs to exist & be executable; subprocess is mocked.
        fake_interp = tmp_path / "python"
        fake_interp.touch()
        fake_interp.chmod(0o755)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "1.28.0\n"

        with patch("subprocess.run", return_value=mock_result):
            version = GalleryDLManager.probe_interpreter(fake_interp)

        assert version == "1.28.0"

    def test_probe_returns_none_when_file_missing(self, tmp_path: Path):
        version = GalleryDLManager.probe_interpreter(tmp_path / "does_not_exist")
        assert version is None

    def test_probe_returns_none_on_nonzero_exit(self, tmp_path: Path):
        fake_interp = tmp_path / "python"
        fake_interp.touch()
        fake_interp.chmod(0o755)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            version = GalleryDLManager.probe_interpreter(fake_interp)

        assert version is None

    def test_probe_returns_none_on_timeout(self, tmp_path: Path):
        import subprocess as sp

        fake_interp = tmp_path / "python"
        fake_interp.touch()
        fake_interp.chmod(0o755)

        with patch("subprocess.run", side_effect=sp.TimeoutExpired(cmd="x", timeout=1)):
            version = GalleryDLManager.probe_interpreter(fake_interp, timeout_s=0.1)

        assert version is None

    def test_probe_returns_unknown_when_stdout_empty(self, tmp_path: Path):
        # Successful exit but no version printed — still treat as "found", with a sentinel.
        fake_interp = tmp_path / "python"
        fake_interp.touch()
        fake_interp.chmod(0o755)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = ""

        with patch("subprocess.run", return_value=mock_result):
            version = GalleryDLManager.probe_interpreter(fake_interp)

        assert version == "unknown"


class TestDiscoverEnvironments:
    """discover_environments scans well-known locations and probes each."""

    def test_discover_returns_envs_with_versions(self, mock_qsettings, tmp_path: Path):
        # Stub the candidate iterator to point at a controlled tmp interpreter.
        fake_interp = tmp_path / "venv-python"
        fake_interp.touch()
        fake_interp.chmod(0o755)

        manager = GalleryDLManager(mock_qsettings)

        with (
            patch(
                "gallerydl_beyond.gallerydl_utils.gallerydl_manager._iter_candidate_interpreters",
                return_value=iter([(fake_interp, "test-source")]),
            ),
            patch.object(GalleryDLManager, "probe_interpreter", staticmethod(lambda interp, timeout_s=3.0: "1.30.0")),
        ):
            envs = manager.discover_environments()

        assert len(envs) == 1
        assert envs[0].source == "test-source"
        assert envs[0].version == "1.30.0"

    def test_discover_skips_non_matching(self, mock_qsettings, tmp_path: Path):
        fake_interp = tmp_path / "broken-python"
        fake_interp.touch()
        fake_interp.chmod(0o755)

        manager = GalleryDLManager(mock_qsettings)

        with (
            patch(
                "gallerydl_beyond.gallerydl_utils.gallerydl_manager._iter_candidate_interpreters",
                return_value=iter([(fake_interp, "test-source")]),
            ),
            patch.object(GalleryDLManager, "probe_interpreter", staticmethod(lambda interp, timeout_s=3.0: None)),
        ):
            envs = manager.discover_environments()

        assert envs == []

    def test_discover_dedupes_by_resolved_path(self, mock_qsettings, tmp_path: Path):
        # Two sources pointing at the same interpreter should appear once.
        fake_interp = tmp_path / "venv-python"
        fake_interp.touch()
        fake_interp.chmod(0o755)

        manager = GalleryDLManager(mock_qsettings)

        with (
            patch(
                "gallerydl_beyond.gallerydl_utils.gallerydl_manager._iter_candidate_interpreters",
                return_value=iter([(fake_interp, "first"), (fake_interp, "second")]),
            ),
            patch.object(GalleryDLManager, "probe_interpreter", staticmethod(lambda interp, timeout_s=3.0: "1.30.0")),
        ):
            envs = manager.discover_environments()

        assert len(envs) == 1
        assert envs[0].source == "first"


class TestResolveExternalPython:
    """resolve() in external_python mode."""

    def test_resolve_external_python_no_interp(self, mock_qsettings):
        mock_qsettings._store[SettingsKeys.GALLERYDL_MODE] = "external_python"
        manager = GalleryDLManager(mock_qsettings)

        assert manager.resolve() is None

    def test_resolve_external_python_invalid_interp(self, mock_qsettings, tmp_path: Path):
        mock_qsettings._store[SettingsKeys.GALLERYDL_MODE] = "external_python"
        mock_qsettings._store[SettingsKeys.GALLERYDL_EXTERNAL_INTERP] = str(tmp_path / "missing")
        manager = GalleryDLManager(mock_qsettings)

        assert manager.resolve() is None

    def test_resolve_external_python_valid(self, mock_qsettings, tmp_path: Path):
        fake_interp = tmp_path / "python"
        fake_interp.touch()
        fake_interp.chmod(0o755)

        mock_qsettings._store[SettingsKeys.GALLERYDL_MODE] = "external_python"
        mock_qsettings._store[SettingsKeys.GALLERYDL_EXTERNAL_INTERP] = str(fake_interp)
        manager = GalleryDLManager(mock_qsettings)

        with patch.object(GalleryDLManager, "probe_interpreter", staticmethod(lambda interp, timeout_s=5.0: "1.30.0")):
            result = manager.resolve()

        assert result is not None
        assert result.mode == "external_python"
        assert result.command == [str(fake_interp), "-m", "gallery_dl"]
        assert str(fake_interp) in result.display


class TestFindUvProjectRoot:
    """`_find_uv_project_root` walks up from sys.prefix looking for uv.lock + pyproject.toml."""

    def test_finds_project_when_both_files_present(self, tmp_path: Path):
        from gallerydl_beyond.gallerydl_utils import gallerydl_manager as gm

        project = tmp_path / "myproj"
        venv = project / ".venv"
        venv.mkdir(parents=True)
        (project / "pyproject.toml").write_text("[project]\nname='x'\n")
        (project / "uv.lock").write_text("# lock")

        with patch("sys.prefix", str(venv)):
            root = gm._find_uv_project_root()

        assert root == project.resolve()

    def test_returns_none_without_uv_lock(self, tmp_path: Path):
        from gallerydl_beyond.gallerydl_utils import gallerydl_manager as gm

        project = tmp_path / "myproj"
        venv = project / ".venv"
        venv.mkdir(parents=True)
        (project / "pyproject.toml").write_text("[project]\nname='x'\n")
        # Intentionally no uv.lock — pip-installed project, not uv-managed.

        with patch("sys.prefix", str(venv)):
            root = gm._find_uv_project_root()

        assert root is None

    def test_returns_none_when_frozen(self, tmp_path: Path):
        from gallerydl_beyond.gallerydl_utils import gallerydl_manager as gm

        project = tmp_path / "myproj"
        venv = project / ".venv"
        venv.mkdir(parents=True)
        (project / "pyproject.toml").write_text("")
        (project / "uv.lock").write_text("")

        with (
            patch("sys.prefix", str(venv)),
            patch.object(gm, "is_frozen", return_value=True),
        ):
            root = gm._find_uv_project_root()

        assert root is None


class TestTryUpdateUvSyncBranch:
    """When inside a uv-managed project, prefer `uv sync --upgrade-package`."""

    def test_uv_sync_chosen_and_succeeds(self, mock_qsettings, tmp_path: Path):
        from gallerydl_beyond.gallerydl_utils import gallerydl_manager as gm

        project = tmp_path / "proj"
        project.mkdir()
        manager = GalleryDLManager(mock_qsettings)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stderr = "Resolved 50 packages\nInstalled 1 package"
        mock_result.stdout = ""

        with (
            patch.object(gm, "_find_uv_project_root", return_value=project),
            patch("subprocess.run", return_value=mock_result) as run_mock,
        ):
            ok, message = manager.try_update_in_current_env()

        assert ok is True
        assert "Installed 1 package" in message
        # uv sync invoked with the project as cwd (not via --directory).
        args, kwargs = run_mock.call_args
        assert args[0][:2] == ["uv", "sync"]
        assert "--upgrade-package" in args[0]
        assert "gallery-dl" in args[0]
        assert kwargs.get("cwd") == str(project)

    def test_uv_sync_failure_does_not_fall_through_to_pip(self, mock_qsettings, tmp_path: Path):
        # If `uv sync` runs and fails (e.g. network error), surface the failure
        # instead of trying `uv pip install` — that would silently update the
        # venv only, hiding the lockfile-relevant error from the user.
        from gallerydl_beyond.gallerydl_utils import gallerydl_manager as gm

        project = tmp_path / "proj"
        project.mkdir()
        manager = GalleryDLManager(mock_qsettings)

        mock_result = MagicMock()
        mock_result.returncode = 1
        mock_result.stderr = "Network is unreachable"
        mock_result.stdout = ""

        with (
            patch.object(gm, "_find_uv_project_root", return_value=project),
            patch("subprocess.run", return_value=mock_result) as run_mock,
        ):
            ok, message = manager.try_update_in_current_env()

        assert ok is False
        assert "Network is unreachable" in message
        # Only one subprocess call — we did not fall back to pip.
        assert run_mock.call_count == 1

    def test_uv_missing_falls_back_to_pip_path(self, mock_qsettings, tmp_path: Path):
        # If uv itself is not on PATH, the `uv sync` attempt raises
        # FileNotFoundError; the fallback chain (uv pip → python -m pip)
        # then runs as before.
        from gallerydl_beyond.gallerydl_utils import gallerydl_manager as gm

        project = tmp_path / "proj"
        project.mkdir()
        manager = GalleryDLManager(mock_qsettings)

        ok_result = MagicMock()
        ok_result.returncode = 0
        ok_result.stdout = "Successfully installed gallery-dl-1.32.0"

        # First call (uv sync) raises FileNotFoundError; second call (uv pip
        # install) also raises; third (python -m pip) succeeds.
        side_effects = [FileNotFoundError(), FileNotFoundError(), ok_result]

        with (
            patch.object(gm, "_find_uv_project_root", return_value=project),
            patch("subprocess.run", side_effect=side_effects) as run_mock,
        ):
            ok, message = manager.try_update_in_current_env()

        assert ok is True
        assert "gallery-dl" in message
        assert run_mock.call_count == 3


class TestTryUpdatePipFallbackBranch:
    """Outside a uv-managed project, `try_update_in_current_env` uses uv pip / pip."""

    def test_no_project_uses_uv_pip(self, mock_qsettings):
        from gallerydl_beyond.gallerydl_utils import gallerydl_manager as gm

        manager = GalleryDLManager(mock_qsettings)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Successfully installed gallery-dl-1.32.0"

        with (
            patch.object(gm, "_find_uv_project_root", return_value=None),
            patch("subprocess.run", return_value=mock_result) as run_mock,
        ):
            ok, message = manager.try_update_in_current_env()

        assert ok is True
        assert "gallery-dl" in message
        # First call should be `uv pip install --upgrade gallery-dl`.
        args, _ = run_mock.call_args_list[0]
        assert args[0][:3] == ["uv", "pip", "install"]


class TestTryUpdateDispatch:
    """`try_update()` dispatches by mode to the right interpreter."""

    def test_external_python_targets_external_interp(self, mock_qsettings, tmp_path: Path):
        from gallerydl_beyond.gallerydl_utils import gallerydl_manager as gm

        external = tmp_path / "external" / "bin" / "python"
        external.parent.mkdir(parents=True)
        external.touch()
        external.chmod(0o755)

        mock_qsettings._store[SettingsKeys.GALLERYDL_MODE] = "external_python"
        mock_qsettings._store[SettingsKeys.GALLERYDL_EXTERNAL_INTERP] = str(external)
        manager = GalleryDLManager(mock_qsettings)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Successfully installed gallery-dl-1.32.0"
        mock_result.stderr = ""

        with (
            # No uv project around the external interp — force the pip path.
            patch.object(gm, "_find_uv_project_root", return_value=None),
            patch("subprocess.run", return_value=mock_result) as run_mock,
        ):
            ok, message = manager.try_update()

        assert ok is True
        assert "gallery-dl" in message
        # Command should target the external interpreter via `--python`.
        args, _ = run_mock.call_args_list[0]
        assert args[0][:3] == ["uv", "pip", "install"]
        assert "--python" in args[0]
        assert str(external) in args[0]

    def test_external_python_no_interp_configured(self, mock_qsettings):
        # If the user picked external_python but never filled in a path,
        # fail fast with a clear message instead of hitting subprocess.
        mock_qsettings._store[SettingsKeys.GALLERYDL_MODE] = "external_python"
        manager = GalleryDLManager(mock_qsettings)

        with patch("subprocess.run") as run_mock:
            ok, message = manager.try_update()

        assert ok is False
        assert "interpreter" in message.lower()
        run_mock.assert_not_called()

    def test_python_mode_targets_sys_executable(self, mock_qsettings):
        from gallerydl_beyond.gallerydl_utils import gallerydl_manager as gm

        mock_qsettings._store[SettingsKeys.GALLERYDL_MODE] = "python"
        manager = GalleryDLManager(mock_qsettings)

        mock_result = MagicMock()
        mock_result.returncode = 0
        mock_result.stdout = "Successfully installed"
        mock_result.stderr = ""

        with (
            patch.object(gm, "_find_uv_project_root", return_value=None),
            patch("subprocess.run", return_value=mock_result) as run_mock,
        ):
            ok, message = manager.try_update()

        assert ok is True
        # uv pip install should target sys.executable via --python.
        args, _ = run_mock.call_args_list[0]
        assert "--python" in args[0]
        assert sys.executable in args[0]


class TestCanSelfUpdateExternalPython:
    """can_self_update() returns True for external_python mode (we own the env)."""

    def test_external_python_is_updatable(self, mock_qsettings):
        manager = GalleryDLManager(mock_qsettings)

        resolution = GalleryDLResolution(
            mode="external_python",
            command=["/some/external/python", "-m", "gallery_dl"],
            display="/some/external/python -m gallery_dl",
        )

        assert manager.can_self_update(resolution) is True


class TestFindUvProjectRootCustomStart:
    """`_find_uv_project_root` accepts an explicit start path for external interpreters."""

    def test_walks_up_from_explicit_start(self, tmp_path: Path):
        from gallerydl_beyond.gallerydl_utils import gallerydl_manager as gm

        project = tmp_path / "external_project"
        venv_bin = project / ".venv" / "bin"
        venv_bin.mkdir(parents=True)
        (project / "pyproject.toml").write_text("")
        (project / "uv.lock").write_text("")

        # Start from the interpreter's directory rather than sys.prefix.
        root = gm._find_uv_project_root(venv_bin)

        assert root == project.resolve()
