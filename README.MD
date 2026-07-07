# ![GalleryDL Beyond logo](https://raw.githubusercontent.com/asomoza/gallerydl-beyond/master/resources/logo.jpg) GalleryDL Beyond

GalleryDL Beyond is a graphical user interface (GUI) for gallery-dl, built to provide a dynamic queue system for URLs. This was developed out of a personal need to queue URLs while browsing galleries, as using a text file was not ideal.

![screenshot](https://raw.githubusercontent.com/asomoza/gallerydl-beyond/refs/heads/master/resources/screenshot.png)

## Features

- Dynamic queue system (add URLs while downloads are running)
- Concurrent downloads (1-8 configurable workers, adjustable while running)
- Downloads tab: active downloads list + worker-prefixed log output
- History tab: searchable URL list with color-coded status, download count, tags, and last error; pagination for large databases
- URL tagging: organize URLs with custom tags, filter by tag, assign tags via context menu
- Duplicate URL handling: "Check for new files" or "Force full re-download"
- Pause/resume and Stop All controls
- Resume stopped downloads: stopped downloads are automatically resumed when clicking Start
- Partial completion tracking: detects when some files fail during a download
- Skip URLs: mark URLs to be skipped so they won't be downloaded
- Individual download control: stop or skip specific downloads from the active list
- Auto-start: URLs start downloading immediately if there's available capacity (works for new URLs and history actions)
- Live worker scaling: increase or decrease concurrent downloads on-the-fly without stopping

## Installation

This project targets Python 3.12+ and uses `uv` for environment management.

```bash
uv sync
```

For a more controlled environment, this application requires a configuration file to be located in the same directory as the project or the executable. If no configuration file is found, an example configuration file will be created with the following settings:

- Creates and uses a `downloads` directory for all downloads.
- Creates archive and cache SQLite databases in the `bin` subdirectory.
- Replaces some invalid characters that were causing problems.
- Restricts download speed to 1 MB/s.
- Sets other download and output configurations.


## Config management 

The app uses a `config.json` file for gallery-dl.

- On startup, it ensures `config.json` exists in the current working directory.
- If missing, it copies from `config_example/config.json` when available (otherwise it writes a minimal default).
- Use the **Gallery-dl Options** button in the UI to edit common settings:
	- `extractor.base-directory`
	- `extractor.archive`
	- `downloader.rate`
	- `downloader.retries`
	- `downloader.timeout`

## Gallery-dl options

The app resolves how to run gallery-dl at startup and stores your preference in `QSettings`.

Open **Gallery-dl Options** in the UI to configure:

### Execution mode
- **Auto (recommended)**: uses system `gallery-dl` if found on `PATH`, otherwise uses the current Python environment (`python -m gallery_dl`).
- **System**: always uses `gallery-dl` from `PATH`.
- **Python env**: uses `python -m gallery_dl` from the current environment.
- **Custom**: use a user-selected executable path.

### Configuration
Edit common `config.json` settings (base-directory, archive, rate, retries, timeout).

## History tab actions

Right-click any row in **History** for quick actions:

- **Copy URL**: copies the selected URL to your clipboard
- **Resume download**: (for Stopped/Failed items) re-queues the URL to continue downloading
- **Skip**: marks the URL as skipped so it won't be downloaded
- **Check for new files**: re-queues the URL using archive semantics (only downloads new items)
- **Force full re-download**: re-queues the URL and runs gallery-dl with `--no-skip`
- **Tags**: submenu with checkable tags to assign/remove tags from the URL
- **Remove from history…**: deletes the row after a confirmation prompt (blocked while downloading)

**Note:** Resume, Check for new files, and Force full re-download will auto-start immediately if downloads are running and slots are available.

### Tag Filtering

Use the **Tag** dropdown next to the search box to filter URLs by tag:
- Select "All" to show all URLs
- Select a specific tag to show only URLs with that tag
- Combine with the search box to filter by both tag and URL text

### Pagination

The History tab supports pagination for efficient browsing of large databases:
- Use **<<** / **<** / **>** / **>>** buttons to navigate between pages
- The page indicator shows "Page X of Y (Z items)"
- Use the **Rows** dropdown to change items per page (50, 100, 200, or 500)
- Page size preference is saved and persists across app restarts
- Search and tag filters reset to page 1; other actions preserve the current page

### Sorting

Click any sortable column header to sort the History tab:
- **#** - Row number (sorts by database ID)
- **URL** - Sort alphabetically by URL
- **Status** - Sort by status (Pending → Completed → Failed, etc.)
- **Downloads** - Sort by download count
- **Added** - Sort by date added
- **Processed** - Sort by last processed date

Click again to toggle between ascending and descending order. Sorting resets to page 1.

## Active downloads actions

Right-click any item in the **Active downloads** list for quick actions:

- **Stop this download**: stops the selected download (marks as Stopped, can be resumed later)
- **Skip this download**: stops the selected download and marks it as Skipped

## Live worker scaling

You can adjust the number of concurrent downloads (1-8) while downloads are running:

- **Increasing workers**: New workers immediately start downloading from the queue
- **Decreasing workers**: Excess downloads are stopped and their URLs are put back in the queue (as Pending), so they'll be picked up when a slot becomes available

This allows you to dynamically allocate more or fewer resources without interrupting your download session.

## Download Status Types

The History tab displays the following columns for each URL: #, URL, Status, Downloads, Added, Processed, Last error, and Tags. The status is color-coded:

| Status | Color | Description |
|--------|-------|-------------|
| Pending | Gray | Waiting in queue |
| In progress | Blue | Currently downloading |
| Completed | Green | Successfully finished |
| Failed | Red | Download failed (non-zero exit code) |
| Stopped | Orange | User manually stopped the download |
| Partial | Yellow | Completed but some files failed to download |
| Skipped | Purple | User marked URL to be skipped |

**Note:** Stopped downloads are automatically resumed when you click the Start button, along with any pending downloads. Skipped URLs will not be downloaded until manually re-queued.

## Graceful Shutdown

When you close the app while downloads are running:
- All active downloads are stopped gracefully
- They are marked as "Stopped" so they can be resumed on next launch
- If the app crashes or is force-killed, any interrupted downloads are automatically reset to "Stopped" on next startup

## Database Manager

Click **Manage Database** in the UI to access database management features:

### Statistics
- Total URLs and counts by status (completed, failed, pending, stopped, skipped, partial)
- Total successful downloads
- Database and archive file sizes
- Date range of entries

### Bulk Operations
- **Clear by status**: Remove all completed, failed, stopped, or partial URLs
- **Retry all failed**: Reset failed URLs to pending for another attempt
- **Clear all**: Remove entire history (with confirmation)

### Import / Export
- **Export URLs**: Save all URLs to a text file
- **Import URLs**: Load URLs from a text file (one per line, supports `#` comments)

### Tag Management
Create and manage tags to organize your URLs:

- **Add Tag**: Create a new tag with a unique name
- **Rename**: Change an existing tag's name
- **Delete**: Remove a tag (also removes it from all URLs)

Tags are assigned to URLs via the History tab's right-click context menu.

### Gallery-dl Archive Import
Import data from external gallery-dl archive databases (`.sqlite3` files):

- **Merge Archive**: Copy download records from another archive into the current one. This preserves gallery-dl's tracking of what was already downloaded, preventing re-downloads when migrating between machines or combining archives.

- **Extract URLs from Archive**: Attempt to reconstruct gallery URLs from archive entries and add them to history. Note that URL reconstruction is best-effort:
  - Many sites have simple URL patterns that can be reconstructed
  - Some sites require additional information (tokens, usernames) that isn't stored in the archive, so their URLs cannot be reconstructed
  - The dialog shows which extractors can/cannot have URLs reconstructed before proceeding

### Database Maintenance
- **Vacuum**: Compact the database file to reclaim space
- **Backup**: Create a backup copy of the database
- **Clear Archive**: Delete gallery-dl's archive file (forces full re-check on all URLs)

## Troubleshooting

### “gallery-dl not found”

- If you expect a system install: verify `gallery-dl` is on your `PATH` (or use **Settings → Custom** and point to the executable).
- If you’re using the project environment: choose **Settings → Python env** (runs `python -m gallery_dl`).
- If `python -m gallery_dl` fails, install it into the current environment (`uv sync` for this project, or `pip install gallery-dl`).

### Update behavior

- Auto-update is attempted when gallery-dl is installed in the current Python environment (venv), regardless of how it was detected (Python env mode or found via PATH inside the venv).
- System-wide installations are not auto-updated; instead, a warning is displayed.
- If updates fail, ensure either `uv` is available or that `pip` is installed in the current environment.

### Wrong gallery-dl being used

- Switch to **System** to force `PATH` usage, or **Custom** to pin a specific executable.

Run the app (new `src/` entrypoint) with:

```bash
uv run python -m gallerydl_beyond
```

## Development

### Running Tests

Install dev dependencies and run the test suite:

```bash
uv sync --extra dev
uv run pytest
```

The test suite covers:
- Database operations and migrations
- Tag CRUD and URL-tag associations
- Config file handling
- Gallery-dl detection and resolution
- Download command building
- Archive import and URL reconstruction

## Release build

To create a self-contained executable:

### Install build dependencies

```bash
uv sync --extra build
```

### Linux

```bash
uv run pyinstaller --noconfirm --onefile --windowed \
	--add-data "./config_example/config.json:." \
	--paths "./src" \
	--noconsole "./src/run_gallerydl_beyond.py"
```

### Windows

```batch
uv run pyinstaller --noconfirm --onefile --windowed \
	--icon "./resources/256x256.ico" \
	--add-data "./config_example/config.json;." \
	--paths "./src" \
	--noconsole "./src/run_gallerydl_beyond.py"
```

The executable will be created in `dist/`.

### Frozen executable limitations

When running as a packaged executable:

- **Python env mode is unavailable**: The app cannot use `python -m gallery_dl` since the bundled executable is not a Python interpreter
- **Auto-update is disabled**: gallery-dl cannot be updated from within the frozen app
- **gallery-dl must be installed separately**: Use system-installed `gallery-dl` (on PATH) or specify a custom executable path in Settings

### Required files for building

| Directory | Required | Purpose |
|-----------|----------|---------|
| `config_example/` | Yes | Bundled as config template |
| `resources/` | Windows only | Contains application icon |
| `bin/` | No | Runtime data (created at execution) |

## Acknowledgements

A big thank you to [Mike Fährmann](https://github.com/mikf), the developer of gallery-dl, for his invaluable contribution in creating such a useful tool. Gratitude is also extended to all the contributors who have helped make gallery-dl even better.

## License

This project is licensed under the GNU General Public License v2.0, the same license as gallery-dl. You can find the full text of the license [here](https://github.com/asomoza/gallerydl-beyond/blob/master/LICENSE).
