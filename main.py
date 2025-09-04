#!/usr/bin/env python3
"""
Main application runner for the AI bid application system.
"""
import argparse
import sys
import os
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime
from loguru import logger

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import settings
from scrapers import SAMGovScraper, FBOScraper, SampleScraper, RemotiveScraper, RemoteOKScraper, UgandaSampleScraper
from processors import DocumentProcessor
from ai import OpportunityMatcher
from applicators import ApplicationGenerator, ApplicationSubmitter

class BidApplicationSystem:
    """Main system for automated bid applications."""
    
    def __init__(self):
        self.setup_logging()
        self.document_processor = DocumentProcessor(settings.documents_folder)
        self.opportunity_matcher = OpportunityMatcher(settings.openai_api_key)
        self.application_generator = ApplicationGenerator(
            settings.openai_api_key, 
            settings.templates_folder
        )
        self.application_submitter = ApplicationSubmitter(headless=True)
        
        # Initialize scrapers
        self.scrapers = [
            SampleScraper(),  # Add sample scraper first for demo
            SAMGovScraper(),
            FBOScraper(),
            RemotiveScraper(),
            RemoteOKScraper(),
            UgandaSampleScraper(),
        ]
        
        logger.info("Bid Application System initialized")
    
    def setup_logging(self):
        """Setup logging configuration."""
        # Remove default logger
        logger.remove()
        
        # Add console logging
        logger.add(
            sys.stderr,
            level=settings.log_level,
            format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
        )
        
        # Add file logging
        log_file = Path(settings.log_file)
        log_file.parent.mkdir(exist_ok=True)
        
        logger.add(
            log_file,
            level=settings.log_level,
            format="{time:YYYY-MM-DD HH:mm:ss} | {level: <8} | {name}:{function}:{line} - {message}",
            rotation="10 MB",
            retention="30 days"
        )
    
    def run(self, days_back: int = 7, max_opportunities: int = 50, 
            auto_submit: bool = None, review_mode: bool = None) -> Dict[str, Any]:
        """Run the complete bid application process."""
        
        if auto_submit is None:
            auto_submit = settings.auto_submit
        if review_mode is None:
            review_mode = settings.review_mode
        
        logger.info(f"Starting bid application process (days_back={days_back}, max_opportunities={max_opportunities})")
        
        try:
            # Step 1: Process company documents
            logger.info("Step 1: Processing company documents...")
            processed_docs = self.document_processor.process_all_documents()
            
            if not processed_docs:
                logger.warning("No documents found. Please add company documents to the documents folder.")
                return {'status': 'warning', 'message': 'No documents found'}
            
            # Create company profile
            company_profile = self.document_processor.get_company_profile(processed_docs)
            self.opportunity_matcher.set_company_profile(company_profile)
            
            logger.info(f"Processed {len(processed_docs)} documents")
            logger.info(f"Company: {company_profile.get('company_name', 'Unknown')}")
            logger.info(f"Technical keywords: {len(company_profile.get('technical_keywords', []))}")
            
            # Step 2: Search for opportunities
            logger.info("Step 2: Searching for opportunities...")
            all_opportunities = []
            
            # Combine keywords
            search_keywords = settings.it_keywords + settings.cybersecurity_keywords
            
            for scraper in self.scrapers:
                try:
                    opportunities = scraper.search_opportunities(search_keywords, days_back)
                    all_opportunities.extend(opportunities)
                    logger.info(f"{scraper.name}: Found {len(opportunities)} opportunities")
                except Exception as e:
                    logger.error(f"Scraper {scraper.name} failed: {e}")
            
            if not all_opportunities:
                logger.warning("No opportunities found")
                return {'status': 'warning', 'message': 'No opportunities found'}
            
            # Remove duplicates and limit
            unique_opportunities = self._remove_duplicate_opportunities(all_opportunities)
            unique_opportunities = unique_opportunities[:max_opportunities]
            
            logger.info(f"Found {len(unique_opportunities)} unique opportunities")
            
            # Step 3: Match opportunities
            logger.info("Step 3: Matching opportunities with company capabilities...")
            match_results = self.opportunity_matcher.match_opportunities(unique_opportunities)
            
            # Filter for opportunities we should apply to
            applicable_opportunities = [result for result in match_results if result.should_apply]
            
            logger.info(f"Found {len(applicable_opportunities)} applicable opportunities")
            
            # Step 4: Generate applications
            logger.info("Step 4: Generating applications...")
            applications_generated = 0
            applications_submitted = 0
            
            for i, match_result in enumerate(applicable_opportunities[:settings.max_applications_per_day]):
                try:
                    logger.info(f"Processing opportunity {i+1}/{len(applicable_opportunities)}: {match_result.opportunity.title}")
                    
                    # Generate application
                    application_package = self.application_generator.generate_application(
                        match_result, company_profile, processed_docs
                    )
                    
                    # Save application package
                    output_folder = self.application_generator.save_application_package(application_package)
                    applications_generated += 1
                    
                    # Submit application if auto_submit is enabled
                    if auto_submit:
                        submission_result = self.application_submitter.submit_application(
                            match_result, application_package, auto_submit=True
                        )
                        
                        if submission_result.get('status') == 'submitted':
                            applications_submitted += 1
                            logger.info(f"Successfully submitted application for: {match_result.opportunity.title}")
                        else:
                            logger.warning(f"Failed to submit application: {submission_result.get('message')}")
                    else:
                        logger.info(f"Application prepared (auto_submit=False): {output_folder}")
                    
                    # Print summary for review
                    if review_mode:
                        summary = self.opportunity_matcher.generate_application_summary(match_result)
                        print(f"\n{summary}\n")
                        print("-" * 80)
                    
                except Exception as e:
                    logger.error(f"Failed to process opportunity {match_result.opportunity.title}: {e}")
                    continue
            
            # Step 5: Generate final report
            logger.info("Step 5: Generating final report...")
            report = self._generate_final_report(
                processed_docs, unique_opportunities, match_results, 
                applications_generated, applications_submitted
            )
            
            logger.info("Bid application process completed successfully")
            return report
            
        except Exception as e:
            logger.error(f"Bid application process failed: {e}")
            return {'status': 'error', 'message': str(e)}
        
        finally:
            # Cleanup
            self.application_submitter.close()
    
    def _remove_duplicate_opportunities(self, opportunities: List) -> List:
        """Remove duplicate opportunities based on opportunity_id."""
        seen_ids = set()
        unique_opportunities = []
        
        for opp in opportunities:
            if opp.opportunity_id not in seen_ids:
                seen_ids.add(opp.opportunity_id)
                unique_opportunities.append(opp)
        
        return unique_opportunities
    
    def _generate_final_report(self, processed_docs: List, opportunities: List, 
                             match_results: List, applications_generated: int, 
                             applications_submitted: int) -> Dict[str, Any]:
        """Generate final report of the process."""
        
        # Calculate statistics
        high_confidence_matches = len([r for r in match_results if r.confidence == 'High'])
        medium_confidence_matches = len([r for r in match_results if r.confidence == 'Medium'])
        low_confidence_matches = len([r for r in match_results if r.confidence == 'Low'])
        
        applicable_opportunities = [r for r in match_results if r.should_apply]
        
        report = {
            'status': 'success',
            'timestamp': datetime.now().isoformat(),
            'summary': {
                'documents_processed': len(processed_docs),
                'opportunities_found': len(opportunities),
                'opportunities_matched': len(match_results),
                'applications_generated': applications_generated,
                'applications_submitted': applications_submitted
            },
            'match_confidence': {
                'high': high_confidence_matches,
                'medium': medium_confidence_matches,
                'low': low_confidence_matches
            },
            'top_opportunities': [
                {
                    'title': r.opportunity.title,
                    'agency': r.opportunity.agency,
                    'match_score': r.match_score,
                    'confidence': r.confidence,
                    'due_date': str(r.opportunity.due_date),
                    'should_apply': r.should_apply
                }
                for r in applicable_opportunities[:10]
            ]
        }
        
        return report

def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="AI-powered system for finding and applying to government contracts"
    )
    
    parser.add_argument(
        "--days-back", 
        type=int, 
        default=7,
        help="Number of days back to search for opportunities (default: 7)"
    )
    
    parser.add_argument(
        "--max-opportunities", 
        type=int, 
        default=50,
        help="Maximum number of opportunities to process (default: 50)"
    )
    
    parser.add_argument(
        "--auto-submit", 
        action="store_true",
        help="Automatically submit applications (default: False)"
    )
    
    parser.add_argument(
        "--review-mode", 
        action="store_true",
        help="Show detailed review information (default: True)"
    )
    
    parser.add_argument(
        "--no-review", 
        action="store_true",
        help="Disable review mode"
    )
    
    parser.add_argument(
        "--config-check", 
        action="store_true",
        help="Check configuration and exit"
    )
    
    args = parser.parse_args()
    
    # Configuration check
    if args.config_check:
        print("Configuration Check:")
        print(f"OpenAI API Key: {'✓ Set' if settings.openai_api_key else '✗ Missing'}")
        print(f"Documents Folder: {settings.documents_folder}")
        print(f"Templates Folder: {settings.templates_folder}")
        print(f"Company Name: {settings.company_name}")
        print(f"IT Keywords: {len(settings.it_keywords)}")
        print(f"Cybersecurity Keywords: {len(settings.cybersecurity_keywords)}")
        return
    
    # Initialize and run system
    try:
        system = BidApplicationSystem()
        
        # Determine review mode
        review_mode = args.review_mode
        if args.no_review:
            review_mode = False
        
        # Run the system
        result = system.run(
            days_back=args.days_back,
            max_opportunities=args.max_opportunities,
            auto_submit=args.auto_submit,
            review_mode=review_mode
        )
        
        # Print final result
        if result.get('status') == 'success':
            print("\n" + "="*60)
            print("BID APPLICATION PROCESS COMPLETED SUCCESSFULLY")
            print("="*60)
            
            summary = result.get('summary', {})
            print(f"Documents Processed: {summary.get('documents_processed', 0)}")
            print(f"Opportunities Found: {summary.get('opportunities_found', 0)}")
            print(f"Opportunities Matched: {summary.get('opportunities_matched', 0)}")
            print(f"Applications Generated: {summary.get('applications_generated', 0)}")
            print(f"Applications Submitted: {summary.get('applications_submitted', 0)}")
            
            print("\nTop Opportunities:")
            for opp in result.get('top_opportunities', [])[:5]:
                print(f"  • {opp['title']} ({opp['agency']}) - Score: {opp['match_score']:.2f}")
        
        elif result.get('status') == 'warning':
            print(f"\nWARNING: {result.get('message')}")
        
        else:
            print(f"\nERROR: {result.get('message')}")
            sys.exit(1)
    
    except KeyboardInterrupt:
        print("\nProcess interrupted by user")
        sys.exit(1)
    
    except Exception as e:
        print(f"\nFatal error: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
