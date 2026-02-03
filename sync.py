import os
import json
from PIL import Image

# Configuration
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
EVENTS_FILE = os.path.join(DATA_DIR, 'events.json')

IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.webm', '.mkv'}
THUMB_SIZE = (400, 400)

def load_events():
    if not os.path.exists(EVENTS_FILE):
        return {}
    try:
        with open(EVENTS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading events.json: {e}")
        return {}

def save_events(events):
    try:
        with open(EVENTS_FILE, 'w') as f:
            json.dump(events, f, indent=2)
        print("Updated events.json")
    except Exception as e:
        print(f"Error saving events.json: {e}")

def generate_thumbnail(media_path, thumb_path):
    try:
        with Image.open(media_path) as img:
            # Convert to RGB if necessary (e.g. for PNGs with alpha)
            if img.mode in ("RGBA", "P"):
                img = img.convert("RGB")
            
            # Create thumbnail
            img.thumbnail(THUMB_SIZE)
            
            # Save as webp
            img.save(thumb_path, "WEBP", quality=80)
            print(f"Generated thumbnail: {thumb_path}")
            return True
    except Exception as e:
        print(f"Failed to generate thumbnail for {media_path}: {e}")
        return False

def sync_events():
    print(f"Scanning data directory: {DATA_DIR}")
    if not os.path.isdir(DATA_DIR):
        print("Data directory not found!")
        return

    events = load_events()
    existing_folders = set(ev['folder'] for ev in events.values())
    
    # helper map to find event key by folder 
    folder_to_key = {ev['folder']: key for key, ev in events.items()}

    # 1. Discover new event folders
    files_in_data = os.listdir(DATA_DIR)
    
    for item in files_in_data:
        item_path = os.path.join(DATA_DIR, item)
        if os.path.isdir(item_path) and item != "Thumbnail":
            # Check if this folder is already in events
            if item not in existing_folders:
                print(f"Found new event folder: {item}")
                # Create default entry
                event_key = item.lower().replace(" ", "-")
                events[event_key] = {
                    "name": item,
                    "description": "Auto-discovered event",
                    "date": "2025-01-01", # Default date
                    "folder": item,
                    "hidden": True, # Default to hidden so admin can review
                    "password": ""
                }
                existing_folders.add(item)
                folder_to_key[item] = event_key
    
    # 2. Cleanup missing events
    keys_to_remove = []
    for key, ev in events.items():
        folder_path = os.path.join(DATA_DIR, ev['folder'])
        if not os.path.exists(folder_path):
            print(f"Event folder missing: {ev['folder']}. Removing event '{key}'.")
            keys_to_remove.append(key)
    
    for key in keys_to_remove:
        del events[key]

    # Save changes (additions and removals)
    save_events(events)

    # 3. Process Media files (Generate Thumbs & Cleanup Orphans)
    for key, ev in events.items():
        folder_name = ev['folder']
        event_root = os.path.join(DATA_DIR, folder_name)
        media_dir = os.path.join(event_root, 'Media')
        thumb_dir = os.path.join(event_root, 'Thumbnail')
        
        if not os.path.isdir(media_dir):
            continue
            
        # Ensure thumbnail directory exists
        if not os.path.exists(thumb_dir):
            os.makedirs(thumb_dir)
            print(f"Created Thumbnail directory for {folder_name}")

        # Get set of current media base names
        media_files = os.listdir(media_dir)
        valid_media_bases = set()
        for fname in media_files:
            base, ext = os.path.splitext(fname)
            if ext.lower() in IMAGE_EXTS or ext.lower() in VIDEO_EXTS:
                valid_media_bases.add(base)

        # 3a. Generate missing thumbnails
        for fname in media_files:
            base, ext = os.path.splitext(fname)
            if ext.lower() in IMAGE_EXTS:
                media_path = os.path.join(media_dir, fname)
                thumb_fname = base + '.webp'
                thumb_path = os.path.join(thumb_dir, thumb_fname)
                
                if not os.path.exists(thumb_path):
                    print(f"Missing thumbnail for {fname} in {folder_name}...")
                    generate_thumbnail(media_path, thumb_path)
        
        # 3b. Cleanup orphaned thumbnails
        if os.path.isdir(thumb_dir):
            for thumb_fname in os.listdir(thumb_dir):
                base, ext = os.path.splitext(thumb_fname)
                if ext.lower() == '.webp':
                    # Check if this thumbnail corresponds to an existing media file
                    # Note: We assumed thumb name is base + .webp. 
                    # If valid_media_bases contains 'base', keep it.
                    if base not in valid_media_bases:
                        print(f"Removing orphaned thumbnail: {thumb_fname} in {folder_name}")
                        try:
                            os.remove(os.path.join(thumb_dir, thumb_fname))
                        except OSError as e:
                            print(f"Error removing {thumb_fname}: {e}")

    print("Sync complete.")

if __name__ == "__main__":
    sync_events()
