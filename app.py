from flask import Flask, render_template, request, redirect, url_for, abort, send_from_directory, jsonify
import os, json

app = Flask(__name__)

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
EVENTS_FILE = os.path.join(DATA_DIR, 'events.json')
GLOBAL_THUMB_DIR = os.path.join(DATA_DIR, 'Thumbnail')

# Allowed file extensions
IMAGE_EXTS = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
VIDEO_EXTS = {'.mp4', '.mov', '.avi', '.webm', '.mkv'}

def load_events():
    try:
        with open(EVENTS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading events.json: {e}")
        return {}

def get_event_media_list(ev):
    event_folder = os.path.join(DATA_DIR, ev['folder'])
    media_dir = os.path.join(event_folder, 'Media')
    thumb_dir = os.path.join(event_folder, 'Thumbnail')
    
    media_list = []
    if os.path.isdir(media_dir):
        # Sort files to ensure consistent order for pagination
        files = sorted(os.listdir(media_dir))
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in IMAGE_EXTS or ext in VIDEO_EXTS:
                # Determine thumbnail filename
                thumb_fname = os.path.splitext(fname)[0] + '.webp'
                # If thumbnail exists in event's Thumbnail, use it; else decide fallback
                if os.path.exists(os.path.join(thumb_dir, thumb_fname)):
                    thumb_file = thumb_fname
                    thumb_url_fn = 'thumb_file'   # route function for event thumbnails
                else:
                    # Use global fallback
                    thumb_file = 'image.webp' if ext in IMAGE_EXTS else 'video.webp'
                    thumb_url_fn = 'global_thumb'  # route for global thumbs
                media_list.append({
                    'filename': fname,
                    'thumb_filename': thumb_file,
                    'thumb_route': thumb_url_fn
                })
    return media_list

@app.route('/')
def root():
    return redirect(url_for('list_events'))

@app.route('/e')
def list_events():
    events = load_events()
    return render_template('index.html', events=events)

@app.route('/e/<event_path>')
def event_page(event_path):
    events = load_events()
    ev = events.get(event_path)
    if not ev:
        abort(404, description="Event not found")
    
    # Check password
    key = request.args.get('key', default='', type=str)
    is_locked = bool(ev.get('password'))
    unlocked = (not is_locked) or (key == ev.get('password'))
    
    if is_locked and not unlocked:
        # Show password form
        return render_template('event.html', event=ev, event_path=event_path, locked=True)
    
    # Unlocked: gather media list
    all_media = get_event_media_list(ev)
    
    # Pagination: Load first chunk (e.g., 20)
    PAGE_SIZE = 20
    media_list = all_media[:PAGE_SIZE]
    
    # Render gallery
    return render_template('event.html', event=ev, event_path=event_path,
                           locked=False, media_list=media_list, key=key)

@app.route('/api/e/<event_path>')
def event_api(event_path):
    events = load_events()
    ev = events.get(event_path)
    if not ev: return jsonify({'error': 'Event not found'}), 404
    
    # Check password
    key = request.args.get('key', default='', type=str)
    if ev.get('password') and key != ev['password']:
         return jsonify({'error': 'Unauthorized'}), 401

    all_media = get_event_media_list(ev)
    
    # Pagination
    page = request.args.get('page', default=1, type=int)
    PAGE_SIZE = 20
    
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    
    chunk = all_media[start:end]
    has_more = end < len(all_media)
    
    return jsonify({
        'media': chunk,
        'has_more': has_more,
        'next_page': page + 1 if has_more else None
    })

@app.route('/e/<event_path>/m/<filename>')
def media_file(event_path, filename):
    events = load_events()
    ev = events.get(event_path)
    if not ev: abort(404)
    key = request.args.get('key', '')
    if ev.get('password') and key != ev['password']:
        abort(403)
    # Safe send
    media_dir = os.path.join(DATA_DIR, ev['folder'], 'Media')
    if not os.path.isdir(media_dir):
        abort(404)
    return send_from_directory(media_dir, filename)

@app.route('/e/<event_path>/t/<filename>')
def thumb_file(event_path, filename):
    # Thumbnails for an event
    events = load_events()
    ev = events.get(event_path)
    if not ev: abort(404)
    key = request.args.get('key', '')
    if ev.get('password') and key != ev['password']:
        abort(403)
    thumb_dir = os.path.join(DATA_DIR, ev['folder'], 'Thumbnail')
    if os.path.isdir(thumb_dir) and os.path.exists(os.path.join(thumb_dir, filename)):
        return send_from_directory(thumb_dir, filename)
    # Fallback: not found in event thumb dir, use global thumbs
    return global_thumb(filename)

@app.route('/e/<event_path>/thumbnail')
def event_thumb(event_path):
    events = load_events()
    ev = events.get(event_path)
    if not ev: abort(404)
    # Check if custom thumbnail exists in event root
    event_folder = os.path.join(DATA_DIR, ev['folder'])
    if os.path.exists(os.path.join(event_folder, 'thumbnail.webp')):
        return send_from_directory(event_folder, 'thumbnail.webp')
    return global_thumb('event.webp')

@app.route('/thumbs/<filename>')
def global_thumb(filename):
    # Serve global fallback thumbnails (no auth needed)
    return send_from_directory(GLOBAL_THUMB_DIR, filename)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 2021))
    app.run(debug=True, host='0.0.0.0', port=port)
