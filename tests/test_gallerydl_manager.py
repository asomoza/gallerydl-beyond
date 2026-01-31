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
        mock_result.stdout = "Successfully installed gallery-dl"

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
