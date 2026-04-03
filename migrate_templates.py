import os

def process_file(filepath, replacements):
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
    
    for old, new in replacements:
        content = content.replace(old, new)
        
    with open(filepath, 'w', encoding='utf-8') as f:
        f.write(content)

base_dir = r"s:\Dev\Gen9\Ameryd\templates"

# event.html
event_replacements = [
    ("url_for('event_thumb', event_path=event_path,", "url_for('event_thumb', org_id=org_id, event_id=event_id,"),
    ("url_for('upload_page', event_path=event_path)", "url_for('upload_page', org_id=org_id, event_id=event_id)"),
    ("url_for('edit_event_page', event_path=event_path)", "url_for('edit_event_page', org_id=org_id, event_id=event_id)"),
    ("url_for('list_events')", "url_for('root')"),
    ("url_for(media.thumb_route, event_path=event_path, filename=media.filename, key=key) if media.thumb_route == 'media_file' else url_for('media_file', event_path=event_path, filename=media.filename, key=key)", "url_for(media.thumb_route, org_id=org_id, event_id=event_id, filename=media.filename, key=key) if media.thumb_route == 'media_file' else url_for('media_file', org_id=org_id, event_id=event_id, filename=media.filename, key=key)"),
    ("url_for('thumb_file', event_path=event_path, filename=media.thumb_filename, key=key)", "url_for('thumb_file', org_id=org_id, event_id=event_id, filename=media.thumb_filename, key=key)"),
    ("var eventPath = \"{{ event_path }}\";", "var orgId = \"{{ org_id }}\";\n        var eventId = \"{{ event_id }}\";"),
    ('window._dynamicEventPath = eventPath;', 'window._dynamicOrgId = orgId; window._dynamicEventId = eventId;'),
    ("'/e/' + eventPath + '/t/'", "'/' + orgId + '/' + eventId + '/t/'"),
    ("'/e/' + eventPath + '/m/'", "'/' + orgId + '/' + eventId + '/m/'"),
    ("fetch('/api/events/{{ event_path }}/delete'", "fetch('/api/events/{{ org_id }}/{{ event_id }}/delete'"),
    ("fetch(`/api/e/{{ event_path }}/delete`", "fetch(`/api/${orgId}/${eventId}/delete`"),
    ("window.location.href = '/e';", "window.location.href = '/';"),
    ("const eventPath = \"{{ event_path }}\";", "const orgId = \"{{ org_id }}\";\n        const eventId = \"{{ event_id }}\";"),
    ("`/e/${eventPath}/m/${filename}?key=${key}`", "`/${orgId}/${eventId}/m/${filename}?key=${key}`"),
    ("`/e/${eventPath}/t/${item.thumb_filename}?key=${key}`", "`/${orgId}/${eventId}/t/${item.thumb_filename}?key=${key}`"),
    ("fetch(`/api/e/${eventPath}?page=${page}&key=${key}`)", "fetch(`/api/${orgId}/${eventId}?page=${page}&key=${key}`)")
]
process_file(os.path.join(base_dir, 'event.html'), event_replacements)

# upload.html
upload_replacements = [
    ("url_for('list_events')", "url_for('root')"),
    ("url_for('event_page', event_path=event_path)", "url_for('event_page', org_id=org_id, event_id=event_id)"),
    ("const eventPath = \"{{ event_path }}\";", "const orgId = \"{{ org_id }}\";\n    const eventId = \"{{ event_id }}\";"),
    ("`/api/e/${eventPath}/upload`", "`/api/${orgId}/${eventId}/upload`")
]
process_file(os.path.join(base_dir, 'upload.html'), upload_replacements)

# event_form.html - this one needs some manual replacements because of block replacements
with open(os.path.join(base_dir, 'event_form.html'), 'r') as f:
    content = f.read()

content = content.replace("url_for('list_events')", "url_for('root')")

event_id_block = '''                    {% if not event %}
                    <div class="mb-3">
                        <label for="event_id" class="form-label">Event ID (URL Path)</label>
                        <input type="text" class="form-control" id="event_id" name="event_id"
                            placeholder="Auto-generated if empty" required>
                        <div class="form-text">Optional: Customize the URL (e.g., /e/my-custom-path).</div>
                    </div>
                    {% endif %}'''

org_id_block = '''                    {% if not event %}
                    <div class="mb-3">
                        <label for="org_id" class="form-label">Organization <span class="text-danger">*</span></label>
                        <select class="form-control" id="org_id" name="org_id" required>
                            {% for oid in orgs %}
                            <option value="{{ oid }}" {% if oid == org_id %}selected{% endif %}>{{ oid }}</option>
                            {% endfor %}
                        </select>
                        <div class="form-text">Choose the underlying organization for this event</div>
                    </div>
                    {% endif %}'''

content = content.replace(event_id_block, org_id_block)

js_vars_old = '''    const isEdit = {{ 'true' if event else 'false' }};
    const eventPath = "{{ event_path if event else '' }}";'''
js_vars_new = '''    const isEdit = {{ 'true' if event else 'false' }};
    const orgId = "{{ org_id if event else '' }}";
    const eventId = "{{ event_id if event else '' }}";'''
content = content.replace(js_vars_old, js_vars_new)

url_old = "const url = isEdit ? `/api/events/${eventPath}/update` : '/api/events/create';"
url_new = "const url = isEdit ? `/api/events/${orgId}/${eventId}/update` : '/api/events/create';"
content = content.replace(url_old, url_new)

redirect_old = '''                    if (isEdit) {
                        window.location.href = `/e/${eventPath}`;
                    } else {
                        window.location.href = `/e/${data.event_path}`;
                    }'''
redirect_new = '''                    if (isEdit) {
                        window.location.href = `/${orgId}/${eventId}`;
                    } else {
                        window.location.href = `/${data.org_id}/${data.event_id}`;
                    }'''
content = content.replace(redirect_old, redirect_new)

with open(os.path.join(base_dir, 'event_form.html'), 'w') as f:
    f.write(content)

print("Done")
