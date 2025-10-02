import requests
from bs4 import BeautifulSoup
import logging
from typing import Dict, List, Optional
import asyncio
import httpx

logger = logging.getLogger(__name__)

class WebTools:
    """Enhanced web tools with better error handling and features"""
    
    def __init__(self):
        self.session = None
        self.max_concurrent_requests = 5
        self.request_timeout = 30
    
    async def search_web(self, query: str, num_results: int = 5) -> Dict:
        """
        Mencari di web menggunakan DuckDuckGo dengan error handling yang lebih baik
        """
        try:
            # Gunakan httpx untuk async request
            async with httpx.AsyncClient(timeout=self.request_timeout) as client:
                response = await client.get(
                    'https://duckduckgo.com/html/',
                    params={'q': query},
                    headers={
                        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'
                    }
                )
                
                response.raise_for_status()
                html = response.text
                
                # Parse hasil pencarian
                soup = BeautifulSoup(html, 'html.parser')
                results = []
                
                for result_elem in soup.select('.result__body'):
                    try:
                        title_elem = result_elem.select_one('.result__title')
                        snippet_elem = result_elem.select_one('.result__snippet')
                        url_elem = result_elem.select_one('.result__url')
                        
                        if title_elem and snippet_elem and url_elem:
                            title = title_elem.get_text(strip=True)
                            snippet = snippet_elem.get_text(strip=True)
                            url = url_elem.get('href')
                            
                            # Validasi URL
                            if url and (url.startswith('http://') or url.startswith('https://')):
                                results.append({
                                    'title': title,
                                    'snippet': snippet,
                                    'url': url
                                })
                                
                                if len(results) >= num_results:
                                    break
                                    
                    except Exception as e:
                        logger.warning(f"Error parsing search result: {e}")
                        continue
                
                return {"results": results}
                
        except httpx.TimeoutException as e:
            logger.error(f"Timeout saat mencari di web: {e}")
            return {"results": [], "error": "Timeout"}
        except httpx.RequestError as e:
            logger.error(f"Error request saat mencari di web: {e}")
            return {"results": [], "error": "Request failed"}
        except Exception as e:
            logger.error(f"Error tak terduga saat mencari di web: {e}")
            return {"results": [], "error": "Unknown error"}
    
    async def scrape_url(self, url: str, max_content_length: int = 8000) -> Dict:
        """
        Mengambil dan membersihkan teks utama dari sebuah URL dengan error handling yang lebih baik
        """
        try:
            async with httpx.AsyncClient(timeout=self.request_timeout) as client:
                response = await client.get(
                    url,
                    headers={
                        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"
                    }
                )
                
                response.raise_for_status()
                html = response.text
                
                # Parse konten halaman
                soup = BeautifulSoup(html, "html.parser")
                
                # Coba cari konten utama
                main_content = (
                    soup.find("article") or
                    soup.find("main") or
                    soup.find("div", class_="content") or
                    soup.find("div", id="content") or
                    soup.body
                )
                
                if not main_content:
                    return {"text": "", "error": "No content found"}
                
                # Hapus elemen yang tidak relevan
                selectors_to_remove = [
                    'script', 'style', 'nav', 'footer', 'header', 'aside',
                    '.sidebar', '.ad', '.advertisement', '.cookie-banner'
                ]
                
                for selector in selectors_to_remove:
                    for element in main_content.select(selector):
                        element.decompose()
                
                # Ekstrak teks
                text = main_content.get_text(separator="\n", strip=True)
                
                # Batasi panjang teks
                if len(text) > max_content_length:
                    text = text[:max_content_length] + "\n\n[Content truncated]"
                
                return {"text": text}
                
        except httpx.TimeoutException as e:
            logger.error(f"Timeout saat scraping URL {url}: {e}")
            return {"text": "", "error": "Timeout"}
        except httpx.RequestError as e:
            logger.error(f"Error request saat scraping URL {url}: {e}")
            return {"text": "", "error": "Request failed"}
        except Exception as e:
            logger.error(f"Error tak terduga saat scraping URL {url}: {e}")
            return {"text": "", "error": "Unknown error"}

# Instansiasi global
web_tools = WebTools()

# Fungsi kompatibilitas untuk kode lama
async def search_web(q: str, num_results: int = 5):
    """Fungsi kompatibilitas untuk kode lama"""
    return await web_tools.search_web(q, num_results)

async def scrape_url(url: str):
    """Fungsi kompatibilitas untuk kode lama"""
    return await web_tools.scrape_url(url)
