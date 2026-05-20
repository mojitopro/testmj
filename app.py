#!/usr/bin/env python3
from flask import Flask, request, jsonify, send_file
import os
import re
import cloudscraper

app = Flask(__name__)
scraper = cloudscraper.create_scraper()

channels_db = []
db_ready = False

def load_channels():
    global channels_db, db_ready
    print('[SOF] Loading channels from searchtv.net...')
    
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
                    channels_db.append({
                        'slug': slug_raw,
                        'num': number,
                        'name': name
                    })
            
            if page % 5 == 0:
                print(f'  Page {page}: {len(channels_db)} channels')
        except Exception as e:
            print(f'  Page {page} error: {e}')
            break
    
    db_ready = True
    print(f'[SOF] Total: {len(channels_db)} channels')

def get_stream(slug, num):
    try:
        url = f'https://searchtv.net/stream/line/channel/{slug}/number/{num}/'
        r = scraper.get(url, timeout=10, stream=True, allow_redirects=False)
        if r.status_code == 200:
            ct = r.headers.get('content-type', '')
            if 'mpeg' in ct or 'm3u' in ct:
                txt = r.content.decode('utf-8', errors='ignore')
                for line in txt.split('\n'):
                    if line.startswith('http') and '.m3u8' in line:
                        return line.strip()
                for line in txt.split('\n'):
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
    global db_ready
    q = request.args.get('q', '').strip().lower()
    
    if not q:
        return jsonify({'streams': []})
    
    if not db_ready:
        load_channels()
    
    results = []
    for ch in channels_db:
        if q in ch['name'].lower():
            url = get_stream(ch['slug'], ch['num'])
            if url:
                title = re.sub(r'\s\[[^\]]+\]', '', ch['name']).strip()
                results.append({'title': title, 'url': url})
                if len(results) >= 50:
                    break
    
    results.sort(key=lambda x: 1 if '1080' in x['title'] else 2)
    return jsonify({'streams': results})

@app.route('/api/channels')
def api_channels():
    global db_ready
    if not db_ready:
        load_channels()
    return jsonify({'count': len(channels_db), 'loaded': db_ready})

@app.route('/api/adult')
def api_adult():
    return jsonify({
        'streams': [
            {'title': 'Adult Swim', 'url': 'http://181.119.86.1:8000/play/a019'},
            {'title': 'Adult Swim 2', 'url': 'http://190.60.59.67:8000/play/a0io'},
            {'title': 'Cartoon Network', 'url': 'http://181.119.86.1:8000/play/a01g'},
            {'title': 'Nickelodeon', 'url': 'http://45.169.163.237:4000/play/a01c'},
            {'title': 'HBO', 'url': 'http://38.187.3.110:8000/play/a07z/index.m3u8'},
            {'title': 'ESPN', 'url': 'http://38.41.8.1:8000/play/a0t3'},
            {'title': 'ESPN 2', 'url': 'http://38.41.8.1:8000/play/a0rp'},
            {'title': 'Fox Sports', 'url': 'http://38.41.8.1:8000/play/a0sw'},
            {'title': 'TNT', 'url': 'http://38.41.8.1:8000/play/a0sv'},
            {'title': 'CNN', 'url': 'http://38.41.8.1:8000/play/a0t3'},
            {'title': 'Nat Geo', 'url': 'http://38.41.8.1:8000/play/a0t3'},
            {'title': 'Movies', 'url': 'https://30a-tv.com/feeds/pzaz/30atvmovies.m3u8'}
        ]
    })

if __name__ == '__main__':
    print('SŌF TV - searchtv.net')
    load_channels()
    app.run(host='0.0.0.0', port=8080)