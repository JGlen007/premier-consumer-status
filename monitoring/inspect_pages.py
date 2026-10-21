import json
from concurrent.futures import ThreadPoolExecutor
from html.parser import HTMLParser
from pathlib import Path
from http_probe import request

class Scan(HTMLParser):
    def __init__(self):
        super().__init__()
        self.lang = None
        self.forms = []
        self.inputs = []
        self.iframes = []
    def handle_starttag(self, tag, attrs):
        a = dict(attrs)
        if tag == "html": self.lang = a.get("lang")
        if tag == "form": self.forms.append({k:a.get(k) for k in ("id","class","action")})
        if tag == "input" and a.get("type","text") not in ("hidden","checkbox","radio","submit"):
            self.inputs.append({k:a.get(k) for k in ("type","name","id")})
        if tag == "iframe": self.iframes.append({k:a.get(k) for k in ("src","title")})

def scan(site):
    status, final, body, seconds = request(site["url"])
    parser = Scan()
    parser.feed(body.decode("utf-8", errors="replace"))
    return {"id":site["id"],"status":status,"final":final,"lang":parser.lang,"forms":parser.forms[:8],"inputs":parser.inputs[:15],"iframes":parser.iframes[:5]}
sites=json.loads(Path("monitoring/sites.json").read_text())
with ThreadPoolExecutor(max_workers=5) as pool:
    for result in pool.map(scan,sites):
        print(json.dumps(result),flush=True)
