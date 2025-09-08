"""
Additional scrapers for international remote jobs and Ugandan jobs.
"""
from typing import List, Optional
from datetime import datetime, timedelta
from loguru import logger

from .base_scraper import BaseScraper, BidOpportunity
from bs4 import BeautifulSoup
from urllib.parse import urljoin, quote
import re
import json


class RemotiveScraper(BaseScraper):
    """Scraper for Remotive remote jobs (international). Uses public API.
    Notes: This fetches by keyword and maps jobs to BidOpportunity.
    """
    def __init__(self):
        super().__init__("Remotive (Remote Jobs)")
        # Common API endpoint
        self.api_url = "https://remotive.com/api/remote-jobs"

    def search_opportunities(self, keywords: List[str], days_back: int = 7) -> List[BidOpportunity]:
        opportunities: List[BidOpportunity] = []
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)

        # Use a subset of keywords to avoid excessive requests
        used_keywords = keywords[:8] if len(keywords) > 8 else keywords

        for kw in used_keywords:
            try:
                logger.info(f"Searching Remotive for keyword: {kw}")
                resp = self._make_request(self.api_url, params={"search": kw})
                if not resp:
                    continue
                data = resp.json() or {}
                jobs = data.get("jobs", [])
                for job in jobs:
                    try:
                        pub = job.get("publication_date") or job.get("created_at")
                        # publication_date format example: '2025-08-05T10:20:30'
                        try:
                            published_at = datetime.fromisoformat(pub.replace("Z", "+00:00")) if pub else end_date
                        except Exception:
                            published_at = end_date
                        if published_at < start_date:
                            continue
                        opp = BidOpportunity(
                            title=job.get("title") or "Remote Job",
                            description=(job.get("description") or "").strip()[:500] or (job.get("category") or "")[:500],
                            agency=job.get("company_name") or "Remotive Employer",
                            opportunity_id=str(job.get("id") or job.get("slug") or f"remotive-{int(published_at.timestamp())}"),
                            due_date=published_at + timedelta(days=14),
                            estimated_value=None,
                            naics_codes=[],
                            url=job.get("url") or job.get("job_url") or "",
                            source="Remotive"
                        )
                        opportunities.append(opp)
                    except Exception as e:
                        logger.debug(f"Skip Remotive job due to parse error: {e}")
                        continue
            except Exception as e:
                logger.warning(f"Failed Remotive request for keyword '{kw}': {e}")
                continue

        # Filter by keywords presence in title/description for relevance
        return self.filter_relevant_opportunities(opportunities, used_keywords)

    def get_opportunity_details(self, opportunity_id: str) -> Optional[BidOpportunity]:
        # Remotive API does not provide a direct job-by-id lookup in this minimal implementation
        return None


class RemoteOKScraper(BaseScraper):
    """Scraper for RemoteOK jobs (international). Uses public API and filters locally by keywords."""
    def __init__(self):
        super().__init__("RemoteOK (Remote Jobs)")
        self.api_url = "https://remoteok.com/api"

    def search_opportunities(self, keywords: List[str], days_back: int = 7) -> List[BidOpportunity]:
        opportunities: List[BidOpportunity] = []
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        try:
            logger.info("Fetching RemoteOK API feed")
            resp = self._make_request(self.api_url)
            if not resp:
                return []
            data = resp.json()
            # First element can be metadata; jobs are dicts with 'id'
            for item in data:
                if not isinstance(item, dict) or "id" not in item:
                    continue
                try:
                    date_str = item.get("date") or item.get("created_at")
                    try:
                        published_at = datetime.fromisoformat(date_str.replace("Z", "+00:00")) if date_str else end_date
                    except Exception:
                        published_at = end_date
                    if published_at < start_date:
                        continue
                    title = item.get("position") or item.get("title") or "Remote Job"
                    company = item.get("company") or "RemoteOK Employer"
                    description = (item.get("description") or "").strip()
                    tags = item.get("tags") or []
                    url = item.get("url") or ""
                    opp = BidOpportunity(
                        title=title,
                        description=(description[:500] if description else " ") + (" Tags: " + ",".join(tags) if tags else ""),
                        agency=company,
                        opportunity_id=str(item.get("id")),
                        due_date=published_at + timedelta(days=14),
                        estimated_value=None,
                        naics_codes=[],
                        url=url,
                        source="RemoteOK"
                    )
                    opportunities.append(opp)
                except Exception as e:
                    logger.debug(f"Skip RemoteOK item due to parse error: {e}")
                    continue
        except Exception as e:
            logger.warning(f"Failed to fetch RemoteOK feed: {e}")
            return []

        # Filter by provided keywords for relevance
        used_keywords = keywords[:8] if len(keywords) > 8 else keywords
        return self.filter_relevant_opportunities(opportunities, used_keywords)

    def get_opportunity_details(self, opportunity_id: str) -> Optional[BidOpportunity]:
        return None


class UgandaSampleScraper(BaseScraper):
    """Seed scraper returning sample Ugandan jobs and tenders.
    This provides immediate coverage without relying on brittle HTML selectors.
    """
    def __init__(self):
        super().__init__("Uganda (Sample Jobs & Tenders)")

    def search_opportunities(self, keywords: List[str], days_back: int = 7) -> List[BidOpportunity]:
        logger.info("Generating sample Uganda opportunities")
        now = datetime.utcnow()
        samples: List[BidOpportunity] = [
            BidOpportunity(
                title="ICT Support Specialist (Kampala, Remote-First)",
                description="Provide IT support, network administration, and helpdesk services for a distributed team in Uganda.",
                agency="Uganda Tech Services Ltd.",
                opportunity_id="UG-ICT-{}".format(now.strftime("%Y%m%d%H%M%S")),
                due_date=now + timedelta(days=21),
                estimated_value=None,
                naics_codes=[],
                url="https://example.ug/jobs/ict-support",
                source="Uganda Sample"
            ),
            BidOpportunity(
                title="Government Tender: Network Upgrade for Municipal Offices",
                description="Supply and install network equipment, secure Wi-Fi, and provide maintenance SLA for municipal offices.",
                agency="Kampala Capital City Authority",
                opportunity_id="UG-TENDER-NET-{}".format(now.strftime("%Y%m%d%H%M%S")),
                due_date=now + timedelta(days=28),
                estimated_value=None,
                naics_codes=["541512"],
                url="https://example.ug/tenders/network-upgrade",
                source="Uganda Sample"
            ),
            BidOpportunity(
                title="Software Developer - Public Health Reporting System",
                description="Build and maintain a reporting platform with data analytics dashboards for regional health centers.",
                agency="Ministry of Health Uganda",
                opportunity_id="UG-SW-{}".format(now.strftime("%Y%m%d%H%M%S")),
                due_date=now + timedelta(days=30),
                estimated_value=None,
                naics_codes=["541511"],
                url="https://example.ug/jobs/health-software",
                source="Uganda Sample"
            ),
        ]
        # Filter against keywords for relevance
        return self.filter_relevant_opportunities(samples, keywords)

    def get_opportunity_details(self, opportunity_id: str) -> Optional[BidOpportunity]:
        return None


class EGPUgandaScraper(BaseScraper):
    """Scraper for Uganda's e-GP bid notices (https://egpuganda.go.ug/bid-notices).
    Parses the listing page and extracts recent notices, filtering by keywords.
    """
    def __init__(self):
        super().__init__("EGP Uganda (Bid Notices)")
        self.base_url = "https://egpuganda.go.ug"
        self.listing_url = "https://egpuganda.go.ug/bid-notices"

    def search_opportunities(self, keywords: List[str], days_back: int = 7) -> List[BidOpportunity]:
        opportunities: List[BidOpportunity] = []
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)

        resp = self._make_request(self.listing_url)
        if not resp:
            return []
        try:
            soup = BeautifulSoup(resp.content, "html.parser")
            links = []
            # Collect candidate links
            for a in soup.find_all("a", href=True):
                href = a["href"].strip()
                text = (a.get_text(strip=True) or "")
                if not href:
                    continue
                # Consider links that point to bid-notices detail pages
                if "/bid-notices" in href or "/notice" in href or href.startswith("/bid/"):
                    links.append((a, href, text))
            seen_urls = set()
            for a, href, text in links:
                url = urljoin(self.base_url, href)
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                # Try to infer a date from nearby text
                context = " ".join(
                    [text]
                    + [s.get_text(" ", strip=True) for s in a.parent.find_all(recursive=False)[:5]]
                ) if a and a.parent else text
                date_found = None
                for m in re.findall(r"(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4})", context):
                    try:
                        if "/" in m:
                            parts = m.split("/")
                            day_first = True if int(parts[0]) > 12 else False
                            date_found = datetime.strptime(m, "%d/%m/%Y" if day_first else "%m/%d/%Y")
                        else:
                            date_found = datetime.strptime(m, "%Y-%m-%d")
                        break
                    except Exception:
                        continue
                published_at = date_found or end_date
                if published_at < start_date:
                    continue

                title = text or "Bid Notice"
                description = context[:500] if context else title
                opp = BidOpportunity(
                    title=title,
                    description=description,
                    agency="EGP Uganda",
                    opportunity_id=f"egp-ug-{abs(hash(url))}",
                    due_date=published_at + timedelta(days=21),
                    estimated_value=None,
                    naics_codes=[],
                    url=url,
                    source="EGP Uganda"
                )
                opportunities.append(opp)
        except Exception as e:
            logger.warning(f"Failed to parse EGP Uganda listing: {e}")
            return []

        # Filter for relevance
        used_keywords = keywords[:10] if len(keywords) > 10 else keywords
        return self.filter_relevant_opportunities(opportunities, used_keywords)

    def get_opportunity_details(self, opportunity_id: str) -> Optional[BidOpportunity]:
        return None


class UpworkScraper(BaseScraper):
    """Lightweight scraper for Upwork job search results.
    Note: Upwork may throttle or require JS; we attempt best-effort HTML parsing.
    """
    def __init__(self):
        super().__init__("Upwork (Freelance Jobs)")
        self.base_url = "https://www.upwork.com"
        self.search_url = "https://www.upwork.com/ab/jobs/search/"

    def search_opportunities(self, keywords: List[str], days_back: int = 7) -> List[BidOpportunity]:
        opportunities: List[BidOpportunity] = []
        end_date = datetime.utcnow()
        used_keywords = keywords[:4] if len(keywords) > 4 else keywords
        seen_urls = set()

        for kw in used_keywords:
            try:
                resp = self._make_request(self.search_url, params={"q": kw, "sort": "recency"})
                if not resp:
                    continue
                soup = BeautifulSoup(resp.content, "html.parser")
                # Find job tiles
                anchors = soup.find_all("a", href=True)
                for a in anchors:
                    href = a["href"].strip()
                    if not href or not href.startswith("/jobs/"):
                        continue
                    url = urljoin(self.base_url, href)
                    if url in seen_urls:
                        continue
                    seen_urls.add(url)
                    title = a.get_text(strip=True) or f"Upwork Job: {kw}"
                    # Try to get nearby description snippet
                    parent_text = a.find_parent().get_text(" ", strip=True)[:500] if a.find_parent() else title
                    description = parent_text or title

                    opp = BidOpportunity(
                        title=title,
                        description=description,
                        agency="Upwork Client",
                        opportunity_id=f"upwork-{abs(hash(url))}",
                        due_date=end_date + timedelta(days=14),
                        estimated_value=None,
                        naics_codes=[],
                        url=url,
                        source="Upwork"
                    )
                    opportunities.append(opp)
            except Exception as e:
                logger.debug(f"Upwork parse issue for '{kw}': {e}")
                continue

        return self.filter_relevant_opportunities(opportunities, used_keywords)

    def get_opportunity_details(self, opportunity_id: str) -> Optional[BidOpportunity]:
        return None


class UnitedNationsScraper(BaseScraper):
    """Scraper for United Nations bid opportunities, contracts, and jobs."""
    
    def __init__(self):
        super().__init__("United Nations Global Marketplace")
        # UNGM - United Nations Global Marketplace for procurement opportunities
        self.ungm_base_url = "https://www.ungm.org/Public/Notice"
        # UN Careers for job opportunities
        self.careers_base_url = "https://careers.un.org/lbw/jobsearch.aspx"
    
    def search_opportunities(self, keywords: List[str], days_back: int = 7) -> List[BidOpportunity]:
        """Search for bid opportunities from United Nations sources."""
        opportunities: List[BidOpportunity] = []
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)
        used_keywords = keywords[:5] if len(keywords) > 5 else keywords
        
        logger.info(f"UnitedNationsScraper.search_opportunities called with keywords: {keywords}")
        logger.info(f"UnitedNationsScraper is active and will return sample opportunities")
        logger.info(f"Current date: {end_date}, looking back to {start_date}")
        logger.info(f"Using keywords: {used_keywords}")
        
        # For testing purposes, generate sample UN opportunities with IT/ICT keywords
        # In a production environment, this would be replaced with actual web scraping
        sample_opportunities = [
            {
                "title": "Supply of IT Equipment for UN Offices",
                "description": "Procurement of laptops, desktops, and peripherals for UN offices worldwide. Includes software installation and IT support services. Keywords: information technology, computer systems, network infrastructure.",
                "agency": "United Nations Development Programme (UNDP)",
                "due_date": end_date + timedelta(days=14),
                "url": "https://www.ungm.org/Public/Notice/172458",
                "source": "UNGM"
            },
            {
                "title": "IT Consultant for Climate Change Data Systems",
                "description": "Development of information systems and software for climate change data collection and analysis. Requires expertise in database management and cloud computing. Keywords: information technology, software development, data systems.",
                "agency": "United Nations Environment Programme (UNEP)",
                "due_date": end_date + timedelta(days=21),
                "url": "https://www.ungm.org/Public/Notice/172459",
                "source": "UNGM"
            },
            {
                "title": "ICT Specialist - Sustainable Development",
                "description": "UN Career opportunity in New York: ICT specialist for sustainable development projects. Responsibilities include systems administration, network management, and software development. Keywords: information and communications technology, systems administration, network engineering.",
                "agency": "United Nations",
                "due_date": end_date + timedelta(days=30),
                "url": "https://careers.un.org/lbw/jobdetail.aspx?id=12345",
                "source": "UN Careers"
            },
            {
                "title": "Cybersecurity Program Manager",
                "description": "UN Career opportunity in Geneva: Program manager for coordinating cybersecurity initiatives and information security protocols across UN agencies. Keywords: cybersecurity, information security, IT security.",
                "agency": "United Nations Office for the Coordination of Humanitarian Affairs (OCHA)",
                "due_date": end_date + timedelta(days=14),
                "url": "https://careers.un.org/lbw/jobdetail.aspx?id=12346",
                "source": "UN Careers"
            },
            {
                "title": "Software Development for Water Management Systems",
                "description": "Development of software applications and IT infrastructure for water treatment facilities monitoring in developing countries. Includes database design and mobile app development. Keywords: software engineering, mobile development, database administration.",
                "agency": "United Nations Children's Fund (UNICEF)",
                "due_date": end_date + timedelta(days=45),
                "url": "https://www.ungm.org/Public/Notice/172460",
                "source": "UNGM"
            }
        ]
        
        # For testing purposes, always return sample opportunities regardless of keywords
        # This ensures we can test the UI display of UN opportunities
        for opp_data in sample_opportunities:
            opp = BidOpportunity(
                title=opp_data["title"],
                description=opp_data["description"],
                agency=opp_data["agency"],
                opportunity_id=f"un-{abs(hash(opp_data['url'] or opp_data['title']))}",
                due_date=opp_data["due_date"],
                estimated_value=None,
                naics_codes=[],
                url=opp_data["url"],
                source="United Nations - " + opp_data["source"]
            )
            opportunities.append(opp)
        
        # In a real implementation, we would also try to scrape from the actual websites:
        # 1. Make requests to UNGM and parse notice items
        # 2. Make requests to UN Careers and parse job listings
        # However, for testing purposes, we're using sample data
        
        # Skip filtering and return all sample opportunities to ensure they appear in results
        logger.info(f"United Nations scraper returning {len(opportunities)} sample opportunities")
        return opportunities
    
    def get_opportunity_details(self, opportunity_id: str) -> Optional[BidOpportunity]:
        """Get detailed information about a specific UN opportunity."""
        return None


class NewVisionTendersScraper(BaseScraper):
    """Scraper for New Vision Uganda tenders (https://www.newvision.co.ug/opportunities/tenders).
    Parses the listing page and extracts recent tenders, filtering by keywords.
    """
    def __init__(self):
        super().__init__("New Vision (Tenders)")
        self.base_url = "https://www.newvision.co.ug"
        self.listing_url = "https://www.newvision.co.ug/opportunities/tenders"

    def search_opportunities(self, keywords: List[str], days_back: int = 7) -> List[BidOpportunity]:
        opportunities: List[BidOpportunity] = []
        end_date = datetime.utcnow()
        start_date = end_date - timedelta(days=days_back)

        resp = self._make_request(self.listing_url)
        if not resp:
            return []
        try:
            soup = BeautifulSoup(resp.content, "html.parser")
            seen_urls = set()

            # Strategy 1: Look for article cards typically used in news sites
            articles = soup.find_all(["article", "div"], attrs={"class": re.compile(r"(card|article|listing|post)", re.I)})
            candidates = []
            for art in articles:
                a = art.find("a", href=True)
                if not a:
                    continue
                href = a["href"].strip()
                if not href:
                    continue
                if any(seg in href for seg in ["/opportunities/tenders", "/opportunities", "/tenders"]):
                    candidates.append((a, art))

            # Fallback: any anchors on the page containing opportunities/tenders
            if not candidates:
                for a in soup.find_all("a", href=True):
                    href = a["href"].strip()
                    if any(seg in href for seg in ["/opportunities/tenders", "/opportunities", "/tenders"]):
                        candidates.append((a, a.parent))

            for a, container in candidates:
                href = a["href"].strip()
                url = urljoin(self.base_url, href)
                if url in seen_urls:
                    continue
                seen_urls.add(url)

                title = a.get_text(strip=True) or "Tender Opportunity"

                # Collect context text for description and date parsing
                context_nodes = []
                if container:
                    # Include container text and limited siblings
                    context_nodes.append(container.get_text(" ", strip=True))
                    parent = container.parent
                    if parent:
                        siblings = parent.find_all(recursive=False)
                        # Take up to first few siblings' text for context
                        for s in siblings[:6]:
                            try:
                                context_nodes.append(s.get_text(" ", strip=True))
                            except Exception:
                                continue
                context = " ".join([t for t in context_nodes if t])

                # Try to find a datetime from a <time> tag or text
                published_at = None
                time_tag = container.find("time") if container else None
                if time_tag and (time_tag.get("datetime") or time_tag.get_text(strip=True)):
                    t = time_tag.get("datetime") or time_tag.get_text(strip=True)
                    for fmt in ["%Y-%m-%d", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S", "%d/%m/%Y", "%m/%d/%Y", "%b %d, %Y", "%B %d, %Y"]:
                        try:
                            published_at = datetime.strptime(t, fmt)
                            break
                        except Exception:
                            continue

                if not published_at:
                    # Regex scan common date patterns in context
                    date_found = None
                    for m in re.findall(r"(\d{4}-\d{2}-\d{2}|\d{1,2}/\d{1,2}/\d{2,4}|[A-Za-z]{3,9}\s+\d{1,2},\s*\d{4})", context):
                        try:
                            if "/" in m:
                                parts = m.split("/")
                                day_first = True if int(parts[0]) > 12 else False
                                date_found = datetime.strptime(m, "%d/%m/%Y" if day_first else "%m/%d/%Y")
                            elif "," in m and any(mon in m for mon in ["Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec", "January", "February", "March", "April", "June", "July", "August", "September", "October", "November", "December"]):
                                # Handles formats like "Jan 02, 2025" or "January 2, 2025"
                                try:
                                    date_found = datetime.strptime(m, "%b %d, %Y")
                                except Exception:
                                    date_found = datetime.strptime(m, "%B %d, %Y")
                            else:
                                date_found = datetime.strptime(m, "%Y-%m-%d")
                            break
                        except Exception:
                            continue
                    published_at = date_found or end_date

                if published_at < start_date:
                    continue

                description = (context[:500] if context else title)
                opp = BidOpportunity(
                    title=title,
                    description=description,
                    agency="New Vision Uganda",
                    opportunity_id=f"newvision-{abs(hash(url))}",
                    due_date=published_at + timedelta(days=21),
                    estimated_value=None,
                    naics_codes=[],
                    url=url,
                    source="New Vision"
                )
                opportunities.append(opp)
        except Exception as e:
            logger.warning(f"Failed to parse New Vision tenders: {e}")
            return []

        used_keywords = keywords[:10] if len(keywords) > 10 else keywords
        return self.filter_relevant_opportunities(opportunities, used_keywords)

    def get_opportunity_details(self, opportunity_id: str) -> Optional[BidOpportunity]:
        return None