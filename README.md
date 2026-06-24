# News Ticker

A Windows-first desktop news ticker built with PySide6. The app renders a thin always-on-top ticker bar along the top or bottom of the screen, refreshes RSS and Atom feeds, and exposes quick controls through a system tray icon.

## Features

- Frameless ticker bar anchored to the top or bottom of the primary display
- Custom-painted marquee with pause-on-hover and clickable headlines
- RSS and Atom feed support with normalized headline deduplication
- JSON-backed settings for appearance, behavior, and feed management
- System tray controls for show/hide, pause, refresh, settings, and exit
- Optional Windows startup registration

## Install

```bash
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

## Run

```bash
python main.py
```

## Project Layout

```text
main.py
src/
  app/
  feeds/
  services/
  ui/
  utils/
data/
assets/
```
