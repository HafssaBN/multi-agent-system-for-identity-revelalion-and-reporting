from typing import Dict, List
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.utilities.google_search import GoogleSearchAPIWrapper
from langchain_community.document_loaders import WebBaseLoader
import logging

class SearchTools:
    def __init__(self):
        self.tavily = TavilySearchResults()
        self.google_search = GoogleSearchAPIWrapper()
        self.logger = logging.getLogger(__name__)
    
    def tavily_search(self, query: str) -> List[Dict[str, str]]:
        """Perform a general web search using Tavily."""
        try:
            results = self.tavily.invoke({"query": query})
            return [{"url": r["url"], "content": r["content"]} for r in results]
        except Exception as e:
            self.logger.error(f"Tavily search failed: {str(e)}")
            return []
    
    def google_search(self, query: str) -> List[Dict[str, str]]:
        """Perform an advanced Google search (supports dork queries)."""
        try:
            results = self.google_search.results(query, 5)
            return [{"url": r["link"], "title": r["title"]} for r in results]
        except Exception as e:
            self.logger.error(f"Google search failed: {str(e)}")
            return []
    
    def web_scraper(self, url: str) -> Dict[str, str]:
        """Scrape content from a specific URL."""
        try:
            loader = WebBaseLoader(url)
            docs = loader.load()
            return {"url": url, "content": docs[0].page_content[:5000]}  # Limit content
        except Exception as e:
            self.logger.error(f"Web scraping failed for {url}: {str(e)}")
            return {"url": url, "error": str(e)}

# Initialize tools
tavily_search = SearchTools().tavily_search
google_search = SearchTools().google_search
web_scraper = SearchTools().web_scraper