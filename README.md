# Ameryd

Ameryd is a self-hosted, filesystem-based media gallery application built with Flask. It is designed for organizing and sharing event photos and videos through a clean, lightweight web interface — with no database required.

Content is structured around **Organizations** and **Events**. Visitors access galleries using short numeric IDs, and administrators manage everything through a secure admin panel.

---

## Features

### Gallery & Viewing
- Multiple view modes: **Masonry**, **Grid**, and **List**
- Adjustable column density
- Infinite scroll with lazy-loaded pagination (30 items per page)
- Dark / light theme toggle
- Support for both images and videos (with auto-generated thumbnails)
- Natural filename sorting

### Organization Hierarchy
- Content is grouped under **Organizations** (4-digit ID) containing **Events** (6-digit ID)
- Short numeric IDs are used for quick, shareable access
- ID resolver on the homepage routes to the correct org or event automatically

### Access Control
- Optional password protection per **Organization**
- Optional password protection per **Event** (via URL key parameter)
- Separate admin authentication with session-based login
- Admin session is invalidated automatically if the password changes

### Admin Panel
- Create, edit, and delete Organizations and Events
- Upload media directly to events through the web interface
- Delete individual media files
- Mark events as hidden (invisible to non-admin visitors)
- Set or clear passwords for orgs and events
- Upload custom thumbnails per event (stored as WebP at 95% quality)

### Media Processing
- Automatic thumbnail generation on upload (WebP format)
- Video thumbnail extraction from the first second of the clip using OpenCV
- EXIF-aware image orientation correction via Pillow
- Dimension metadata cached per-event to avoid repeated I/O
- Aggressively cached static media responses (`Cache-Control: immutable`)

### Deployment
- Docker and Docker Compose support
- Data directory is volume-mounted — media persists independently of the container
- Configurable via environment variables

---

## Tech Stack

| Layer | Technology |
|---|---|
| Backend | Python 3.11, Flask |
| Image Processing | Pillow |
| Video Processing | OpenCV (`opencv-python-headless`) |
| Frontend | HTML, CSS, Vanilla JavaScript |
| UI / Layout | Bootstrap 5, Masonry.js, ImagesLoaded.js |
| Deployment | Docker, Docker Compose |

No database or ORM is used. All state is stored in a single `events.json` file and the filesystem.

---

## URL Structure

| Path | Description |
|---|---|
| `/` | Homepage — ID resolver input |
| `/<org_id>` | Organization page listing all its events |
| `/<event_id>` | Event gallery page |
| `/<event_id>?key=<password>` | Unlocked event gallery (password via query param) |
| `/events/create` | Admin: create a new event |
| `/events/<event_id>/edit` | Admin: edit an event |
| `/<org_id>/edit` | Admin: edit an organization |
| `/<event_id>/u` | Admin: upload media to an event |
| `/authenticate` | Admin login page |

---

## Getting Started

### Prerequisites

- Python 3.9+
- pip

### Local Setup

```bash
git clone <repository-url>
cd Ameryd
pip install -r requirements.txt
python app.py
```

The application runs on port `2021` by default.  
Set the `PORT` environment variable to change it.

### Environment Variables

| Variable | Default | Description |
|---|---|---|
| `PORT` | `2021` | Port the server listens on |
| `ADMIN_PASSWORD` | `admin` | Admin login password |
| `SECRET_KEY` | *(random)* | Flask session secret key |

> **Note:** Always set a strong `ADMIN_PASSWORD` and `SECRET_KEY` in production.

---

## Docker Deployment

A `Dockerfile` and `docker-compose.yml` are included for containerized deployment.

```bash
docker compose up -d
```

The default compose file mounts a host directory as the data volume. Edit `docker-compose.yml` to point the volume to your media storage location:

```yaml
volumes:
  - /your/media/path:/app/data
```

---

## Project Structure

```
Ameryd/
├── app.py                  # Flask application — routes, auth, API endpoints
├── sync.py                 # CLI utility: sync filesystem to events.json
├── utils.py                # Thumbnail generation and media dimension helpers
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── data/                   # Runtime data (gitignored)
│   ├── events.json         # Organization and event registry
│   ├── Thumbnail/          # Global fallback thumbnails
│   └── <event_id>/         # Per-event folders
│       ├── Media/          # Original media files
│       ├── Thumbnail/      # Per-file WebP thumbnails
│       ├── thumbnail.webp  # Event cover image
│       └── metadata.json   # Cached image dimensions
└── templates/
    ├── base.html
    ├── index.html          # Homepage / ID resolver
    ├── org_page.html       # Organization event listing
    ├── org_form.html       # Admin: create/edit organization
    ├── org_auth.html       # Organization password prompt
    ├── event.html          # Event gallery viewer
    ├── event_form.html     # Admin: create/edit event
    ├── upload.html         # Admin: media uploader
    └── authenticate.html   # Admin login
```

---

## Sync Utility

`sync.py` is a standalone CLI tool for syncing the filesystem with `events.json`. It is useful when media has been added or removed directly on disk outside of the web interface.

```bash
python sync.py
```

It will:
1. Discover new event folders and register them as hidden events
2. Remove registry entries for folders that no longer exist
3. Generate missing thumbnails for all media files
4. Clean up orphaned thumbnails with no matching media

---

## Design Philosophy

- **Filesystem-first** — content lives on disk, not in a database
- **No ORM or query layer** — a single JSON file tracks all metadata
- **ID-based access** — short numeric codes replace slugs or long URLs
- **Hierarchical structure** — organizations group related events cleanly
- **Easy self-hosting** — minimal dependencies, Docker-ready

---

## License

MIT License
