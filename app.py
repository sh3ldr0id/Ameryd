from flask import Flask, render_template, request, redirect, url_for, abort, send_from_directory, jsonify, session
import os, json, secrets
from functools import wraps
from werkzeug.utils import secure_filename
from utils import generate_thumb_for_any, IMAGE_EXTS, VIDEO_EXTS

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
EVENTS_FILE = os.path.join(DATA_DIR, 'events.json')
GLOBAL_THUMB_DIR = os.path.join(DATA_DIR, 'Thumbnail')

# Auth Configuration
# os.environ["ADMIN_PASSWORD"] = "admin"
ADMIN_PASSWORD = os.environ.get('ADMIN_PASSWORD')

import hashlib

def get_admin_auth_state():
    return ADMIN_PASSWORD

def get_admin_pass_hash(password):
    return hashlib.sha256(password.encode()).hexdigest()

@app.before_request
def check_auth_sync():
    if session.get('is_admin'):
        current_pass = get_admin_auth_state()
        if not current_pass or session.get('admin_pass_hash') != get_admin_pass_hash(current_pass):
            session.clear()

def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

def load_events():
    try:
        with open(EVENTS_FILE, 'r') as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading events.json: {e}")
        return {}

def save_events(events_dict):
    """Save events dictionary to events.json file"""
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(EVENTS_FILE, 'w') as f:
            json.dump(events_dict, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving events.json: {e}")
        return False

def slugify(text):
    """Convert text to URL-friendly slug"""
    import re
    text = text.lower().strip()
    text = re.sub(r'[^\w\s-]', '', text)
    text = re.sub(r'[\s_-]+', '-', text)
    text = re.sub(r'^-+|-+$', '', text)
    return text


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
                thumb_fname = fname + '.webp'
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
    events_dict = load_events()
    
    # Sort events by date descending (newest first)
    # Date format is assume DD-MM-YYYY
    def parse_date(date_str):
        try:
            from datetime import datetime
            return datetime.strptime(date_str, '%d-%m-%Y')
        except:
            return None

    # Convert to list of tuples for sorting: [(path, data), ...]
    events_list = []
    is_admin = session.get('is_admin')
    for path, data in events_dict.items():
        if not data.get('hidden') or is_admin:
            events_list.append((path, data))
            
    events_list.sort(key=lambda x: parse_date(x[1].get('date', '')), reverse=True)
    
    return render_template('index.html', events=events_list)

@app.route('/authenticate', methods=['GET', 'POST'])
def login():
    if not ADMIN_PASSWORD:
        return "Admin password not set in environment.", 500
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['is_admin'] = True
            session['admin_pass_hash'] = get_admin_pass_hash(ADMIN_PASSWORD)
            return redirect(url_for('list_events'))
        return render_template('authenticate.html', error="Invalid password")
    return render_template('authenticate.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('list_events'))

@app.route('/events/create')
@admin_required
def create_event_page():
    return render_template('event_form.html', event=None, event_path=None)

@app.route('/events/<event_path>/edit')
@admin_required
def edit_event_page(event_path):
    events = load_events()
    ev = events.get(event_path)
    if not ev:
        abort(404, description="Event not found")
    return render_template('event_form.html', event=ev, event_path=event_path)

@app.route('/e/<event_path>')
def event_page(event_path):
    events = load_events()
    ev = events.get(event_path)
    if not ev:
        abort(404, description="Event not found")
    
    key = request.args.get('key', default='', type=str)
    is_locked = bool(ev.get('password'))
    unlocked = (not is_locked) or (key == ev.get('password')) or session.get('is_admin')
    
    if is_locked and not unlocked:
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
    
    key = request.args.get('key', default='', type=str)
    if ev.get('password') and key != ev['password'] and not session.get('is_admin'):
         return jsonify({'error': 'Unauthorized'}), 401

    all_media = get_event_media_list(ev)
    
    # Pagination
    page = request.args.get('page', default=1, type=int)
    PAGE_SIZE = 20
    
    start = (page - 1) * PAGE_SIZE
    end = start + PAGE_SIZE
    
    chunk = all_media[start:end]
    has_more = end < len(all_media)
    
    return jsonify({'media': chunk, 'has_more': has_more, 'next_page': page + 1 if has_more else None})

@app.route('/e/<event_path>/u')
@admin_required
def upload_page(event_path):
    events = load_events()
    ev = events.get(event_path)
    if not ev: abort(404)
    return render_template('upload.html', event=ev, event_path=event_path)

@app.route('/api/e/<event_path>/upload', methods=['POST'])
def api_upload(event_path):
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    events = load_events()
    ev = events.get(event_path)
    if not ev: return jsonify({'error': 'Event not found'}), 404
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    filename = secure_filename(file.filename)
    event_folder = os.path.join(DATA_DIR, ev['folder'])
    media_dir = os.path.join(event_folder, 'Media')
    thumb_dir = os.path.join(event_folder, 'Thumbnail')
    
    os.makedirs(media_dir, exist_ok=True)
    os.makedirs(thumb_dir, exist_ok=True)
    
    media_path = os.path.join(media_dir, filename)
    file_ext = os.path.splitext(filename)[1].lower()
    
    # Save original file directly to preserve quality (no re-compression)
    file.save(media_path)
    
    thumb_fname = filename + '.webp'
    thumb_path = os.path.join(thumb_dir, thumb_fname)
    generate_thumb_for_any(media_path, thumb_path)
    
    thumb_url = url_for('thumb_file', event_path=event_path, filename=thumb_fname)
    return jsonify({'success': True, 'filename': filename, 'thumb_url': thumb_url})

@app.route('/api/e/<event_path>/delete', methods=['POST'])
def api_delete(event_path):
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
        
    events = load_events()
    ev = events.get(event_path)
    if not ev: return jsonify({'error': 'Event not found'}), 404
    
    filename = request.form.get('filename')
    if not filename: return jsonify({'error': 'No filename provided'}), 400
    
    filename = secure_filename(filename)
    event_folder = os.path.join(DATA_DIR, ev['folder'])
    media_dir = os.path.join(event_folder, 'Media')
    thumb_dir = os.path.join(event_folder, 'Thumbnail')
    
    media_path = os.path.join(media_dir, filename)
    thumb_path = os.path.join(thumb_dir, filename + '.webp')
    
    if os.path.exists(media_path): os.remove(media_path)
    if os.path.exists(thumb_path): os.remove(thumb_path)
    
    return jsonify({'success': True})

@app.route('/api/events/create', methods=['POST'])
def api_create_event():
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    # Get form data
    name = request.form.get('name', '').strip()
    date = request.form.get('date', '').strip()
    description = request.form.get('description', '').strip()
    password = request.form.get('password', '').strip()
    folder = request.form.get('folder', '').strip()
    
    # Validate required fields
    if not name:
        return jsonify({'error': 'Event name is required'}), 400
    if not date:
        return jsonify({'error': 'Event date is required'}), 400
    if not description:
        return jsonify({'error': 'Event description is required'}), 400
    
    # Generate event path (URL slug)
    custom_id = request.form.get('event_id', '').strip()
    if custom_id:
        event_path = slugify(custom_id)
    else:
        event_path = slugify(name)

    if not event_path:
        return jsonify({'error': 'Invalid event name or ID'}), 400
    
    # Generate folder name if not provided
    if not folder:
        folder = event_path
    else:
        folder = secure_filename(folder)
    
    # Check if event already exists
    events = load_events()
    if event_path in events:
        return jsonify({'error': f'Event "{event_path}" already exists'}), 400
    
    # Create folder structure
    event_folder = os.path.join(DATA_DIR, folder)
    media_dir = os.path.join(event_folder, 'Media')
    thumb_dir = os.path.join(event_folder, 'Thumbnail')
    
    try:
        os.makedirs(media_dir, exist_ok=True)
        os.makedirs(thumb_dir, exist_ok=True)
    except Exception as e:
        return jsonify({'error': f'Failed to create folders: {str(e)}'}), 500
    
    # Add event to events dictionary
    events[event_path] = {
        'name': name,
        'date': date,
        'description': description,
        'folder': folder,
        'hidden': request.form.get('hidden') == 'on'
    }
    
    # Add password if provided
    if password:
        events[event_path]['password'] = password
    
    # Save events.json
    if not save_events(events):
        return jsonify({'error': 'Failed to save events'}), 500
    
    # Handle optional thumbnail upload
    if 'thumbnail' in request.files:
        thumb_file = request.files['thumbnail']
        if thumb_file and thumb_file.filename != '':
            thumb_ext = os.path.splitext(thumb_file.filename)[1].lower()
            if thumb_ext in IMAGE_EXTS:
                # Save as thumbnail.webp in event root
                final_thumb_path = os.path.join(event_folder, 'thumbnail.webp')
                
                # Save temporarily to process
                temp_path = os.path.join(event_folder, 'temp_thumb' + thumb_ext)
                thumb_file.save(temp_path)
                
                # Use generate_thumbnail to resize and convert to WebP
                from utils import generate_thumbnail
                generate_thumbnail(temp_path, final_thumb_path)
                
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
    
    return jsonify({'success': True, 'event_path': event_path})

@app.route('/api/events/<event_path>/update', methods=['POST'])
def api_update_event(event_path):
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    events = load_events()
    if event_path not in events:
        return jsonify({'error': 'Event not found'}), 404
    
    # Get form data
    name = request.form.get('name', '').strip()
    date = request.form.get('date', '').strip()
    description = request.form.get('description', '').strip()
    password = request.form.get('password', '').strip()
    
    # Validate required fields
    if not name:
        return jsonify({'error': 'Event name is required'}), 400
    if not date:
        return jsonify({'error': 'Event date is required'}), 400
    if not description:
        return jsonify({'error': 'Event description is required'}), 400
    
    # Update event data
    events[event_path]['name'] = name
    events[event_path]['date'] = date
    events[event_path]['description'] = description
    events[event_path]['hidden'] = request.form.get('hidden') == 'on'
    
    # Update or remove password
    if password:
        events[event_path]['password'] = password
    elif 'password' in events[event_path]:
        del events[event_path]['password']
    
    # Save events.json
    if not save_events(events):
        return jsonify({'error': 'Failed to save events'}), 500
    
    # Handle optional thumbnail upload
    if 'thumbnail' in request.files:
        thumb_file = request.files['thumbnail']
        if thumb_file and thumb_file.filename != '':
            thumb_ext = os.path.splitext(thumb_file.filename)[1].lower()
            if thumb_ext in IMAGE_EXTS:
                ev = events[event_path]
                event_folder = os.path.join(DATA_DIR, ev['folder'])
                final_thumb_path = os.path.join(event_folder, 'thumbnail.webp')
                
                # Save temporarily to process
                temp_path = os.path.join(event_folder, 'temp_thumb' + thumb_ext)
                thumb_file.save(temp_path)
                
                # Use generate_thumbnail to resize and convert to WebP
                from utils import generate_thumbnail
                generate_thumbnail(temp_path, final_thumb_path)
                
                # Clean up temp file
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
    return jsonify({'success': True})

@app.route('/api/events/<event_path>/delete', methods=['POST'])
def api_delete_event(event_path):
    if not session.get('is_admin'):
        return jsonify({'error': 'Unauthorized'}), 401
    
    events = load_events()
    if event_path not in events:
        return jsonify({'error': 'Event not found'}), 404
    
    ev = events[event_path]
    event_folder = os.path.join(DATA_DIR, ev['folder'])
    
    # Delete folder and all contents
    import shutil
    try:
        if os.path.exists(event_folder):
            shutil.rmtree(event_folder)
    except Exception as e:
        return jsonify({'error': f'Failed to delete folder: {str(e)}'}), 500
    
    # Remove from events dictionary
    del events[event_path]
    
    # Save events.json
    if not save_events(events):
        return jsonify({'error': 'Failed to save events'}), 500
    
    return jsonify({'success': True})


def add_cache_headers(response, max_age=31536000):
    response.headers['Cache-Control'] = f'public, max-age={max_age}, immutable'
    return response

@app.route('/e/<event_path>/m/<filename>')
def media_file(event_path, filename):
    events = load_events()
    ev = events.get(event_path)
    if not ev: abort(404)
    key = request.args.get('key', '')
    if ev.get('password') and key != ev['password'] and not session.get('is_admin'):
        abort(403)
    # Safe send
    media_dir = os.path.join(DATA_DIR, ev['folder'], 'Media')
    if not os.path.isdir(media_dir):
        abort(404)
    response = send_from_directory(media_dir, filename)
    # Cache media for a bit shorter than thumbs, or same if immutable
    return add_cache_headers(response, max_age=86400) # 1 day for full media

@app.route('/e/<event_path>/t/<filename>')
def thumb_file(event_path, filename):
    # Thumbnails for an event
    events = load_events()
    ev = events.get(event_path)
    if not ev: abort(404)
    key = request.args.get('key', '')
    if ev.get('password') and key != ev['password'] and not session.get('is_admin'):
        abort(403)
    thumb_dir = os.path.join(DATA_DIR, ev['folder'], 'Thumbnail')
    if os.path.isdir(thumb_dir) and os.path.exists(os.path.join(thumb_dir, filename)):
        response = send_from_directory(thumb_dir, filename)
        return add_cache_headers(response)
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
        response = send_from_directory(event_folder, 'thumbnail.webp')
        return add_cache_headers(response)
    return global_thumb('event.webp')

@app.route('/thumbs/<filename>')
def global_thumb(filename):
    # Serve global fallback thumbnails (no auth needed)
    response = send_from_directory(GLOBAL_THUMB_DIR, filename)
    return add_cache_headers(response)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 2021))
    app.run(debug=True, host='0.0.0.0', port=port)
