"""
Automated application submission system.
"""
import time
import json
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from loguru import logger
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.options import Options
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager

from scrapers import BidOpportunity
from ai import MatchResult

class ApplicationSubmitter:
    """Handles automated submission of bid applications."""
    
    def __init__(self, headless: bool = True):
        self.headless = headless
        self.driver = None
        self.submission_log = []
        
    def _setup_driver(self):
        """Setup Chrome WebDriver with appropriate options."""
        chrome_options = Options()
        
        if self.headless:
            chrome_options.add_argument("--headless")
        
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
        
        try:
            self.driver = webdriver.Chrome(
                ChromeDriverManager().install(),
                options=chrome_options
            )
            self.driver.implicitly_wait(10)
            logger.info("Chrome WebDriver initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize WebDriver: {e}")
            raise
    
    def submit_application(self, match_result: MatchResult, 
                          application_package: Dict[str, str],
                          auto_submit: bool = False) -> Dict[str, Any]:
        """Submit application for an opportunity."""
        
        if not auto_submit:
            logger.info(f"Auto-submit disabled. Application prepared for: {match_result.opportunity.title}")
            return {
                'status': 'prepared',
                'message': 'Application prepared but not submitted (auto_submit=False)',
                'opportunity_id': match_result.opportunity.opportunity_id
            }
        
        opportunity = match_result.opportunity
        
        try:
            if not self.driver:
                self._setup_driver()
            
            logger.info(f"Submitting application for: {opportunity.title}")
            
            # Navigate to opportunity page
            if not self._navigate_to_opportunity(opportunity):
                return {
                    'status': 'failed',
                    'message': 'Failed to navigate to opportunity page',
                    'opportunity_id': opportunity.opportunity_id
                }
            
            # Fill out application form
            submission_result = self._fill_application_form(application_package, opportunity)
            
            # Log submission
            self._log_submission(opportunity, submission_result)
            
            return submission_result
            
        except Exception as e:
            logger.error(f"Failed to submit application: {e}")
            return {
                'status': 'failed',
                'message': f'Submission failed: {str(e)}',
                'opportunity_id': opportunity.opportunity_id
            }
    
    def _navigate_to_opportunity(self, opportunity: BidOpportunity) -> bool:
        """Navigate to the opportunity submission page."""
        try:
            # Try different possible submission URLs
            submission_urls = [
                opportunity.url,
                f"{opportunity.url}/submit",
                f"{opportunity.url}/proposal",
                f"{opportunity.url}/response"
            ]
            
            for url in submission_urls:
                try:
                    logger.info(f"Trying to navigate to: {url}")
                    self.driver.get(url)
                    time.sleep(3)
                    
                    # Check if we're on a valid submission page
                    if self._is_submission_page():
                        logger.info(f"Successfully navigated to submission page: {url}")
                        return True
                        
                except Exception as e:
                    logger.warning(f"Failed to navigate to {url}: {e}")
                    continue
            
            logger.error("Could not find valid submission page")
            return False
            
        except Exception as e:
            logger.error(f"Navigation failed: {e}")
            return False
    
    def _is_submission_page(self) -> bool:
        """Check if current page is a submission form."""
        try:
            # Look for common submission form elements
            submission_indicators = [
                "submit", "proposal", "response", "application",
                "upload", "attach", "document"
            ]
            
            page_text = self.driver.page_source.lower()
            
            # Check for form elements
            form_elements = self.driver.find_elements(By.TAG_NAME, "form")
            if not form_elements:
                return False
            
            # Check for submission-related text
            for indicator in submission_indicators:
                if indicator in page_text:
                    return True
            
            return False
            
        except Exception:
            return False
    
    def _fill_application_form(self, application_package: Dict[str, str], 
                             opportunity: BidOpportunity) -> Dict[str, Any]:
        """Fill out the application form with provided content."""
        try:
            # Wait for form to load
            WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.TAG_NAME, "form"))
            )
            
            # Try to fill common form fields
            filled_fields = []
            
            # Company name
            if self._fill_field("company_name", application_package.get('company_name', '')):
                filled_fields.append("company_name")
            
            # Contact information
            if self._fill_field("contact_email", application_package.get('contact_email', '')):
                filled_fields.append("contact_email")
            
            # Executive summary
            if self._fill_textarea("executive_summary", application_package.get('executive_summary', '')):
                filled_fields.append("executive_summary")
            
            # Technical approach
            if self._fill_textarea("technical_approach", application_package.get('technical_approach', '')):
                filled_fields.append("technical_approach")
            
            # Past performance
            if self._fill_textarea("past_performance", application_package.get('past_performance', '')):
                filled_fields.append("past_performance")
            
            # Team qualifications
            if self._fill_textarea("team_qualifications", application_package.get('team_qualifications', '')):
                filled_fields.append("team_qualifications")
            
            # Upload documents if possible
            uploaded_files = self._upload_documents(application_package)
            
            # Submit form
            if self._submit_form():
                return {
                    'status': 'submitted',
                    'message': 'Application submitted successfully',
                    'filled_fields': filled_fields,
                    'uploaded_files': uploaded_files,
                    'opportunity_id': opportunity.opportunity_id,
                    'submission_time': datetime.now().isoformat()
                }
            else:
                return {
                    'status': 'failed',
                    'message': 'Failed to submit form',
                    'filled_fields': filled_fields,
                    'uploaded_files': uploaded_files,
                    'opportunity_id': opportunity.opportunity_id
                }
                
        except TimeoutException:
            return {
                'status': 'failed',
                'message': 'Form submission timed out',
                'opportunity_id': opportunity.opportunity_id
            }
        except Exception as e:
            return {
                'status': 'failed',
                'message': f'Form filling failed: {str(e)}',
                'opportunity_id': opportunity.opportunity_id
            }
    
    def _fill_field(self, field_name: str, value: str) -> bool:
        """Fill a form field with the given value."""
        if not value:
            return False
            
        try:
            # Try different selectors for the field
            selectors = [
                f"input[name='{field_name}']",
                f"input[id='{field_name}']",
                f"input[placeholder*='{field_name}']",
                f"#{field_name}",
                f".{field_name}"
            ]
            
            for selector in selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    element.clear()
                    element.send_keys(value)
                    logger.info(f"Filled field {field_name}")
                    return True
                except NoSuchElementException:
                    continue
            
            logger.warning(f"Could not find field: {field_name}")
            return False
            
        except Exception as e:
            logger.error(f"Failed to fill field {field_name}: {e}")
            return False
    
    def _fill_textarea(self, field_name: str, value: str) -> bool:
        """Fill a textarea with the given value."""
        if not value:
            return False
            
        try:
            # Try different selectors for textarea
            selectors = [
                f"textarea[name='{field_name}']",
                f"textarea[id='{field_name}']",
                f"textarea[placeholder*='{field_name}']",
                f"#{field_name}",
                f".{field_name}"
            ]
            
            for selector in selectors:
                try:
                    element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    element.clear()
                    element.send_keys(value)
                    logger.info(f"Filled textarea {field_name}")
                    return True
                except NoSuchElementException:
                    continue
            
            logger.warning(f"Could not find textarea: {field_name}")
            return False
            
        except Exception as e:
            logger.error(f"Failed to fill textarea {field_name}: {e}")
            return False
    
    def _upload_documents(self, application_package: Dict[str, str]) -> List[str]:
        """Upload documents if file upload fields are available."""
        uploaded_files = []
        
        try:
            # Look for file upload fields
            file_inputs = self.driver.find_elements(By.CSS_SELECTOR, "input[type='file']")
            
            for i, file_input in enumerate(file_inputs):
                try:
                    # Create temporary file for this section
                    temp_file = self._create_temp_file(application_package, i)
                    if temp_file:
                        file_input.send_keys(temp_file)
                        uploaded_files.append(temp_file)
                        logger.info(f"Uploaded file: {temp_file}")
                except Exception as e:
                    logger.warning(f"Failed to upload file {i}: {e}")
            
        except Exception as e:
            logger.error(f"File upload failed: {e}")
        
        return uploaded_files
    
    def _create_temp_file(self, application_package: Dict[str, str], index: int) -> Optional[str]:
        """Create a temporary file for upload."""
        try:
            temp_dir = Path("./temp_uploads")
            temp_dir.mkdir(exist_ok=True)
            
            # Get content based on index
            content_keys = ['executive_summary', 'technical_approach', 'past_performance', 'team_qualifications']
            if index < len(content_keys):
                content = application_package.get(content_keys[index], '')
                if content:
                    temp_file = temp_dir / f"{content_keys[index]}_{index}.txt"
                    with open(temp_file, 'w', encoding='utf-8') as f:
                        f.write(content)
                    return str(temp_file)
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to create temp file: {e}")
            return None
    
    def _submit_form(self) -> bool:
        """Submit the application form."""
        try:
            # Look for submit button
            submit_selectors = [
                "input[type='submit']",
                "button[type='submit']",
                "button:contains('Submit')",
                "button:contains('Send')",
                "button:contains('Apply')",
                ".submit-button",
                "#submit"
            ]
            
            for selector in submit_selectors:
                try:
                    submit_button = self.driver.find_element(By.CSS_SELECTOR, selector)
                    submit_button.click()
                    logger.info("Form submitted successfully")
                    return True
                except NoSuchElementException:
                    continue
            
            logger.warning("Could not find submit button")
            return False
            
        except Exception as e:
            logger.error(f"Form submission failed: {e}")
            return False
    
    def _log_submission(self, opportunity: BidOpportunity, result: Dict[str, Any]):
        """Log submission result."""
        log_entry = {
            'timestamp': datetime.now().isoformat(),
            'opportunity_id': opportunity.opportunity_id,
            'opportunity_title': opportunity.title,
            'agency': opportunity.agency,
            'status': result.get('status'),
            'message': result.get('message'),
            'filled_fields': result.get('filled_fields', []),
            'uploaded_files': result.get('uploaded_files', []),
            'opportunity_url': getattr(opportunity, 'url', None) or ''
        }
        
        self.submission_log.append(log_entry)
        
        # Save to file
        log_file = Path("./logs/submissions.json")
        log_file.parent.mkdir(exist_ok=True)
        
        with open(log_file, 'a', encoding='utf-8') as f:
            f.write(json.dumps(log_entry) + '\n')
    
    def get_submission_log(self) -> List[Dict[str, Any]]:
        """Get submission log."""
        return self.submission_log
    
    def close(self):
        """Close the WebDriver."""
        if self.driver:
            self.driver.quit()
            self.driver = None
            logger.info("WebDriver closed")
    
    def __enter__(self):
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
