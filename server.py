from fastapi import FastAPI, HTTPException
from spotipy import Spotify
from spotipy.oauth2 import SpotifyClientCredentials
from loguru import logger
import os
import dotenv
from typing import Dict, List, Optional
from enum import Enum
from pydantic import BaseModel

# Load environment variables
dotenv.load_dotenv()

# Configure logging
logger.add(
    "spotify_fetcher.log",
    rotation="10 MB",
    retention="1 week",
    level="INFO",
    format="{time} {level} {message}",
)

# Verify required environment variables
required_env_vars = ["CLIENT_ID", "CLIENT_SECRET"]
missing_vars = [var for var in required_env_vars if not os.getenv(var)]
if missing_vars:
    logger.error(f"Missing required environment variables: {', '.join(missing_vars)}")
    raise RuntimeError(f"Please set the following environment variables: {', '.join(missing_vars)}")

# Initialize FastAPI app
app = FastAPI(
    title="Spotify Search API",
    description="A simplified FastAPI service for searching Spotify content",
    version="1.0.0",
    docs_url="/",
)

# Initialize Spotify client
sp = Spotify(
    auth_manager=SpotifyClientCredentials(
        client_id=os.getenv("CLIENT_ID"),
        client_secret=os.getenv("CLIENT_SECRET"),
    )
)

# Define valid search types
class SearchType(str, Enum):
    track = "track"
    album = "album"
    playlist = "playlist"

# Define response models
class SpotifyItem(BaseModel):
    name: str
    uri: str

class SearchResponse(BaseModel):
    results: List[SpotifyItem]
    total: int

@app.get("/search", response_model=SearchResponse)
async def search(
    query: str,
    type: SearchType,
    limit: int = 5
) -> SearchResponse:
    """
    Search for content on Spotify and return simplified results with name and URI.
    
    Args:
        query (str): Search query string
        type (SearchType): Type of content to search for (track, album, or playlist)
        limit (int): Number of results to return (default: 5, max: 50)
        
    Returns:
        SearchResponse: Contains a list of items with name and URI, plus total count
    """
    logger.info(f"Searching for {type} with query: {query}, limit: {limit}")
    
    try:
        # Ensure limit is within bounds
        limit = min(max(1, limit), 50)
        
        # Clean up query - replace underscores with spaces
        query = query.replace("_", " ")
        
        # Perform search
        results = sp.search(
            q=query,
            type=type.value,
            limit=limit,
            market="US"  # Add market parameter for better results
        )
        
        # Validate response structure
        if not results:
            logger.warning("Search returned no results")
            return SearchResponse(results=[], total=0)
            
        # Extract the relevant section based on type (Spotify adds 's' to the type)
        result_key = f"{type.value}s"
        if result_key not in results:
            logger.error(f"Unexpected API response structure. Missing key: {result_key}")
            return SearchResponse(results=[], total=0)
        
        # Extract items safely
        items = results[result_key].get('items', [])
        if not items:
            logger.info(f"No {type.value}s found for query: {query}")
            return SearchResponse(results=[], total=0)
        
        # Extract items and simplify to name and URI only
        simplified_results = []
        for item in items:
            if isinstance(item, dict) and 'name' in item and 'uri' in item:
                simplified_results.append(
                    SpotifyItem(
                        name=item['name'],
                        uri=item['uri']
                    )
                )
        
        total = len(simplified_results)
        logger.info(f"Found {total} {type.value} results")
        return SearchResponse(results=simplified_results, total=total)
        
    except Exception as e:
        logger.error(f"Error processing search request: {str(e)}", exc_info=True)
        # Return empty results instead of error
        return SearchResponse(results=[], total=0)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)