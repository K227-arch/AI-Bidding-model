"""
SAM.gov scraper for government bid opportunities.
"""
import re
import json
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from loguru import logger

from .base_scraper import BaseScraper, BidOpportunity

class SAMGovScraper(BaseScraper):
    """Scraper for SAM.gov opportunities."""
    
    def __init__(self):
        super().__init__("SAM.gov")
        self.base_url = "https://sam.gov"
        self.api_url = "https://api.sam.gov/prod/opportunities/v2/search"
        
    def search_opportunities(self, keywords: List[str], days_back: int = 7) -> List[BidOpportunity]:
        """Search for opportunities on SAM.gov."""
        opportunities = []
        
        # Calculate date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=days_back)
        
        for keyword in keywords:
            logger.info(f"Searching SAM.gov for keyword: {keyword}")
            
            # Search parameters
            params = {
                'limit': 100,
                'offset': 0,
                'postedFrom': start_date.strftime('%m/%d/%Y'),
                'postedTo': end_date.strftime('%m/%d/%Y'),
                'ptype': 'o,k,r',  # Opportunities, K-sols, RFIs
                'q': keyword,
                'sort': '-modifiedOn'
            }
            
            # Make API request
            response = self._make_request(self.api_url, params=params)
            if not response:
                continue
                
            try:
                data = response.json()
                opportunities.extend(self._parse_api_response(data, keyword))
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse SAM.gov API response: {e}")
                continue
                
        # Remove duplicates and return
        unique_opportunities = self._remove_duplicates(opportunities)
        logger.info(f"Found {len(unique_opportunities)} unique opportunities from SAM.gov")
        return unique_opportunities
    
    def _parse_api_response(self, data: Dict[str, Any], keyword: str) -> List[BidOpportunity]:
        """Parse SAM.gov API response into BidOpportunity objects."""
        opportunities = []
        
        if 'opportunitiesData' not in data:
            return opportunities
            
        for item in data['opportunitiesData']:
            try:
                # Extract basic information
                title = item.get('title', 'No Title')
                description = item.get('description', 'No Description')
                agency = item.get('organizationType', 'Unknown Agency')
                opportunity_id = item.get('noticeId', '')
                
                # Parse dates
                due_date = self._parse_date(item.get('responseDeadLine', ''))
                if not due_date:
                    continue  # Skip if no valid due date
                    
                # Extract NAICS codes
                naics_codes = []
                if 'naicsCode' in item:
                    naics_codes = [str(item['naicsCode'])]
                    
                # Extract estimated value
                estimated_value = None
                if 'awardAmount' in item:
                    try:
                        estimated_value = float(item['awardAmount'])
                    except (ValueError, TypeError):
                        pass
                
                # Create opportunity
                opportunity = BidOpportunity(
                    title=title,
                    description=description,
                    agency=agency,
                    opportunity_id=opportunity_id,
                    due_date=due_date,
                    estimated_value=estimated_value,
                    naics_codes=naics_codes,
                    url=f"{self.base_url}/opp/{opportunity_id}",
                    source="SAM.gov"
                )
                
                opportunities.append(opportunity)
                
            except Exception as e:
                logger.warning(f"Failed to parse opportunity: {e}")
                continue
                
        return opportunities
    
    def _parse_date(self, date_str: str) -> Optional[datetime]:
        """Parse date string into datetime object."""
        if not date_str:
            return None
            
        # Common date formats in SAM.gov
        date_formats = [
            '%Y-%m-%dT%H:%M:%S.%fZ',
            '%Y-%m-%dT%H:%M:%SZ',
            '%Y-%m-%d',
            '%m/%d/%Y',
            '%m/%d/%Y %H:%M:%S'
        ]
        
        for fmt in date_formats:
            try:
                return datetime.strptime(date_str, fmt)
            except ValueError:
                continue
                
        logger.warning(f"Could not parse date: {date_str}")
        return None
    
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
        url = f"{self.api_url}/{opportunity_id}"
        response = self._make_request(url)
        
        if not response:
            return None
            
        try:
            data = response.json()
            if 'opportunityData' in data:
                return self._parse_api_response({'opportunitiesData': [data['opportunityData']]}, '')[0]
        except (json.JSONDecodeError, KeyError, IndexError) as e:
            logger.error(f"Failed to get opportunity details: {e}")
            
        return None

