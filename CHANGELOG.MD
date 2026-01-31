# Changelog

## 0.0.2 - Unreleased

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

## 0.0.1 - 2023-06-29

- initial release
