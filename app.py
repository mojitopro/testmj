#!/usr/bin/env python3
from flask import Flask, request, jsonify, send_file
import os
import re
import cloudscraper
from concurrent.futures import ThreadPoolExecutor
import threading

app = Flask(__name__)
executor = ThreadPoolExecutor(max_workers=3)

scraper = cloudscraper.create_scraper()
channels_db = {}
channels_lock = threading.Lock()
db_loaded = False

def load_all_channels():
    global channels_db, db_loaded
    print('[SOF] Loading channels from searchtv.net...')
    
    for page in range(1, 300):
        try:
            r = scraper.get(f'https://searchtv.net/list-line/{page}/', timeout=25)
            if r.status_code != 200:
                break
            
            links = re.findall(r'href="(/post/line/channel/[^"]+)"[^>]*>\s*Watch Now', r.text)
            if not links:
                break
            
            for link in links:
                match = re.search(r'channel/([^/]+)/number/(\d+)', link)
                if match:
                    slug_raw = match.group(1)
                    number = match.group(2)
                    parts = slug_raw.split(',')[0].rsplit('(', 1)[0].strip()
                    name = slug_raw.replace('-', ' ').replace('(', ' [').replace(')', ']')
                    slug = parts.lower().replace(' ', '-')
                    
                    if slug not in channels_db:
                        channels_db[slug] = {
                            'name': name,
                            'raw': slug_raw,
                            'number': number,
                            'link': link
                        }
            
            if page % 5 == 0:
                print(f'  Page {page}: {len(channels_db)} channels')
            
        except Exception as e:
            print(f'  Page {page} error: {e}')
            break
    
    db_loaded = True
    print(f'[SOF] Total channels: {len(channels_db)}')

def get_stream_url(slug, number):
    try:
        url = f'https://searchtv.net/stream/line/channel/{slug_raw}/number/{number}/'
        r = scraper.get(url, timeout=15, stream=True)
        
        if r.status_code == 200 and r.headers.get('content-type', '').startswith('application/x-mpeg'):
            content = r.content.decode('utf-8', errors='ignore')
            for line in content.split('\n'):
                if line.startswith('http'):
                    return line.strip()
    except:
        pass
    return None

@app.route('/')
def index():
    return send_file(os.path.join(os.path.dirname(__file__), 'tv.html'))

@app.route('/api/search')
def api_search():
    global db_loaded
    q = request.args.get('q', '').strip().lower()
    page = int(request.args.get('page', 1))
    
    if not q:
        return jsonify({'streams': []})
    
    with channels_lock:
        if not db_loaded:
            load_all_channels()
    
    matches = []
    for slug, data in channels_db.items():
        name_lower = data['name'].lower()
        if q in name_lower or q in slug:
            matches.append((slug, data))
    
    matches.sort(key=lambda x: 1 if '1080' in x[1]['name'] else (2 if '720' in x[1]['name'] else 3))
    
    limit = 20
    start = (page - 1) * limit
    chunk = matches[start:start + limit]
    
    streams = []
    for slug, data in chunk:
        slug_raw = data['raw']
        number = data['number']
        
        try:
            url = f'https://searchtv.net/stream/line/channel/{slug_raw}/number/{number}/'
            r = scraper.get(url, timeout=15, stream=True)
            
            if r.status_code == 200 and r.headers.get('content-type', '').startswith('application/x-mpeg'):
                content = r.content.decode('utf-8', errors='ignore')
                for line in content.split('\n'):
                    if line.startswith('http'):
                        title = re.sub(r'\s*\[[^\]]*\]', '', data['name']).strip()
                        streams.append({'title': title, 'url': line.strip()})
                        break
        except:
            pass
    
    return jsonify({
        'streams': streams,
        'hasMore': start + limit < len(matches),
        'total': len(matches)
    })

@app.route('/api/status')
def api_status():
    with channels_lock:
        return jsonify({
            'loaded': db_loaded,
            'channels': len(channels_db)
        })

if __name__ == '__main__':
    print('SŌF TV - searchtv.net')
    executor.submit(load_all_channels)
    app.run(host='0.0.0.0', port=8080, threaded=True, debug=False)