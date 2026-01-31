"""PyInstaller-friendly entry point.

This script lives in `src/` so the `gallerydl_beyond` package is importable without
needing to manipulate `sys.path`.
"""

from gallerydl_beyond.__main__ import main


if __name__ == "__main__":
    main()
