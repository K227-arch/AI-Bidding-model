"""
Additional scrapers for international remote jobs and Ugandan jobs.
"""
from typing import List, Optional
from datetime import datetime, timedelta
from loguru import logger

from .base_scraper import BaseScraper, BidOpportunity


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