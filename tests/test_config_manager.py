"""Tests for ConfigManager."""

from __future__ import annotations

import json
from pathlib import Path

from gallerydl_beyond.gallerydl_utils.config_manager import ConfigManager


class TestResolvePaths:
    """Test path resolution."""

    def test_resolve_paths_default(self, config_manager: ConfigManager):
        """resolve_paths() should return cwd config path by default."""
        paths = config_manager.resolve_paths()

        assert paths.config_path == Path.cwd() / "config.json"

    def test_resolve_paths_custom(self, config_manager: ConfigManager, tmp_path: Path):
        """resolve_paths() should accept custom path."""
        custom_path = tmp_path / "custom.json"

        paths = config_manager.resolve_paths(custom_path)

        assert paths.config_path == custom_path

    def test_resolve_paths_expands_user(self, config_manager: ConfigManager):
        """resolve_paths() should expand ~ in path."""
        paths = config_manager.resolve_paths("~/config.json")

        assert "~" not in str(paths.config_path)
        assert paths.config_path.is_absolute()


class TestEnsureExists:
    """Test config file creation."""

    def test_ensure_exists_creates_file(self, config_manager: ConfigManager, tmp_config_path: Path):
        """ensure_exists() should create config file if missing."""
        assert not tmp_config_path.exists()

        result = config_manager.ensure_exists(tmp_config_path)

        assert result == tmp_config_path
        assert tmp_config_path.exists()

    def test_ensure_exists_returns_existing(self, config_manager: ConfigManager, tmp_config_path: Path):
        """ensure_exists() should return existing config path."""
        tmp_config_path.write_text('{"test": true}')

        result = config_manager.ensure_exists(tmp_config_path)

        assert result == tmp_config_path
        # Should not overwrite
        content = json.loads(tmp_config_path.read_text())
        assert content.get("test") is True

    def test_ensure_exists_creates_parent_dirs(self, config_manager: ConfigManager, tmp_path: Path):
        """ensure_exists() should create parent directories."""
        deep_path = tmp_path / "a" / "b" / "c" / "config.json"

        config_manager.ensure_exists(deep_path)

        assert deep_path.exists()

    def test_ensure_exists_writes_default_config(self, config_manager: ConfigManager, tmp_config_path: Path):
        """ensure_exists() should write valid JSON with defaults."""
        config_manager.ensure_exists(tmp_config_path)

        content = json.loads(tmp_config_path.read_text())
        assert "extractor" in content
        assert "downloader" in content


class TestLoad:
    """Test config loading."""

    def test_load_creates_if_missing(self, config_manager: ConfigManager, tmp_config_path: Path):
        """load() should create config if missing."""
        assert not tmp_config_path.exists()

        config = config_manager.load(tmp_config_path)

        assert tmp_config_path.exists()
        assert isinstance(config, dict)

    def test_load_returns_dict(self, config_manager: ConfigManager, tmp_config_path: Path, sample_config: dict):
        """load() should return config as dict."""
        tmp_config_path.write_text(json.dumps(sample_config))

        config = config_manager.load(tmp_config_path)

        assert isinstance(config, dict)
        assert config["extractor"]["base-directory"] == "./downloads"

    def test_load_fills_missing_defaults(self, config_manager: ConfigManager, tmp_config_path: Path):
        """load() should fill in missing fields with defaults."""
        tmp_config_path.write_text('{"extractor": {}}')

        config = config_manager.load(tmp_config_path)

        assert config["extractor"]["base-directory"] == "./downloads"
        assert config["extractor"]["archive"] == "./bin/archive.sqlite3"
        assert "downloader" in config

    def test_load_coerces_types(self, config_manager: ConfigManager, tmp_config_path: Path):
        """load() should coerce types for retries and timeout."""
        tmp_config_path.write_text(
            json.dumps(
                {
                    "extractor": {},
                    "downloader": {
                        "retries": "5",  # String instead of int
                        "timeout": "10",  # String instead of float
                    },
                }
            )
        )

        config = config_manager.load(tmp_config_path)

        assert config["downloader"]["retries"] == 5
        assert isinstance(config["downloader"]["retries"], int)
        assert config["downloader"]["timeout"] == 10.0
        assert isinstance(config["downloader"]["timeout"], float)

    def test_load_handles_invalid_types(self, config_manager: ConfigManager, tmp_config_path: Path):
        """load() should use defaults for invalid type values."""
        tmp_config_path.write_text(
            json.dumps(
                {
                    "extractor": {},
                    "downloader": {
                        "retries": "not-a-number",
                        "timeout": "invalid",
                    },
                }
            )
        )

        config = config_manager.load(tmp_config_path)

        assert config["downloader"]["retries"] == 3  # Default
        assert config["downloader"]["timeout"] == 8.0  # Default


class TestSave:
    """Test config saving."""

    def test_save_writes_file(self, config_manager: ConfigManager, tmp_config_path: Path, sample_config: dict):
        """save() should write config to file."""
        config_manager.save(sample_config, tmp_config_path)

        assert tmp_config_path.exists()
        content = json.loads(tmp_config_path.read_text())
        assert content["extractor"]["base-directory"] == "./downloads"

    def test_save_creates_parent_dirs(self, config_manager: ConfigManager, tmp_path: Path, sample_config: dict):
        """save() should create parent directories."""
        deep_path = tmp_path / "x" / "y" / "config.json"

        config_manager.save(sample_config, deep_path)

        assert deep_path.exists()

    def test_save_returns_path(self, config_manager: ConfigManager, tmp_config_path: Path, sample_config: dict):
        """save() should return the config path."""
        result = config_manager.save(sample_config, tmp_config_path)

        assert result == tmp_config_path

    def test_save_formats_json(self, config_manager: ConfigManager, tmp_config_path: Path, sample_config: dict):
        """save() should format JSON with indentation."""
        config_manager.save(sample_config, tmp_config_path)

        content = tmp_config_path.read_text()
        # Check for indentation (pretty-printed)
        assert "\n    " in content or "\n  " in content

    def test_save_fills_defaults(self, config_manager: ConfigManager, tmp_config_path: Path):
        """save() should fill in missing defaults before saving."""
        config_manager.save({"extractor": {}}, tmp_config_path)

        content = json.loads(tmp_config_path.read_text())
        assert content["extractor"]["base-directory"] == "./downloads"
        assert "downloader" in content


class TestUpdateCommonFields:
    """Test updating common config fields."""

    def test_update_common_fields(self, config_manager: ConfigManager, tmp_config_path: Path):
        """update_common_fields() should update specified fields."""
        # Create initial config
        config_manager.save({"extractor": {}, "downloader": {}}, tmp_config_path)

        config_manager.update_common_fields(
            base_directory="/custom/downloads",
            archive_path="/custom/archive.db",
            rate="5M",
            retries=10,
            timeout=30.0,
            config_path=tmp_config_path,
        )

        config = config_manager.load(tmp_config_path)
        assert config["extractor"]["base-directory"] == "/custom/downloads"
        assert config["extractor"]["archive"] == "/custom/archive.db"
        assert config["downloader"]["rate"] == "5M"
        assert config["downloader"]["retries"] == 10
        assert config["downloader"]["timeout"] == 30.0

    def test_update_common_fields_preserves_other(self, config_manager: ConfigManager, tmp_config_path: Path):
        """update_common_fields() should preserve other config fields."""
        initial = {
            "extractor": {
                "base-directory": "./old",
                "custom-field": "preserved",
            },
            "downloader": {},
            "output": {"mode": "terminal"},
        }
        config_manager.save(initial, tmp_config_path)

        config_manager.update_common_fields(
            base_directory="/new",
            archive_path="/archive.db",
            rate="1M",
            retries=3,
            timeout=8.0,
            config_path=tmp_config_path,
        )

        config = config_manager.load(tmp_config_path)
        assert config["extractor"]["custom-field"] == "preserved"
        assert config["output"]["mode"] == "terminal"


class TestCoerceAndFillDefaults:
    """Test config validation and defaults."""

    def test_coerce_non_dict_returns_defaults(self, config_manager: ConfigManager):
        """_coerce_and_fill_defaults() should handle non-dict input."""
        result = config_manager._coerce_and_fill_defaults(None)

        assert isinstance(result, dict)
        assert "extractor" in result
        assert "downloader" in result

    def test_coerce_fills_missing_extractor(self, config_manager: ConfigManager):
        """_coerce_and_fill_defaults() should create extractor section."""
        result = config_manager._coerce_and_fill_defaults({"downloader": {}})

        assert "extractor" in result
        assert result["extractor"]["base-directory"] == "./downloads"

    def test_coerce_fills_missing_downloader(self, config_manager: ConfigManager):
        """_coerce_and_fill_defaults() should create downloader section."""
        result = config_manager._coerce_and_fill_defaults({"extractor": {}})

        assert "downloader" in result
        assert result["downloader"]["rate"] == "1M"

    def test_coerce_preserves_valid_values(self, config_manager: ConfigManager):
        """_coerce_and_fill_defaults() should preserve valid existing values."""
        result = config_manager._coerce_and_fill_defaults(
            {
                "extractor": {"base-directory": "/custom"},
                "downloader": {"retries": 5, "timeout": 15.0},
            }
        )

        assert result["extractor"]["base-directory"] == "/custom"
        assert result["downloader"]["retries"] == 5
        assert result["downloader"]["timeout"] == 15.0


class TestDefaultConfig:
    """Test default config values."""

    def test_default_config_structure(self, config_manager: ConfigManager):
        """_default_config() should return expected structure."""
        default = config_manager._default_config()

        assert "extractor" in default
        assert "downloader" in default
        assert default["extractor"]["base-directory"] == "./downloads"
        assert default["extractor"]["archive"] == "./bin/archive.sqlite3"
        assert default["downloader"]["rate"] == "1M"
        assert default["downloader"]["retries"] == 3
        assert default["downloader"]["timeout"] == 8.0
