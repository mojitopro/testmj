#!/usr/bin/env python3
from flask import Flask, request, jsonify, send_file
import os
import re
import json
import cloudscraper

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, 'channels_db.json')
STREAMS_FILE = os.path.join(BASE_DIR, 'streams_cache.json')

channels_db = None
streams_cache = {}
scraper = cloudscraper.create_scraper()

def load_db():
    global channels_db
    if channels_db is None:
        if os.path.exists(DB_FILE):
            with open(DB_FILE, 'r') as f:
                channels_db = json.load(f)
            print(f'[SOF] {len(channels_db)} canales')
        else:
            channels_db = []

def get_stream(slug_raw, number):
    key = f"{slug_raw}|{number}"
    if key in streams_cache:
        return streams_cache[key]
    
    try:
        url = f'https://searchtv.net/stream/line/channel/{slug_raw}/number/{number}/'
        r = scraper.get(url, timeout=10, stream=True, allow_redirects=False)
        if r.status_code == 200 and ('mpeg' in r.headers.get('content-type', '') or 'm3u' in r.headers.get('content-type', '')):
            content = r.content.decode('utf-8', errors='ignore')
            for line in content.split('\n'):
                if line.startswith('http'):
                    streams_cache[key] = line.strip()
                    return line.strip()
    except:
        pass
    return None

@app.route('/')
def index():
    return send_file(os.path.join(BASE_DIR, 'tv.html'))

@app.route('/hls.min.js')
def hls_js():
    return send_file(os.path.join(BASE_DIR, 'hls.min.js'))

@app.route('/api/search')
def api_search():
    q = request.args.get('q', '').strip().lower()
    page = int(request.args.get('page', 1))
    
    if not q:
        return jsonify({'streams': [], 'total': 0})
    
    load_db()
    
    results = []
    for ch in channels_db:
        if q in ch['name'].lower():
            url = get_stream(ch['slug_raw'], ch['number'])
            if url:
                title = re.sub(r'\s\[[^\]]+\]', '', ch['name']).strip()
                results.append({'title': title, 'url': url})
    
    results.sort(key=lambda x: 1 if '1080' in x['title'] else (2 if '720' in x['title'] else 3))
    
    limit = 20
    start = (page - 1) * limit
    chunk = results[start:start + limit]
    
    return jsonify({
        'streams': chunk,
        'hasMore': start + limit < len(results),
        'total': len(results)
    })

@app.route('/api/channels')
def api_channels():
    load_db()
    return jsonify({'count': len(channels_db)})

@app.route('/api/status')
def api_status():
    load_db()
    return jsonify({'loaded': len(channels_db) > 0, 'channels': len(channels_db), 'cached_streams': len(streams_cache)})

@app.route('/api/cached-streams')
def api_cached_streams():
    load_db()
    return jsonify(streams_cache)

if __name__ == '__main__':
    print('SŌF TV')
    load_db()
    app.run(host='0.0.0.0', port=8080)