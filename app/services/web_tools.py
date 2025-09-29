import requests
from bs4 import BeautifulSoup

def search_web(q, num_results=5):
    """
    Mencari di web menggunakan DuckDuckGo.
    
    Args:
        q (str): Kueri pencarian.
        num_results (int): Jumlah hasil yang diinginkan.
    """
    try:
        resp = requests.get('https://duckduckgo.com/html/', params={'q': q}, timeout=10)
        resp.raise_for_status() # Akan raise error jika status code bukan 2xx
        
        soup = BeautifulSoup(resp.text, 'html.parser')
        results = []
        
        for r in soup.select('.result__body'):
            title_tag = r.select_one('.result__title')
            snippet_tag = r.select_one('.result__snippet')
            url_tag = r.select_one('.result__url')

            if title_tag and snippet_tag and url_tag:
                title = title_tag.get_text(strip=True)
                snippet = snippet_tag.get_text(strip=True)
                url = url_tag.get('href')
                results.append({'title': title, 'snippet': snippet, 'url': url})
                if len(results) >= num_results:
                    break
        
        return {"results": results}
    except requests.exceptions.RequestException as e:
        print(f"Error saat mencari di web: {e}")
        return {"results": []}

def scrape_url(url):
    """Mengambil dan membersihkan teks utama dari sebuah URL."""
    try:
        resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
        resp.raise_for_status()
        
        soup = BeautifulSoup(resp.text, "html.parser")
        
        # Coba cari elemen <article> atau <main> terlebih dahulu
        main_content = soup.find("article") or soup.find("main") or soup.body
        
        # Hapus elemen yang tidak relevan
        for element in main_content.find_all(['script', 'style', 'nav', 'footer', 'header', 'aside']):
            element.decompose()
            
        text = main_content.get_text(separator="\n", strip=True)
        # Batasi panjang teks untuk efisiensi
        return {"text": text[:8000]}
    except requests.exceptions.RequestException as e:
        print(f"Error saat scraping URL {url}: {e}")
        return {"text": ""}
