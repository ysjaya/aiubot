import requests
from bs4 import BeautifulSoup

def search_web(q):
    resp = requests.get('https://duckduckgo.com/html/', params={'q': q}, timeout=10)
    soup = BeautifulSoup(resp.text, 'html.parser')
    results = []
    for r in soup.select('.result__body'):
        title = r.select_one('.result__title').get_text(strip=True)
        snippet = r.select_one('.result__snippet').get_text(strip=True)
        url = r.select_one('.result__url').get('href')
        results.append({'title': title, 'snippet': snippet, 'url': url})
        if len(results) >= 5: break
    return {"results": results}

def scrape_url(url):
    resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
    soup = BeautifulSoup(resp.text, "html.parser")
    main = soup.find("main") or soup.body
    text = main.get_text(separator="\n", strip=True)[:8000]
    return {"text": text}
