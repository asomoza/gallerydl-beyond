# ![GalleryDL Beyond logo](https://raw.githubusercontent.com/asomoza/gallerydl-beyond/master/resources/logo.jpg) GalleryDL Beyond

GalleryDL Beyond is a graphical user interface (GUI) for gallery-dl, built to provide a dynamic queue system for URLs. This was developed out of a personal need to queue URLs while browsing galleries, as using a text file was not ideal.

![screenshot](https://raw.githubusercontent.com/asomoza/gallerydl-beyond/master/resources/screenshot.png)

## Features

- Dynamic queue system (add URLs while downloads are running)
- Concurrent downloads (configurable worker count)
- Downloads tab: active downloads list + worker-prefixed log output
- History tab: searchable URL list with status, download count, and last error
- Duplicate URL handling: “Check for new files” or “Force full re-download”
- Pause/resume and Stop All controls

## Installation

This project targets Python 3.12+ and uses `uv` for environment management.

```bash
uv sync
```

Alternatively (pip):

```bash
pip install -e .
```

For a more controlled environment, this application requires a configuration file to be located in the same directory as the project or the executable. If no configuration file is found, an example configuration file will be created with the following settings:

- Creates and uses a `downloads` directory for all downloads.
- Creates archive and cache SQLite databases in the `bin` subdirectory.
- Replaces some invalid characters that were causing problems.
- Restricts download speed to 1 MB/s.
- Sets other download and output configurations.

Note: current development targets the modern `src/` application.

## Config management (new `src/` app)

The modern `src/` app uses a `config.json` file for gallery-dl.

- On startup, it ensures `config.json` exists in the current working directory.
- If missing, it copies from `config_example/config.json` when available (otherwise it writes a minimal default).
- Use the **Config** button in the UI to edit common settings:
	- `extractor.base-directory`
	- `extractor.archive`
	- `downloader.rate`
	- `downloader.retries`
	- `downloader.timeout`

## Gallery-dl selection (new `src/` app)

The modern `src/` entrypoint resolves how to run gallery-dl at startup and stores your preference in `QSettings`.

Available modes:

- **Auto (recommended)**: uses system `gallery-dl` if found on `PATH`, otherwise uses the current Python environment (`python -m gallery_dl`).
- **System**: always uses `gallery-dl` from `PATH`.
- **Python env**: uses `python -m gallery_dl` from the current environment.
- **Custom**: use a user-selected executable path.

Open **Settings** in the UI to change the mode.

## History tab actions (new `src/` app)

Right-click any row in **History** for quick actions:

- **Copy URL**: copies the selected URL to your clipboard
- **Check for new files**: re-queues the URL using archive semantics (only downloads new items)
- **Force full re-download**: re-queues the URL and runs gallery-dl with `--no-skip`
- **Remove from history…**: deletes the row after a confirmation prompt (blocked while downloading)

## Troubleshooting

### “gallery-dl not found”

- If you expect a system install: verify `gallery-dl` is on your `PATH` (or use **Settings → Custom** and point to the executable).
- If you’re using the project environment: choose **Settings → Python env** (runs `python -m gallery_dl`).
- If `python -m gallery_dl` fails, install it into the current environment (`uv sync` for this project, or `pip install gallery-dl`).

### Update behavior

- Auto-update is only attempted when using **Python env** mode (updating a system binary/package isn’t safe/portable).
- If updates fail, ensure either `uv` is available or that `pip` is installed in the current environment.

### Wrong gallery-dl being used

- Switch to **System** to force `PATH` usage, or **Custom** to pin a specific executable.

Run the app (new `src/` entrypoint) with:

```bash
uv run python -m gallerydl_beyond
```

## Release build

To create a self-contained application run this command:

### Linux

```bash
pyinstaller --noconfirm --onefile --windowed \
	--add-data "./config_example/config.json:." \
	--paths "./src" \
	--noconsole "./src/run_gallerydl_beyond.py"
```

### Windows

```batch
pyinstaller --noconfirm --onefile --windowed \
	--icon "./resources/256x256.ico" \
	--add-data "./config_example/config.json;." \
	--paths "./src" \
	--noconsole "./src/run_gallerydl_beyond.py"
```

## Acknowledgements

A big thank you to [Mike Fährmann](https://github.com/mikf), the developer of gallery-dl, for his invaluable contribution in creating such a useful tool. Gratitude is also extended to all the contributors who have helped make gallery-dl even better.

## License

This project is licensed under the GNU General Public License v2.0, the same license as gallery-dl. You can find the full text of the license [here](https://github.com/asomoza/gallerydl-beyond/blob/master/LICENSE).
