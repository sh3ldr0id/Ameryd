from flask import Flask, render_template, request, redirect, url_for, abort, send_from_directory, jsonify, session
import os, json, secrets
from functools import wraps
from werkzeug.utils import secure_filename
from werkzeug.routing import BaseConverter
from utils import generate_thumb_for_any, IMAGE_EXTS, VIDEO_EXTS

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', secrets.token_hex(32))

# ── Custom URL Converters ─────────────────────────────────────────────────────
# These let Flask natively differentiate 4-digit org IDs from 6-digit event IDs
# at the routing level, so url_for() works correctly for both.

class OrgIDConverter(BaseConverter):
    """Matches exactly 4 numeric digits (organization ID)."""
    regex = r'\d{4}'

class EventIDConverter(BaseConverter):
    """Matches exactly 6 numeric digits (event ID)."""
    regex = r'\d{6}'

app.url_map.converters['org_id'] = OrgIDConverter
app.url_map.converters['event_id'] = EventIDConverter

# Paths
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(BASE_DIR, 'data')
EVENTS_FILE = os.path.join(DATA_DIR, 'events.json')
GLOBAL_THUMB_DIR = os.path.join(DATA_DIR, 'Thumbnail')
MEDIA_PAGE_SIZE = 30

# Auth Configuration
os.environ["ADMIN_PASSWORD"] = "test"

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

def admin_required_api(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('is_admin'):
            return jsonify({'error': 'Unauthorized'}), 401
        return f(*args, **kwargs)
    return decorated_function

def get_event_dirs(ev):
    event_folder = os.path.join(DATA_DIR, ev.get('folder', ''))
    media_dir = os.path.join(event_folder, 'Media')
    thumb_dir = os.path.join(event_folder, 'Thumbnail')
    return event_folder, media_dir, thumb_dir

def generate_unique_id(length, existing_ids):
    import random, string
    new_id = ''.join(random.choices(string.digits, k=length))
    while new_id in existing_ids:
        new_id = ''.join(random.choices(string.digits, k=length))
    return new_id

def migrate_events_if_needed(data):
    if not data:
        return {"organizations": {}, "events": {}}
    
    if "organizations" not in data: data["organizations"] = {}
    if "events" not in data: data["events"] = {}
    
    dirty = False
    
    # 1. Migrate 6-digit Org IDs to 4-digit
    old_org_ids = [oid for oid in data["organizations"].keys() if len(oid) == 6]
    if old_org_ids:
        new_orgs = {}
        org_map = {}
        for old_id in old_org_ids:
            new_id = generate_unique_id(4, list(data["organizations"].keys()) + list(new_orgs.keys()))
            org_map[old_id] = new_id
            new_orgs[new_id] = data["organizations"][old_id]
            dirty = True
        
        for old_id, new_id in org_map.items():
            del data["organizations"][old_id]
            data["organizations"][new_id] = new_orgs[new_id]
            
        for eid, edata in data["events"].items():
            if edata.get("org_id") in org_map:
                edata["org_id"] = org_map[edata["org_id"]]
                dirty = True

    # 2. Migrate 4-digit Event IDs to 6-digit
    old_event_ids = [eid for eid in data["events"].keys() if len(eid) == 4]
    if old_event_ids:
        event_map = {}
        for old_id in old_event_ids:
            new_id = generate_unique_id(6, list(data["events"].keys()) + list(event_map.values()))
            event_map[old_id] = new_id
            dirty = True
            
        import shutil
        for old_id, new_id in event_map.items():
            edata = data["events"][old_id]
            old_folder = edata.get("folder")
            
            edata["folder"] = new_id
            data["events"][new_id] = edata
            del data["events"][old_id]
            
            if old_folder:
                old_path = os.path.join(DATA_DIR, old_folder)
                new_path = os.path.join(DATA_DIR, new_id)
                if os.path.exists(old_path) and not os.path.exists(new_path):
                    try:
                        os.rename(old_path, new_path)
                    except Exception as e:
                        print(f"Error renaming folder {old_path} to {new_path}: {e}")

    if dirty:
        print("--- ID Migration Performed ---")
        save_events(data)
        
    return data

def load_events():
    try:
        if not os.path.exists(EVENTS_FILE):
             return migrate_events_if_needed({})
        with open(EVENTS_FILE, 'r') as f:
            data = json.load(f)
            return migrate_events_if_needed(data)
    except Exception as e:
        print(f"Error loading events.json: {e}")
        return migrate_events_if_needed({})

def save_events(events_dict):
    try:
        os.makedirs(DATA_DIR, exist_ok=True)
        with open(EVENTS_FILE, 'w') as f:
            json.dump(events_dict, f, indent=2)
        return True
    except Exception as e:
        print(f"Error saving events.json: {e}")
        return False

def slugify(text):
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
    
    from utils import get_media_dimensions
    
    metadata_file = os.path.join(event_folder, 'metadata.json')
    metadata = {}
    
    if os.path.exists(metadata_file):
        try:
            with open(metadata_file, 'r') as f:
                metadata = json.load(f)
        except:
            metadata = {}
            
    metadata_dirty = False
    
    media_list = []
    if os.path.isdir(media_dir):
        files = sorted(os.listdir(media_dir))
        for fname in files:
            ext = os.path.splitext(fname)[1].lower()
            if ext in IMAGE_EXTS or ext in VIDEO_EXTS:
                thumb_fname = fname + '.webp'
                if os.path.exists(os.path.join(thumb_dir, thumb_fname)):
                    thumb_file = thumb_fname
                    thumb_url_fn = 'thumb_file'
                else:
                    thumb_file = 'image.webp' if ext in IMAGE_EXTS else 'video.webp'
                    thumb_url_fn = 'global_thumb'
                
                dims = metadata.get(fname)
                if not dims:
                    full_media_path = os.path.join(media_dir, fname)
                    w, h = get_media_dimensions(full_media_path)
                    if w and h:
                        dims = [w, h]
                        metadata[fname] = dims
                        metadata_dirty = True
                    else:
                        dims = [800, 600]
                
                media_list.append({
                    'filename': fname,
                    'thumb_filename': thumb_file,
                    'thumb_route': thumb_url_fn,
                    'width': dims[0],
                    'height': dims[1]
                })
        
        if metadata_dirty:
            try:
                with open(metadata_file, 'w') as f:
                    json.dump(metadata, f)
            except:
                pass
                
    return media_list

# ── Core Pages ────────────────────────────────────────────────────────────────

@app.route('/')
def root():
    data = load_events()
    organizations = data.get('organizations', {})
    return render_template('index.html', organizations=organizations)

@app.route('/resolve_id', methods=['POST'])
def resolve_id():
    id_val = request.form.get('id_input', '').strip()
    data = load_events()
    organizations = data.get('organizations', {})
    
    if len(id_val) == 4 and id_val.isdigit():
        return redirect(url_for('org_page', org_id=id_val))
    elif len(id_val) == 6 and id_val.isdigit():
        ev = data.get('events', {}).get(id_val)
        if ev:
            return redirect(url_for('event_page', event_id=id_val))
        return render_template('index.html', error="Event not found", organizations=organizations)
        
    return render_template('index.html', error="Invalid ID (4 digits = Org, 6 digits = Event)", organizations=organizations)

@app.route('/authenticate', methods=['GET', 'POST'])
def login():
    if not ADMIN_PASSWORD:
        return "Admin password not set in environment.", 500
    if request.method == 'POST':
        password = request.form.get('password')
        if password == ADMIN_PASSWORD:
            session['is_admin'] = True
            session['admin_pass_hash'] = get_admin_pass_hash(ADMIN_PASSWORD)
            return redirect(url_for('root'))
        return render_template('authenticate.html', error="Invalid password")
    return render_template('authenticate.html')

@app.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('root'))

# ── Organization Routes ───────────────────────────────────────────────────────

@app.route('/<org_id:org_id>', methods=['GET', 'POST'])
def org_page(org_id):
    data = load_events()
    org = data.get('organizations', {}).get(org_id)
    if not org:
        abort(404, description="Organization not found")
        
    if org.get('password') and not session.get('is_admin'):
        if request.method == 'POST':
            pwd = request.form.get('password')
            if pwd == org.get('password'):
                session[f'org_auth_{org_id}'] = True
            else:
                return render_template('org_auth.html', org_id=org_id, error="Invalid password")
        if not session.get(f'org_auth_{org_id}'):
            return render_template('org_auth.html', org_id=org_id)
            
    is_admin = session.get('is_admin')
    events_list = []
    for e_id, e_data in data.get('events', {}).items():
        if e_data.get('org_id') == org_id:
            if not e_data.get('hidden') or is_admin:
                events_list.append((e_id, e_data))
                
    def parse_date(date_str):
        try:
            from datetime import datetime
            return datetime.strptime(date_str, '%d-%m-%Y')
        except:
            return None

    events_list.sort(key=lambda x: parse_date(x[1].get('date', '')), reverse=True)
    return render_template('org_page.html', org=org, events=events_list, org_id=org_id)

@app.route('/<org_id:org_id>/edit')
@admin_required
def edit_org_page(org_id):
    data = load_events()
    org = data.get('organizations', {}).get(org_id)
    if not org:
        abort(404, description="Organization not found")
    return render_template('org_form.html', org=org, org_id=org_id)

@app.route('/api/organizations/<org_id:org_id>/update', methods=['POST'])
@admin_required_api
def api_update_organization(org_id):
    data = load_events()
    org = data.get('organizations', {}).get(org_id)
    if not org:
        return jsonify({'error': 'Organization not found'}), 404
        
    name = request.form.get('name', '').strip()
    password = request.form.get('password', '').strip()
    description = request.form.get('description', '').strip()
    
    if not name:
        return jsonify({'error': 'Organization name required'}), 400
        
    org['name'] = name
    org['description'] = description
    
    if password:
        org['password'] = password
    elif 'password' in org:
        del org['password']
        
    if not save_events(data):
        return jsonify({'error': 'Failed to save organization'}), 500
        
    return jsonify({'success': True})

@app.route('/api/organizations/<org_id:org_id>/delete', methods=['POST'])
@admin_required_api
def api_delete_organization(org_id):
    data = load_events()
    if org_id not in data.get('organizations', {}):
        return jsonify({'error': 'Organization not found'}), 404
        
    linked_events = [e_id for e_id, e_data in data.get('events', {}).items() if e_data.get('org_id') == org_id]
    if linked_events:
        return jsonify({'error': f'Cannot delete organization: it has {len(linked_events)} linked events. Delete events first.'}), 400
        
    del data['organizations'][org_id]
    if not save_events(data):
        return jsonify({'error': 'Failed to save events'}), 500
        
    return jsonify({'success': True})

# ── Event Routes ──────────────────────────────────────────────────────────────

@app.route('/events/create')
@admin_required
def create_event_page():
    org_id = request.args.get('org_id', '')
    data = load_events()
    orgs = list(data.get('organizations', {}).keys())
    return render_template('event_form.html', event=None, org_id=org_id, orgs=orgs, event_id=None)

@app.route('/events/<event_id:event_id>/edit')
@admin_required
def edit_event_page(event_id):
    data = load_events()
    ev = data.get('events', {}).get(event_id)
    if not ev:
        abort(404, description="Event not found")
    org_id = ev.get('org_id', '')
    orgs = list(data.get('organizations', {}).keys())
    return render_template('event_form.html', event=ev, org_id=org_id, event_id=event_id, orgs=orgs)

@app.route('/<event_id:event_id>')
def event_page(event_id):
    data = load_events()
    ev = data.get('events', {}).get(event_id)
    if not ev:
        abort(404, description="Event not found")
    
    org_id = ev.get('org_id', '')
    key = request.args.get('key', default='', type=str)
    is_locked = bool(ev.get('password'))
    unlocked = (not is_locked) or (key == ev.get('password')) or session.get('is_admin')
    
    if is_locked and not unlocked:
        return render_template('event.html', event=ev, org_id=org_id, event_id=event_id, locked=True)
    
    all_media = get_event_media_list(ev)
    media_list = all_media[:MEDIA_PAGE_SIZE]
    
    return render_template('event.html', event=ev, org_id=org_id, event_id=event_id,
                           locked=False, media_list=media_list, key=key)

# ── Event API ─────────────────────────────────────────────────────────────────

@app.route('/api/<event_id:event_id>')
def event_api(event_id):
    data = load_events()
    ev = data.get('events', {}).get(event_id)
    if not ev:
        return jsonify({'error': 'Event not found'}), 404
    
    key = request.args.get('key', default='', type=str)
    if ev.get('password') and key != ev['password'] and not session.get('is_admin'):
         return jsonify({'error': 'Unauthorized'}), 401

    all_media = get_event_media_list(ev)
    
    page = request.args.get('page', default=1, type=int)
    start = (page - 1) * MEDIA_PAGE_SIZE
    end = start + MEDIA_PAGE_SIZE
    
    chunk = all_media[start:end]
    has_more = end < len(all_media)
    
    return jsonify({
        'media': chunk,
        'has_more': has_more,
        'next_page': page + 1 if has_more else None,
        'total': len(all_media)
    })

@app.route('/<event_id:event_id>/u')
@admin_required
def upload_page(event_id):
    data = load_events()
    ev = data.get('events', {}).get(event_id)
    if not ev:
        abort(404)
    org_id = ev.get('org_id', '')
    return render_template('upload.html', event=ev, org_id=org_id, event_id=event_id)

@app.route('/api/<event_id:event_id>/upload', methods=['POST'])
@admin_required_api
def api_upload(event_id):
    data = load_events()
    ev = data.get('events', {}).get(event_id)
    if not ev:
        return jsonify({'error': 'Event not found'}), 404
    
    if 'file' not in request.files:
        return jsonify({'error': 'No file part'}), 400
    
    file = request.files['file']
    if file.filename == '':
        return jsonify({'error': 'No selected file'}), 400
        
    filename = secure_filename(file.filename)
    event_folder, media_dir, thumb_dir = get_event_dirs(ev)
    
    os.makedirs(media_dir, exist_ok=True)
    os.makedirs(thumb_dir, exist_ok=True)
    
    media_path = os.path.join(media_dir, filename)
    file.save(media_path)
    
    thumb_fname = filename + '.webp'
    thumb_path = os.path.join(thumb_dir, thumb_fname)
    generate_thumb_for_any(media_path, thumb_path)
    
    thumb_url = url_for('thumb_file', event_id=event_id, filename=thumb_fname)
    return jsonify({'success': True, 'filename': filename, 'thumb_url': thumb_url})

@app.route('/api/<event_id:event_id>/delete', methods=['POST'])
@admin_required_api
def api_delete(event_id):
    """Delete a single media file from an event."""
    data = load_events()
    ev = data.get('events', {}).get(event_id)
    if not ev:
        return jsonify({'error': 'Event not found'}), 404
    
    filename = request.form.get('filename')
    if not filename:
        return jsonify({'error': 'No filename provided'}), 400
    
    filename = secure_filename(filename)
    event_folder, media_dir, thumb_dir = get_event_dirs(ev)
    
    media_path = os.path.join(media_dir, filename)
    thumb_path = os.path.join(thumb_dir, filename + '.webp')
    
    if os.path.exists(media_path): os.remove(media_path)
    if os.path.exists(thumb_path): os.remove(thumb_path)
    
    return jsonify({'success': True})

@app.route('/api/events/create', methods=['POST'])
@admin_required_api
def api_create_event():
    name = request.form.get('name', '').strip()
    date = request.form.get('date', '').strip()
    description = request.form.get('description', '').strip()
    password = request.form.get('password', '').strip()
    org_id = request.form.get('org_id', '').strip()
    
    if not name or not date or not description or not org_id:
        return jsonify({'error': 'Missing required fields'}), 400
        
    if 'thumbnail' not in request.files or request.files['thumbnail'].filename == '':
        return jsonify({'error': 'Event thumbnail is required'}), 400
        
    data = load_events()
    if org_id not in data.get('organizations', {}):
        return jsonify({'error': 'Organization not found'}), 400
        
    event_id = generate_unique_id(6, data.get('events', {}).keys())
    folder = event_id
        
    event_folder = os.path.join(DATA_DIR, folder)
    media_dir = os.path.join(event_folder, 'Media')
    thumb_dir = os.path.join(event_folder, 'Thumbnail')
    
    try:
        os.makedirs(media_dir, exist_ok=True)
        os.makedirs(thumb_dir, exist_ok=True)
    except Exception as e:
        return jsonify({'error': f'Failed to create folders: {str(e)}'}), 500
        
    data['events'][event_id] = {
        'org_id': org_id,
        'name': name,
        'date': date,
        'description': description,
        'folder': folder,
        'hidden': request.form.get('hidden') == 'on'
    }
    
    if password:
        data['events'][event_id]['password'] = password
        
    if not save_events(data):
        return jsonify({'error': 'Failed to save event'}), 500
        
    if 'thumbnail' in request.files:
        thumb_file = request.files['thumbnail']
        if thumb_file and thumb_file.filename != '':
            thumb_ext = os.path.splitext(thumb_file.filename)[1].lower()
            if thumb_ext in IMAGE_EXTS:
                final_thumb_path = os.path.join(event_folder, 'thumbnail.webp')
                from utils import generate_thumbnail
                generate_thumbnail(thumb_file, final_thumb_path, quality=95)
                    
    return jsonify({'success': True, 'event_id': event_id})

@app.route('/api/events/<event_id:event_id>/update', methods=['POST'])
@admin_required_api
def api_update_event(event_id):
    data = load_events()
    ev = data.get('events', {}).get(event_id)
    if not ev:
        return jsonify({'error': 'Event not found'}), 404
        
    name = request.form.get('name', '').strip()
    date = request.form.get('date', '').strip()
    description = request.form.get('description', '').strip()
    password = request.form.get('password', '').strip()
    
    if not name or not date or not description:
        return jsonify({'error': 'Missing required fields'}), 400
        
    ev['name'] = name
    ev['date'] = date
    ev['description'] = description
    ev['hidden'] = request.form.get('hidden') == 'on'
    
    if password:
        ev['password'] = password
    elif 'password' in ev:
        del ev['password']
        
    if not save_events(data):
        return jsonify({'error': 'Failed to save event'}), 500
        
    if 'thumbnail' in request.files:
        thumb_file = request.files['thumbnail']
        if thumb_file and thumb_file.filename != '':
            thumb_ext = os.path.splitext(thumb_file.filename)[1].lower()
            if thumb_ext in IMAGE_EXTS:
                event_folder = os.path.join(DATA_DIR, ev['folder'])
                final_thumb_path = os.path.join(event_folder, 'thumbnail.webp')
                temp_path = os.path.join(event_folder, 'temp_thumb' + thumb_ext)
                thumb_file.save(temp_path)
                from utils import generate_thumbnail
                generate_thumbnail(temp_path, final_thumb_path, quality=95)
                if os.path.exists(temp_path):
                    os.remove(temp_path)
                    
    return jsonify({'success': True})

@app.route('/api/events/<event_id:event_id>/delete', methods=['POST'])
@admin_required_api
def api_delete_event(event_id):
    """Delete an entire event and all its media."""
    data = load_events()
    ev = data.get('events', {}).get(event_id)
    if not ev:
         return jsonify({'error': 'Event not found'}), 404
         
    event_folder = os.path.join(DATA_DIR, ev['folder'])
    import shutil
    try:
        if os.path.exists(event_folder):
            shutil.rmtree(event_folder)
    except Exception as e:
        return jsonify({'error': f'Failed to delete folder: {str(e)}'}), 500
        
    del data['events'][event_id]
    if not save_events(data):
        return jsonify({'error': 'Failed to save events'}), 500
        
    return jsonify({'success': True})

@app.route('/api/organizations/create', methods=['POST'])
@admin_required_api
def api_create_organization():
    name = request.form.get('name', '').strip()
    password = request.form.get('password', '').strip()
    description = request.form.get('description', '').strip()
    
    if not name:
        return jsonify({'error': 'Organization name required'}), 400
        
    data = load_events()
    org_id = generate_unique_id(4, data.get('organizations', {}).keys())
        
    data['organizations'][org_id] = {
        'name': name,
        'description': description
    }
    
    if password:
        data['organizations'][org_id]['password'] = password
        
    if not save_events(data):
        return jsonify({'error': 'Failed to save organization'}), 500
        
    return jsonify({'success': True, 'org_id': org_id})

# ── Static Media Serving ──────────────────────────────────────────────────────

def add_cache_headers(response, max_age=31536000):
    response.headers['Cache-Control'] = f'public, max-age={max_age}, immutable'
    return response

@app.route('/<event_id:event_id>/m/<filename>')
def media_file(event_id, filename):
    data = load_events()
    ev = data.get('events', {}).get(event_id)
    if not ev:
        abort(404)
    
    key = request.args.get('key', '')
    if ev.get('password') and key != ev['password'] and not session.get('is_admin'):
        abort(403)
        
    media_dir = os.path.join(DATA_DIR, ev['folder'], 'Media')
    if not os.path.isdir(media_dir):
        abort(404)
    response = send_from_directory(media_dir, filename)
    return add_cache_headers(response, max_age=86400)

@app.route('/<event_id:event_id>/t/<filename>')
def thumb_file(event_id, filename):
    data = load_events()
    ev = data.get('events', {}).get(event_id)
    if not ev:
        abort(404)
    
    key = request.args.get('key', '')
    if ev.get('password') and key != ev['password'] and not session.get('is_admin'):
        abort(403)
        
    thumb_dir = os.path.join(DATA_DIR, ev['folder'], 'Thumbnail')
    if os.path.isdir(thumb_dir) and os.path.exists(os.path.join(thumb_dir, filename)):
        response = send_from_directory(thumb_dir, filename)
        return add_cache_headers(response)
    return global_thumb(filename)

@app.route('/<event_id:event_id>/thumbnail')
def event_thumb(event_id):
    data = load_events()
    ev = data.get('events', {}).get(event_id)
    if not ev:
        abort(404)
    
    event_folder = os.path.join(DATA_DIR, ev['folder'])
    if os.path.exists(os.path.join(event_folder, 'thumbnail.webp')):
        response = send_from_directory(event_folder, 'thumbnail.webp')
        return add_cache_headers(response)
    return global_thumb('event.webp')

@app.route('/thumbs/<filename>')
def global_thumb(filename):
    response = send_from_directory(GLOBAL_THUMB_DIR, filename)
    return add_cache_headers(response)

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 2021))
    app.run(debug=True, use_reloader=True, host='0.0.0.0', port=port)
