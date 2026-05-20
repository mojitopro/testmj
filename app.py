#!/usr/bin/env python3
from flask import Flask, request, jsonify, send_file
import os
import re
import json
import cloudscraper

app = Flask(__name__)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
DB_FILE = os.path.join(BASE_DIR, 'latin_channels.json')

channels_db = []
streams_cache = {}
scraper = cloudscraper.create_scraper()

def load_db():
    global channels_db
    if not channels_db and os.path.exists(DB_FILE):
        with open(DB_FILE, 'r') as f:
            channels_db = json.load(f)
        print(f'[SOF] {len(channels_db)} canales latinos')

def get_stream_url(slug_raw, number):
    key = f"{slug_raw}|{number}"
    if key in streams_cache:
        return streams_cache[key]
    
    try:
        url = f'https://searchtv.net/stream/line/channel/{slug_raw}/number/{number}/'
        r = scraper.get(url, timeout=10, stream=True, allow_redirects=False)
        if r.status_code == 200:
            ct = r.headers.get('content-type', '')
            if 'mpeg' in ct or 'm3u' in ct:
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
    
    if not q:
        return jsonify({'streams': []})
    
    load_db()
    
    results = []
    for ch in channels_db:
        if q in ch['name'].lower():
            url = get_stream_url(ch['slug_raw'], ch['number'])
            if url:
                title = re.sub(r'\s\[[^\]]+\]', '', ch['name']).strip()
                results.append({'title': title, 'url': url})
                if len(results) >= 50:
                    break
    
    results.sort(key=lambda x: 1 if '1080' in x['title'] else 2)
    
    return jsonify({'streams': results})

@app.route('/api/channels')
def api_channels():
    load_db()
    return jsonify({'count': len(channels_db), 'channels': [c['name'] for c in channels_db]})

@app.route('/api/status')
def api_status():
    load_db()
    return jsonify({'loaded': len(channels_db) > 0, 'channels': len(channels_db), 'cached': len(streams_cache)})

if __name__ == '__main__':
    print('SŌF TV - Canales Latinoamericanos')
    load_db()
    app.run(host='0.0.0.0', port=8080)