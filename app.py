#!/usr/bin/env python3
from flask import Flask, request, jsonify, send_file
import os
import re
import cloudscraper
from urllib3.util.retry import Retry
from requests.adapters import HTTPAdapter
import threading

app = Flask(__name__)
scraper = cloudscraper.create_scraper()
scraper.mount('https://', HTTPAdapter(max_retries=Retry(total=2, backoff_factor=0.5)))

channels_cache = {}
cache_lock = threading.Lock()
cache_loaded = False

def preload_channels():
    global cache_loaded
    print('[SOF] Preloading channels...')
    for p in range(1, 10):
        try:
            r = scraper.get(f'https://searchtv.net/list-line/{p}/', timeout=20)
            if r.status_code == 200:
                links = re.findall(r'href="(/post/line/channel/[^"]+)"[^>]*>\s*Watch Now', r.text)
                if not links:
                    break
                with cache_lock:
                    channels_cache[p] = links
                print(f'  Page {p}: {len(links)} channels')
            else:
                break
        except Exception as e:
            print(f'  Error page {p}: {e}')
            break
    cache_loaded = True
    total = sum(len(v) for v in channels_cache.values())
    print(f'[SOF] Loaded {total} channels')

def get_channels(page=1):
    with cache_lock:
        if page in channels_cache:
            return channels_cache[page]
    try:
        r = scraper.get(f'https://searchtv.net/list-line/{page}/', timeout=20)
        if r.status_code == 200:
            links = re.findall(r'href="(/post/line/channel/[^"]+)"[^>]*>\s*Watch Now', r.text)
            with cache_lock:
                channels_cache[page] = links
            return links
    except:
        pass
    return []

def get_stream_url(slug_raw, number):
    try:
        url = f'https://searchtv.net/stream/line/channel/{slug_raw}/number/{number}/'
        r = scraper.get(url, timeout=10, stream=True, allow_redirects=False)
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

@app.route('/hls.min.js')
def hls_js():
    return send_file(os.path.join(os.path.dirname(__file__), 'hls.min.js'))

@app.route('/api/search')
def api_search():
    global cache_loaded
    q = request.args.get('q', '').strip().lower()
    page = int(request.args.get('page', 1))
    
    if not q:
        return jsonify({'streams': [], 'total': 0})
    
    if not cache_loaded:
        preload_channels()
    
    results = []
    checked = 0
    
    for p in range(1, 100):
        links = get_channels(p)
        if not links:
            break
        
        for link in links:
            match = re.search(r'channel/([^/]+)/number/(\d+)', link)
            if match:
                slug_raw = match.group(1)
                number = match.group(2)
                name = slug_raw.replace('-', ' ').replace('(', ' [').replace(')', ']')
                
                if q in name.lower():
                    url = get_stream_url(slug_raw, number)
                    if url:
                        title = re.sub(r'\s*\[[^\]]*\]', '', name).strip()
                        results.append({'title': title, 'url': url})
                
                checked += 1
                if checked >= 100:
                    break
        
        if checked >= 100:
            break
    
    results.sort(key=lambda x: 1 if '1080' in x['title'] else (2 if '720' in x['title'] else 3))
    
    limit = 20
    start = (page - 1) * limit
    chunk = results[start:start + limit]
    
    return jsonify({
        'streams': chunk,
        'hasMore': start + limit < len(results),
        'total': len(results)
    })

@app.route('/api/status')
def api_status():
    with cache_lock:
        return jsonify({
            'loaded': cache_loaded,
            'pages': len(channels_cache),
            'channels': sum(len(v) for v in channels_cache.values())
        })

@app.route('/api/load')
def api_load():
    preload_channels()
    return jsonify({
        'loaded': True,
        'channels': sum(len(v) for v in channels_cache.values())
    })

if __name__ == '__main__':
    print('SŌF TV - searchtv.net')
    preload_channels()
    app.run(host='0.0.0.0', port=8080, threaded=True, debug=False)