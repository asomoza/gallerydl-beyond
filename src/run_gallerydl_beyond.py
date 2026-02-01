"""PyInstaller-friendly entry point.

This script lives in `src/` so the `gallerydl_beyond` package is importable without
needing to manipulate `sys.path`.
"""

import multiprocessing

if __name__ == "__main__":
    multiprocessing.freeze_support()
    from gallerydl_beyond.__main__ import main
    main()
