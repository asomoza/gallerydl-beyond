import os


logging_config = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "console_formatter": {"format": "%(asctime)s - %(name)s - %(levelname)s - %(message)s"},
        "file_formatter": {"format": "%(asctime)s - %(name)s - %(levelname)s - %(filename)s:%(lineno)d - %(message)s"},
    },
    "handlers": {
        "consoleHandler": {
            "class": "logging.StreamHandler",
            "level": "DEBUG",
            "formatter": "console_formatter",
            "stream": "ext://sys.stdout",
        },
        "fileHandler": {
            "class": "logging.FileHandler",
            "level": "ERROR",
            "formatter": "file_formatter",
            "filename": os.path.join(os.path.expanduser("~"), ".gallerydl-beyond", "gallerydl-beyond.log"),
        },
    },
    "loggers": {
        "": {
            "level": "DEBUG",
            "handlers": ["consoleHandler", "fileHandler"],
        },
    },
}
