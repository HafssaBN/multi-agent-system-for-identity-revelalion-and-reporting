
import logging
from typing import Dict, Union
from serpapi import GoogleSearch, BaiduSearch
from ..constants.constants import Constants

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class SearchTools:
    """
    A class that holds the implementation for search tools.
    This keeps the API and execution logic contained in one place.
    """
    def __init__(self):
        self.api_key = Constants.SERPAPI_API_KEY
        if not self.api_key:
            raise ValueError("SERPAPI_API_KEY is not set in your .env file. Search tools cannot function.")

    def _execute_search(self, params: Dict) -> Union[Dict, list]:
        """A private helper method to execute a search with robust error handling."""
        try:
            params['api_key'] = self.api_key
            if params.get('engine') == 'baidu':
                search = BaiduSearch(params)
            else:
                search = GoogleSearch(params)
            
            results = search.get_dict()
            if "error" in results:
                logger.error(f"SerpApi Error for engine {params.get('engine')}: {results['error']}")
                return {"error": results["error"]}
            return results
        except Exception as e:
            logger.error(f"An unexpected error occurred during SerpApi search: {e}", exc_info=True)
            return {"error": f"An unexpected exception occurred: {str(e)}"}

# --- Initialize a single instance of the class that other modules can import ---
search_tools_instance = SearchTools()