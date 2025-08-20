# test_serpapi_direct.py

import os
from dotenv import load_dotenv
from serpapi import GoogleSearch

load_dotenv()

def test_serpapi():
    """Test SerpAPI directly to verify it's working."""
    api_key = os.getenv("SERPAPI_API_KEY")
    
    if not api_key:
        print("❌ SERPAPI_API_KEY not found in environment variables")
        return False
    
    print(f"✅ SERPAPI_API_KEY found (length: {len(api_key)})")
    
    # Test 1: Regular Google search
    print("\n--- Test 1: Regular Google Search ---")
    try:
        search = GoogleSearch({
            "q": "test search query", 
            "api_key": api_key,
            "num": 3
        })
        results = search.get_dict()
        
        if "error" in results:
            print(f"❌ SerpAPI Error: {results['error']}")
            return False
        else:
            organic_results = results.get("organic_results", [])
            print(f"✅ Found {len(organic_results)} organic results")
            if organic_results:
                print(f"   First result: {organic_results[0].get('title', 'No title')[:50]}...")
            return True
            
    except Exception as e:
        print(f"❌ Exception during regular search: {str(e)}")
        return False
    
def test_google_lens():
    """Test Google Lens specifically."""
    api_key = os.getenv("SERPAPI_API_KEY")
    
    print("\n--- Test 2: Google Lens Search ---")
    try:
        search = GoogleSearch({
            "engine": "google_lens",
            "url": "https://a0.muscache.com/im/pictures/user/User/original/213a678f-2d3c-4b11-886e-df873b318aa4.jpeg?im_w=720",
            "api_key": api_key
        })
        results = search.get_dict()
        
        if "error" in results:
            print(f"❌ Google Lens Error: {results['error']}")
            return False
        else:
            visual_matches = results.get("visual_matches", [])
            print(f"✅ Found {len(visual_matches)} visual matches")
            if visual_matches:
                print(f"   First match: {visual_matches[0].get('title', 'No title')[:50]}...")
            return True
            
    except Exception as e:
        print(f"❌ Exception during Google Lens search: {str(e)}")
        return False

def test_search_tools():
    """Test the imported search tools."""
    print("\n--- Test 3: Search Tools Import ---")
    try:
        from multi_agents.tools.search_tools import google_search, google_lens_search
        
        print("✅ Successfully imported search tools")
        
        # Test google_search tool
        print("\nTesting google_search tool...")
        result = google_search.invoke({"query": "test query"})
        print(f"✅ google_search tool returned: {type(result)}")
        
        # Test google_lens_search tool  
        print("\nTesting google_lens_search tool...")
        result = google_lens_search.invoke({
            "image_url": "https://a0.muscache.com/im/pictures/user/User/original/213a678f-2d3c-4b11-886e-df873b318aa4.jpeg?im_w=720"
        })
        print(f"✅ google_lens_search tool returned: {type(result)}")
        
        return True
        
    except Exception as e:
        print(f"❌ Error testing search tools: {str(e)}")
        import traceback
        traceback.print_exc()
        return False

if __name__ == "__main__":
    print("=== SerpAPI Testing ===")
    
    # Test basic API functionality
    basic_works = test_serpapi()
    
    # Test Google Lens
    lens_works = test_google_lens()
    
    # Test our wrapped tools
    tools_work = test_search_tools()
    
    print(f"\n=== Results ===")
    print(f"Basic SerpAPI: {'✅ Working' if basic_works else '❌ Failed'}")
    print(f"Google Lens: {'✅ Working' if lens_works else '❌ Failed'}")  
    print(f"Search Tools: {'✅ Working' if tools_work else '❌ Failed'}")
    
    if basic_works and lens_works and tools_work:
        print("\n🎉 All tests passed! Your search tools should work now.")
    else:
        print("\n⚠️  Some tests failed. Check the errors above.")
        print("\nCommon issues:")
        print("- SerpAPI key invalid or out of credits")
        print("- Internet connectivity issues")
        print("- Module import path problems")