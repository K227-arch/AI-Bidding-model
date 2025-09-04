"""
FBO.gov scraper for government bid opportunities.
"""
import re
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from loguru import logger

from .base_scraper import BaseScraper, BidOpportunity

class FBOScraper(BaseScraper):
    """Scraper for FBO.gov opportunities."""
    
    def __init__(self):
        super().__init__("FBO.gov")
        self.base_url = "https://www.fbo.gov"
        self.search_url = "https://www.fbo.gov/index.php"
        
    def search_opportunities(self, keywords: List[str], days_back: int = 7) -> List[BidOpportunity]:
        """Search for opportunities on FBO.gov."""
        opportunities = []
        
        for keyword in keywords:
            logger.info(f"Searching FBO.gov for keyword: {keyword}")
            
            # FBO.gov search parameters
            params = {
                's': 'opportunity',
                'mode': 'list',
                'tab': 'list',
                'q': keyword,
                'postedFrom': (datetime.now() - timedelta(days=days_back)).strftime('%m/%d/%Y'),
                'postedTo': datetime.now().strftime('%m/%d/%Y')
            }
            
            response = self._make_request(self.search_url, params=params)
            if not response:
                continue
                
            try:
                soup = BeautifulSoup(response.content, 'html.parser')
                opportunities.extend(self._parse_search_results(soup, keyword))
            except Exception as e:
                logger.error(f"Failed to parse FBO.gov search results: {e}")
                continue
                
        # Remove duplicates and return
        unique_opportunities = self._remove_duplicates(opportunities)
        logger.info(f"Found {len(unique_opportunities)} unique opportunities from FBO.gov")
        return unique_opportunities
    
    def _parse_search_results(self, soup: BeautifulSoup, keyword: str) -> List[BidOpportunity]:
        """Parse FBO.gov search results."""
        opportunities = []
        
        # Find opportunity listings
        listings = soup.find_all('div', class_='list-item')
        
        for listing in listings:
            try:
                # Extract title and link
                title_elem = listing.find('a', class_='list-title')
                if not title_elem:
                    continue
                    
                title = title_elem.get_text(strip=True)
                link = title_elem.get('href', '')
                if link.startswith('/'):
                    link = self.base_url + link
                
                # Extract opportunity ID from link
                opportunity_id = self._extract_opportunity_id(link)
                
                # Extract agency
                agency_elem = listing.find('div', class_='agency')
                agency = agency_elem.get_text(strip=True) if agency_elem else 'Unknown Agency'
                
                # Extract due date
                due_date_elem = listing.find('div', class_='due-date')
                due_date = self._parse_fbo_date(due_date_elem.get_text(strip=True)) if due_date_elem else None
                
                if not due_date:
                    continue  # Skip if no valid due date
                
                # Extract description (first few lines)
                desc_elem = listing.find('div', class_='description')
                description = desc_elem.get_text(strip=True)[:500] if desc_elem else 'No description available'
                
                # Extract NAICS codes
                naics_codes = self._extract_naics_codes(description)
                
                # Create opportunity
                opportunity = BidOpportunity(
                    title=title,
                    description=description,
                    agency=agency,
                    opportunity_id=opportunity_id,
                    due_date=due_date,
                    naics_codes=naics_codes,
                    url=link,
                    source="FBO.gov"
                )
                
                opportunities.append(opportunity)
                
            except Exception as e:
                logger.warning(f"Failed to parse FBO listing: {e}")
                continue
                
        return opportunities
    
    def _extract_opportunity_id(self, url: str) -> str:
        """Extract opportunity ID from FBO URL."""
        # FBO URLs typically contain opportunity IDs
        match = re.search(r'/([A-Z0-9-]+)/?$', url)
        return match.group(1) if match else url.split('/')[-1]
    
    def _parse_fbo_date(self, date_str: str) -> Optional[datetime]:
        """Parse FBO.gov date format."""
        if not date_str:
            return None
            
        # Common FBO date formats
        date_formats = [
            '%m/%d/%Y',
            '%m/%d/%y',
            '%Y-%m-%d',
            '%B %d, %Y',
            '%b %d, %Y'
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
                
        logger.warning(f"Could not parse FBO date: {date_str}")
        return None
    
    def _extract_naics_codes(self, text: str) -> List[str]:
        """Extract NAICS codes from text."""
        naics_pattern = r'NAICS[:\s]*(\d{6})'
        matches = re.findall(naics_pattern, text, re.IGNORECASE)
        return matches
    
    def _remove_duplicates(self, opportunities: List[BidOpportunity]) -> List[BidOpportunity]:
        """Remove duplicate opportunities based on opportunity_id."""
        seen_ids = set()
        unique_opportunities = []
        
        for opp in opportunities:
            if opp.opportunity_id not in seen_ids:
                seen_ids.add(opp.opportunity_id)
                unique_opportunities.append(opp)
                
        return unique_opportunities
    
    def get_opportunity_details(self, opportunity_id: str) -> Optional[BidOpportunity]:
        """Get detailed information about a specific opportunity."""
        url = f"{self.base_url}/index.php?tab=opportunity&mode=form&id={opportunity_id}"
        response = self._make_request(url)
        
        if not response:
            return None
            
        try:
            soup = BeautifulSoup(response.content, 'html.parser')
            
            # Extract detailed information
            title_elem = soup.find('h1', class_='opportunity-title')
            title = title_elem.get_text(strip=True) if title_elem else 'No Title'
            
            desc_elem = soup.find('div', class_='opportunity-description')
            description = desc_elem.get_text(strip=True) if desc_elem else 'No Description'
            
            agency_elem = soup.find('div', class_='agency-info')
            agency = agency_elem.get_text(strip=True) if agency_elem else 'Unknown Agency'
            
            # Extract due date
            due_date_elem = soup.find('span', class_='due-date')
            due_date = self._parse_fbo_date(due_date_elem.get_text(strip=True)) if due_date_elem else None
            
            # Extract NAICS codes
            naics_codes = self._extract_naics_codes(description)
            
            return BidOpportunity(
                title=title,
                description=description,
                agency=agency,
                opportunity_id=opportunity_id,
                due_date=due_date,
                naics_codes=naics_codes,
                url=url,
                source="FBO.gov"
            )
            
        except Exception as e:
            logger.error(f"Failed to get FBO opportunity details: {e}")
            return None

