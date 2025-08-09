from typing import Dict, List, Union
from langchain_community.tools.tavily_search import TavilySearchResults
from langchain_community.utilities.google_search import GoogleSearchAPIWrapper
from langchain_community.document_loaders import WebBaseLoader
import logging

class SearchTools:
    def __init__(self):
        self.tavily = TavilySearchResults()
        self.google_search = GoogleSearchAPIWrapper()
        self.logger = logging.getLogger(__name__)
    
    def tavily_search(self, query: str) -> Union[List[Dict[str, str]], Dict[str, str]]:
        """Perform a general web search using Tavily."""
        try:
            results = self.tavily.invoke({"query": query})
            # Ensure results is a list before proceeding
            if not isinstance(results, list):
                return {"error": f"Tavily search returned an unexpected format: {type(results)}"}
            return [{"url": r.get("url"), "content": r.get("content")} for r in results]
        except Exception as e:
            self.logger.error(f"Tavily search failed: {str(e)}")
            return {"error": f"Tavily search failed: {str(e)}"}
    
    def google_search(self, query: str) -> Union[List[Dict[str, str]], Dict[str, str]]:
        """Perform an advanced Google search (supports dork queries)."""
        try:
            results = self.google_search.results(query, 5)
            if not isinstance(results, list):
                return {"error": f"Google search returned an unexpected format: {type(results)}"}
            return [{"url": r.get("link"), "title": r.get("title")} for r in results]
        except Exception as e:
            self.logger.error(f"Google search failed: {str(e)}")
            return {"error": f"Google search failed: {str(e)}"}
    
    def web_scraper(self, url: str) -> Dict[str, str]:
        """Scrape content from a specific URL."""
        try:
            loader = WebBaseLoader(url)
            docs = loader.load()
            content = docs[0].page_content if docs else "No content found."
            return {"url": url, "content": content[:5000]}  # Limit content
        except Exception as e:
            self.logger.error(f"Web scraping failed for {url}: {str(e)}")
            return {"url": url, "content": "", "error": f"Web scraping failed: {str(e)}"}

# Initialize tools
search_tools_instance = SearchTools()
tavily_search = search_tools_instance.tavily_search
google_search = search_tools_instance.google_search
web_scraper = search_tools_instance.web_scraper