import logging
import logging.config
import multiprocessing
import os
import sys

from gallerydl_beyond.Application.gbeyond_application import GalleryDLBeyondApplication
from gallerydl_beyond.Application.logging_conf import logging_config


def my_exception_hook(exctype, value, traceback):
    # Do something with the exception here, such as logging it
    print(f"Unhandled exception: {value}")
    sys.__excepthook__(exctype, value, traceback)


sys.excepthook = my_exception_hook


def _configure_logging() -> None:
    try:
        log_path = logging_config.get("handlers", {}).get("fileHandler", {}).get("filename")
        if log_path:
            os.makedirs(os.path.dirname(log_path), exist_ok=True)
        logging.config.dictConfig(logging_config)
    except Exception:
        logging.basicConfig(level=logging.INFO)


def main():
    multiprocessing.freeze_support()
    _configure_logging()
    app = GalleryDLBeyondApplication(sys.argv)
    sys.exit(app.exec())


if __name__ == "__main__":
    main()
