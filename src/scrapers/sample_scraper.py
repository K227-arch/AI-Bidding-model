"""
Sample scraper that provides mock opportunities for demonstration purposes.
"""
from typing import List
from datetime import datetime, timedelta
from loguru import logger

from .base_scraper import BaseScraper, BidOpportunity

class SampleScraper(BaseScraper):
    """Sample scraper that provides mock opportunities for demonstration."""
    
    def __init__(self):
        super().__init__("Sample Opportunities")
        
    def search_opportunities(self, keywords: List[str], days_back: int = 7) -> List[BidOpportunity]:
        """Generate sample opportunities for demonstration."""
        logger.info("Generating sample opportunities for demonstration")
        
        # Create sample opportunities
        opportunities = [
            BidOpportunity(
                title="Cybersecurity Assessment and Authorization Services",
                description="The Department of Defense requires comprehensive cybersecurity assessment and authorization services including security control assessment, continuous monitoring, and risk management framework implementation. Services must include vulnerability scanning, penetration testing, and compliance reporting.",
                agency="Department of Defense",
                opportunity_id="DOD-CYBER-2025-001",
                due_date=datetime.now() + timedelta(days=30),
                estimated_value=2500000.0,
                naics_codes=["541511", "541512"],
                url="https://sam.gov/opp/DOD-CYBER-2025-001",
                source="Sample Data"
            ),
            BidOpportunity(
                title="IT Infrastructure Modernization and Cloud Migration",
                description="The General Services Administration seeks a contractor to provide IT infrastructure modernization services including cloud migration, system administration, network security, and digital transformation consulting. Experience with AWS, Azure, and hybrid cloud environments required.",
                agency="General Services Administration",
                opportunity_id="GSA-IT-2025-002",
                due_date=datetime.now() + timedelta(days=45),
                estimated_value=1800000.0,
                naics_codes=["541511", "541512"],
                url="https://sam.gov/opp/GSA-IT-2025-002",
                source="Sample Data"
            ),
            BidOpportunity(
                title="Information Security Operations Center (SOC) Services",
                description="The Department of Homeland Security requires 24/7 Security Operations Center services including threat monitoring, incident response, security information and event management (SIEM), and cybersecurity consulting. Must have experience with Splunk, CrowdStrike, and other enterprise security tools.",
                agency="Department of Homeland Security",
                opportunity_id="DHS-SOC-2025-003",
                due_date=datetime.now() + timedelta(days=20),
                estimated_value=3200000.0,
                naics_codes=["541511", "541512"],
                url="https://sam.gov/opp/DHS-SOC-2025-003",
                source="Sample Data"
            ),
            BidOpportunity(
                title="Penetration Testing and Vulnerability Assessment",
                description="The Department of Veterans Affairs requires comprehensive penetration testing and vulnerability assessment services for their network infrastructure, web applications, and mobile applications. Services must include red team exercises, social engineering testing, and detailed remediation recommendations.",
                agency="Department of Veterans Affairs",
                opportunity_id="VA-PENTEST-2025-004",
                due_date=datetime.now() + timedelta(days=25),
                estimated_value=850000.0,
                naics_codes=["541511"],
                url="https://sam.gov/opp/VA-PENTEST-2025-004",
                source="Sample Data"
            ),
            BidOpportunity(
                title="Compliance and Risk Management Framework Implementation",
                description="The Department of Health and Human Services seeks a contractor to implement NIST Cybersecurity Framework, FISMA compliance, and risk management framework (RMF) processes. Must have experience with healthcare IT security requirements and HIPAA compliance.",
                agency="Department of Health and Human Services",
                opportunity_id="HHS-COMPLIANCE-2025-005",
                due_date=datetime.now() + timedelta(days=35),
                estimated_value=1200000.0,
                naics_codes=["541511", "541512"],
                url="https://sam.gov/opp/HHS-COMPLIANCE-2025-005",
                source="Sample Data"
            ),
            BidOpportunity(
                title="Network Security and Firewall Management",
                description="The Department of Energy requires network security services including firewall management, intrusion detection and prevention, network monitoring, and security architecture design. Experience with Palo Alto Networks, Cisco, and enterprise network security required.",
                agency="Department of Energy",
                opportunity_id="DOE-NETSEC-2025-006",
                due_date=datetime.now() + timedelta(days=40),
                estimated_value=1500000.0,
                naics_codes=["541511", "541512"],
                url="https://sam.gov/opp/DOE-NETSEC-2025-006",
                source="Sample Data"
            ),
            BidOpportunity(
                title="Identity and Access Management (IAM) Implementation",
                description="The Department of Transportation seeks a contractor to implement enterprise identity and access management solutions including single sign-on (SSO), multi-factor authentication (MFA), privileged access management (PAM), and identity governance. Experience with Okta, Microsoft Azure AD, and SailPoint required.",
                agency="Department of Transportation",
                opportunity_id="DOT-IAM-2025-007",
                due_date=datetime.now() + timedelta(days=28),
                estimated_value=950000.0,
                naics_codes=["541511"],
                url="https://sam.gov/opp/DOT-IAM-2025-007",
                source="Sample Data"
            ),
            BidOpportunity(
                title="Software Development and Application Security",
                description="The Department of Agriculture requires software development services with a focus on application security, secure coding practices, and DevSecOps implementation. Must have experience with modern development frameworks, containerization, and application security testing.",
                agency="Department of Agriculture",
                opportunity_id="USDA-DEV-2025-008",
                due_date=datetime.now() + timedelta(days=50),
                estimated_value=2100000.0,
                naics_codes=["541511", "541512"],
                url="https://sam.gov/opp/USDA-DEV-2025-008",
                source="Sample Data"
            ),
            BidOpportunity(
                title="Incident Response and Digital Forensics",
                description="The Department of Justice requires incident response and digital forensics services including malware analysis, evidence collection, forensic imaging, and incident investigation. Must have experience with enterprise incident response tools and legal evidence handling procedures.",
                agency="Department of Justice",
                opportunity_id="DOJ-IR-2025-009",
                due_date=datetime.now() + timedelta(days=15),
                estimated_value=750000.0,
                naics_codes=["541511"],
                url="https://sam.gov/opp/DOJ-IR-2025-009",
                source="Sample Data"
            ),
            BidOpportunity(
                title="Cloud Security Architecture and Implementation",
                description="The Department of Commerce seeks a contractor to design and implement cloud security architecture for their AWS and Azure environments. Services must include cloud security assessment, configuration management, and compliance monitoring.",
                agency="Department of Commerce",
                opportunity_id="DOC-CLOUD-2025-010",
                due_date=datetime.now() + timedelta(days=42),
                estimated_value=1800000.0,
                naics_codes=["541511", "541512"],
                url="https://sam.gov/opp/DOC-CLOUD-2025-010",
                source="Sample Data"
            )
        ]
        
        # Filter opportunities based on keywords if provided
        if keywords:
            filtered_opportunities = []
            for opp in opportunities:
                text_to_search = f"{opp.title} {opp.description}".lower()
                if any(keyword.lower() in text_to_search for keyword in keywords):
                    filtered_opportunities.append(opp)
            opportunities = filtered_opportunities
        
        logger.info(f"Generated {len(opportunities)} sample opportunities")
        return opportunities
    
    def get_opportunity_details(self, opportunity_id: str) -> BidOpportunity:
        """Get details for a specific sample opportunity."""
        # For demo purposes, return the first opportunity
        opportunities = self.search_opportunities([])
        for opp in opportunities:
            if opp.opportunity_id == opportunity_id:
                return opp
        return None




