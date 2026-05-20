#!/usr/bin/env python3
from flask import Flask, request, jsonify, send_file
import os
import re
import cloudscraper

app = Flask(__name__)
scraper = cloudscraper.create_scraper()

channels_cache = []
cache_ready = False

def load_all_channels():
    global channels_cache, cache_ready
    print('[SOF] Loading channels...')
    
    for page in range(1, 100):
        try:
            r = scraper.get(f'https://searchtv.net/list-line/{page}/', timeout=20)
            if r.status_code != 200:
                break
            
            links = re.findall(r'href="(/post/line/channel/[^"]+)"[^>]*>\s*Watch Now', r.text)
            if not links:
                break
            
            for link in links:
                m = re.search(r'channel/([^/]+)/number/(\d+)', link)
                if m:
                    slug_raw = m.group(1)
                    number = m.group(2)
                    name = slug_raw.replace('-', ' ').replace('(', '[').replace(')', ']')
                    channels_cache.append({
                        'slug_raw': slug_raw,
                        'number': number,
                        'name': name
                    })
            
            if page % 5 == 0:
                print(f'  Page {page}: {len(channels_cache)} channels')
        except Exception as e:
            print(f'  Page {page} error: {e}')
            break
    
    cache_ready = True
    print(f'[SOF] Total: {len(channels_cache)} channels')

def get_stream_url(slug_raw, number):
    try:
        url = f'https://searchtv.net/stream/line/channel/{slug_raw}/number/{number}/'
        r = scraper.get(url, timeout=10, stream=True, allow_redirects=False)
        if r.status_code == 200:
            ct = r.headers.get('content-type', '')
            if 'mpeg' in ct or 'm3u' in ct:
                content = r.content.decode('utf-8', errors='ignore')
                for line in content.split('\n'):
                    if line.startswith('http') and '.m3u8' in line:
                        return line.strip()
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
    global cache_ready
    q = request.args.get('q', '').strip().lower()
    page = int(request.args.get('page', 1))
    
    if not q:
        return jsonify({'streams': [], 'total': 0})
    
    if not cache_ready:
        load_all_channels()
    
    results = []
    checked = 0
    
    for ch in channels_cache:
        name_lower = ch['name'].lower()
        if q in name_lower:
            url = get_stream_url(ch['slug_raw'], ch['number'])
            if url:
                title = re.sub(r'\s\[[^\]]+\]', '', ch['name']).strip()
                results.append({'title': title, 'url': url})
        
        checked += 1
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

@app.route('/api/channels')
def api_channels():
    global cache_ready
    if not cache_ready:
        load_all_channels()
    return jsonify({'count': len(channels_cache), 'loaded': cache_ready})

@app.route('/api/status')
def api_status():
    return jsonify({'loaded': cache_ready, 'channels': len(channels_cache)})

if __name__ == '__main__':
    print('SŌF TV - searchtv.net')
    load_all_channels()
    app.run(host='0.0.0.0', port=8080, threaded=True, debug=False)