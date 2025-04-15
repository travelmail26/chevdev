from serpapi import GoogleSearch
from typing import Dict, Optional
import logging
import json
import os

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def search_serpapi(query: str = "", site: str = "") -> Optional[Dict]:
    """
    Search for recipes using SerpAPI with input validation and error handling.
    
    Args:
        query (str): Search query string
        site (str): Specific site to search, e.g., 'reddit.com'
    """
    search_query = query if not site else f"site:{site} {query}"
    try:
        # Input validation
        if not query or not isinstance(query, str):
            raise ValueError("Query must be a non-empty string")

        logger.info(f"Searching recipes with query: {query} on site: {site}")
        
        params = {
            "q": search_query,
            "hl": "en",
            "num": 30,
            "gl": "us",
            "api_key": "5dfc2b51a4c7d1866b5aca18c49f902cec425ca083affe953bfa5b0c9767de07"
        }

        search = GoogleSearch(params)
        results = search.get_dict()

        # Validate results
        if not results or not isinstance(results, dict):
            logger.warning("No valid results returned from API")
            return None


        try:
            output_path = 'serpapi_recipes_results.txt'
            # Ensure directory exists            
            with open(output_path, 'w', encoding='utf-8') as file:
                json.dump(results, file, indent=2, ensure_ascii=False)
        except IOError as e:
            logger.error(f"Failed to save results to file: {e}")
            # Continue execution even if file save fails
        except TypeError as e:
            logger.error(f"Failed to serialize results to JSON: {e}")
            # Continue execution if JSON serialization fails

        final_result = []
        if 'organic_results' in results:
            print("\n=== results from serp api ===\n")
            for idx, result in enumerate(results['organic_results'], 1):
                print(f"{idx}. Title: {result.get('title', 'No title')}")
                print(f"   URL: {result.get('link', 'No link')}")
                print("-" * 60)
        if 'organic_results' in results:
            final_result = [{'title': result.get('title', 'No title'), 'link': result.get('link', 'No link')}
                           for result in results['organic_results']]
        else:
            print("No organic results found in the API response.")

        print ('DEBUG: serp api results', final_result)
        return final_result

    except Exception as e:
        logger.error(f"Error during recipe search: {e}")
        return None

if __name__ == "__main__":
    query = 'site: reddit.com semifreddo recipe too hard'
    results = search_serpapi(query)
    
    if results is None:
        print("Search failed. Please try again.")