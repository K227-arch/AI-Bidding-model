"""
Base scraper class for government bid opportunities.
"""
import time
import random
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime, timedelta
from loguru import logger
import requests
from fake_useragent import UserAgent

@dataclass
class BidOpportunity:
    """Data class representing a bid opportunity."""
    title: str
    description: str
    agency: str
    opportunity_id: str
    due_date: datetime
    estimated_value: Optional[float] = None
    naics_codes: List[str] = None
    keywords: List[str] = None
    url: str = ""
    source: str = ""
    
    def __post_init__(self):
        if self.naics_codes is None:
            self.naics_codes = []
        if self.keywords is None:
            self.keywords = []

class BaseScraper(ABC):
    """Base class for all bid scrapers."""
    
    def __init__(self, name: str):
        self.name = name
        self.session = requests.Session()
        self.ua = UserAgent()
        self._setup_session()
        
    def _setup_session(self):
        """Setup the requests session with headers and configuration."""
        self.session.headers.update({
            'User-Agent': self.ua.random,
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'Accept-Encoding': 'gzip, deflate',
            'Connection': 'keep-alive',
        })
        
    def _random_delay(self, min_delay: float = 1.0, max_delay: float = 3.0):
        """Add random delay to avoid being blocked."""
        delay = random.uniform(min_delay, max_delay)
        time.sleep(delay)
        
    def _make_request(self, url: str, **kwargs) -> Optional[requests.Response]:
        """Make a request with error handling and retry logic."""
        max_retries = 3
        for attempt in range(max_retries):
            try:
                self._random_delay()
                response = self.session.get(url, timeout=30, **kwargs)
                response.raise_for_status()
                return response
            except requests.RequestException as e:
                logger.warning(f"Request failed (attempt {attempt + 1}/{max_retries}): {e}")
                if attempt == max_retries - 1:
                    logger.error(f"Failed to fetch {url} after {max_retries} attempts")
                    return None
                time.sleep(2 ** attempt)  # Exponential backoff
        return None
    
    @abstractmethod
    def search_opportunities(self, keywords: List[str], days_back: int = 7) -> List[BidOpportunity]:
        """Search for bid opportunities matching the given keywords."""
        pass
    
    @abstractmethod
    def get_opportunity_details(self, opportunity_id: str) -> Optional[BidOpportunity]:
        """Get detailed information about a specific opportunity."""
        pass
    
    def filter_relevant_opportunities(self, opportunities: List[BidOpportunity], 
                                    target_keywords: List[str]) -> List[BidOpportunity]:
        """Filter opportunities based on relevance to target keywords."""
        relevant_opportunities = []
        
        for opp in opportunities:
            # Check if any target keywords appear in title or description
            text_to_search = f"{opp.title} {opp.description}".lower()
            keyword_matches = sum(1 for keyword in target_keywords 
                                if keyword.lower() in text_to_search)
            
            # Consider opportunity relevant if it matches at least one keyword
            if keyword_matches > 0:
                opp.keywords = [kw for kw in target_keywords 
                              if kw.lower() in text_to_search]
                relevant_opportunities.append(opp)
                
        logger.info(f"Filtered {len(opportunities)} opportunities to {len(relevant_opportunities)} relevant ones")
        return relevant_opportunities

