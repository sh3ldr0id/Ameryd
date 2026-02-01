# Ameryd

Ameryd is a minimal, filesystem-based gallery application built with Flask.  
It is designed for hosting and viewing event media with a clean UI, multiple layout modes, and zero database dependency.

## Features

- Minimal, responsive UI
- Dark / light theme toggle
- Multiple view modes  
  - Masonry (mixed orientations)  
  - Grid (square tiles with filenames)  
  - List (thumbnail + metadata)
- Adjustable column density
- Natural filename sorting
- Infinite scrolling
- Optional access-key protection per gallery
- Automatic thumbnail generation

## Tech Stack

- **Backend**: Python, Flask  
- **Image Processing**: Pillow  
- **Frontend**: HTML, CSS, Vanilla JavaScript  
- **UI / Layout**: Bootstrap 5, Masonry.js, ImagesLoaded.js  

No database is used. All content is read directly from the filesystem.

## Requirements

- Python 3.7+
- pip

## Installation

```bash
git clone <repository-url>
cd Ameryd
pip install flask Pillow
```

## Running the App

```bash
python ameryd_app/app.py
```

The app runs on port `5000` by default.  
Update the host or port in `app.py` if needed.

## Project Structure

```
ameryd_app/
├── app.py              # Flask server
├── sync.py             # Media sync utility
├── data/               # Event metadata (gitignored)
├── static/
│   ├── css/style.css   # UI styles
│   ├── js/settings.js  # View modes, sorting, UI logic
│   ├── media/          # Original media files (gitignored)
│   └── thumbnails/     # Generated thumbnails (gitignored)
└── templates/          # HTML templates
```

## Design Philosophy

- Filesystem-first architecture
- No database or ORM
- Simple backend, UI-driven experience
- Fast loading and predictable behavior
- Easy self-hosting

## License

MIT License
