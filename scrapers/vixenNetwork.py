import json
import os
import re
import requests
import sys
import traceback


MINIMUM_VERSION_MAJOR = 3
MINIMUM_VERSION_MINOR = 3


def log(*s):
    print(*s, file=sys.stderr)


def get_from_url(url_to_parse):
    m = re.match(r'(?:https?://)?(?:www\.)?((\w+)\.com)/(?:videos/)?([a-z0-9-]+)', url_to_parse)
    if m is None:
        return None, None, None
    return m.groups()


def make_request(request_url, origin_site):
    try:
        r = requests.get(request_url, headers={
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:79.0) Gecko/20100101 Firefox/79.0',
            'Origin': origin_site,
            'Referer': request_url
        }, timeout=(3, 6))
    except requests.exceptions.RequestException as e:
        return None, e
    if r.status_code == 200:
        return r.text, None
    return None, 'HTTP Error: %s' % r.status_code


def fetch_page_json(page_html):
    try:
        tag = '<script id="__NEXT_DATA__" type="application/json">'
        start = page_html.index(tag) + len(tag)
    except ValueError:
        # script tag not found
        matches = re.findall(r'window\.__APOLLO_STATE__ = (.+);$', page_html, re.MULTILINE)
        return json.loads(matches[0]) if matches else None

    end = page_html.index('</script>', start)
    content = page_html[start:end]
    data = json.loads(content)

    return data['props']['pageProps']['__APOLLO_STATE__']


def save_json(scraped_json, video_id, save_location):
    location = os.path.join('..', 'scraperJSON', 'VixenNetwork')
    if save_location != 'save':
        location = save_location
    try:
        os.makedirs(location)
    except FileExistsError:
        pass
    filename = os.path.join(location, '%s.json' % video_id)
    with open(filename, 'w', encoding='utf-8') as f:
        json.dump(scraped_json, f, ensure_ascii=False, indent=4)


def main():
    stdin = sys.stdin.read()
    log(stdin)
    fragment = json.loads(stdin)

    if not fragment['url']:
        log('No URL entered.')
        sys.exit(1)
    url = fragment['url'].strip()
    site, studio, slug = get_from_url(url)
    if site is None:
        log('The URL could not be parsed')
        sys.exit(1)
    response, err = make_request('https://%s/videos/%s' % (site, slug), 'https://%s' % site)
    if err is not None:
        log('Could not fetch page HTML', err)
        sys.exit(1)
    j = fetch_page_json(response)
    if j is None:
        log('Could not find JSON on page')
        sys.exit(1)
    scene_id = 'Video:%s:%s' % (studio, slug)
    if scene_id not in j:
        log('Could not locate scene within JSON')
        sys.exit(1)
    scene = j[scene_id]
    scene_url = url
    if scene['absoluteUrl'] is not None:
        scene_url = 'https:%s' % scene['absoluteUrl']
    scrape = {}
    if scene.get('title'):
        scrape['title'] = scene['title']
    if scene.get('releaseDate'):
        scrape['date'] = scene['releaseDate'][:10]
    if scene.get('description'):
        scrape['details'] = scene['description']
    if scene_url:
        scrape['url'] = scene_url
    if studio:
        scrape['studio'] = {'name': studio}
    if scene.get('models'):
        scrape['performers'] = [{'name': x['name']} for x in scene['models']]
    if scene.get('categories'):
        scrape['tags'] = [{'name': x['name']} for x in scene['categories']]
    if scene.get('images'):
        scrape['image'] = scene['images']['poster'][len(scene['images']['poster']) - 1]['src']
    if len(sys.argv) > 1:
        save_json(j, scene['videoId'], sys.argv[1])
    print(json.dumps(scrape))


if __name__ == '__main__':
    if sys.version_info.major != MINIMUM_VERSION_MAJOR or sys.version_info.minor < MINIMUM_VERSION_MINOR:
        log('Invalid Python version. Version %s.%s or later required.' % (MINIMUM_VERSION_MAJOR, MINIMUM_VERSION_MINOR))
        sys.exit(1)
    try:
        main()
    except Exception as e:
        log(traceback.format_exc())
        log(e)
