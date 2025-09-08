"""
Scrapers package for government bid opportunities.
"""
from .base_scraper import BaseScraper, BidOpportunity
from .sam_gov_scraper import SAMGovScraper
from .fbo_scraper import FBOScraper
from .sample_scraper import SampleScraper
from .extra_scrapers import RemotiveScraper, RemoteOKScraper, UgandaSampleScraper, EGPUgandaScraper, UpworkScraper, NewVisionTendersScraper, UnitedNationsScraper

__all__ = [
    "BaseScraper", "BidOpportunity",
    "SAMGovScraper", "FBOScraper", "SampleScraper",
    "RemotiveScraper", "RemoteOKScraper", "UgandaSampleScraper",
    "EGPUgandaScraper", "UpworkScraper", "NewVisionTendersScraper", "UnitedNationsScraper"
]
