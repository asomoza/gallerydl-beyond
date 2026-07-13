# Changelog

## 0.1.0 - 2026-07-13

- new `src/` entrypoint improvements (startup checks + logging)
- gallery-dl selection UI (Auto/System/Python/Custom)
- config editor UI for common `config.json` fields
- tabbed UI (Downloads + History)
- concurrent downloads via a worker pool (pause/resume/stop-all)
- History tab: search + context menu actions (copy URL, check new, force re-download, remove with confirmation)
- duplicate URL dialog with re-queue behavior (check new / force)
- new status types: Stopped (user manually stopped), Partial (completed with some file failures), Skipped (user chose to skip)
- color-coded status display in History tab
- Resume download context menu action for Stopped/Failed items
- Start button now automatically resumes stopped downloads along with pending ones
- partial completion detection: tracks when gallery-dl reports file download errors
- Skip functionality: mark URLs to be skipped from History tab or while downloading
- individual download control: stop or skip specific downloads from Active downloads context menu
- auto-start: URLs start downloading immediately when slots are available (new URLs and history actions like resume/check new/force re-download)
- graceful shutdown: closing the app stops downloads and marks them as Stopped for later resumption
- startup recovery: interrupted downloads (from crash or force-close) are automatically reset to Stopped
- Database Manager dialog with statistics, bulk operations, and maintenance tools
- import/export URLs to text files
- gallery-dl archive import: merge archives and extract gallery URLs from external archive databases
- improved auto-update detection: now works for gallery-dl installed in the current venv (not just Python env mode)
- live worker scaling: adjust concurrent downloads (1-8) while running; reducing workers requeues excess downloads
- fix: "Stop this download" now works correctly (stopped downloads no longer immediately restart)
- fix: archive URL extraction dialog now uses a scrollable list for large archives with many extractors
- History tab pagination: navigate large databases efficiently with First/Prev/Next/Last buttons, page indicator, and configurable rows per page (50/100/200/500)
- History tab row numbers: "#" column shows absolute position in the filtered/sorted results
- History tab sorting: click column headers to sort by URL, Status, Downloads, Added, or Processed date (ascending/descending)
- page size preference persists across app restarts
- database performance: added indexes on date_processed, date_added, and url columns
- fix: PyInstaller builds no longer spawn infinite app instances (added frozen executable detection)

## 0.0.1 - 2023-06-29

- initial release
