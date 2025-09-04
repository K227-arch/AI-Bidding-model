"""
Application generator for creating bid proposals and applications.
"""
import os
import re
from typing import List, Dict, Any, Optional
from datetime import datetime
from pathlib import Path
from loguru import logger
import openai
from docx import Document
from docx.shared import Inches

from scrapers import BidOpportunity
from ai import MatchResult
from processors import ProcessedDocument

class ApplicationGenerator:
    """Generates bid applications and proposals."""
    
    def __init__(self, openai_api_key: str, templates_folder: str = "./templates"):
        self.openai_api_key = openai_api_key
        openai.api_key = openai_api_key
        self.templates_folder = Path(templates_folder)
        self.templates_folder.mkdir(exist_ok=True)
        
        # Create default templates if they don't exist
        self._create_default_templates()
    
    def _create_default_templates(self):
        """Create default application templates."""
        templates = {
            'cover_letter.txt': self._get_cover_letter_template(),
            'technical_approach.txt': self._get_technical_approach_template(),
            'past_performance.txt': self._get_past_performance_template(),
            'team_qualifications.txt': self._get_team_qualifications_template()
        }
        
        for filename, content in templates.items():
            template_path = self.templates_folder / filename
            if not template_path.exists():
                with open(template_path, 'w', encoding='utf-8') as f:
                    f.write(content)
    
    def generate_application(self, match_result: MatchResult, 
                           company_profile: Dict[str, Any],
                           processed_docs: List[ProcessedDocument]) -> Dict[str, str]:
        """Generate complete application package for an opportunity."""
        
        opportunity = match_result.opportunity
        
        logger.info(f"Generating application for: {opportunity.title}")
        
        # Generate different sections
        cover_letter = self._generate_cover_letter(match_result, company_profile)
        technical_approach = self._generate_technical_approach(match_result, company_profile)
        past_performance = self._generate_past_performance(match_result, processed_docs)
        team_qualifications = self._generate_team_qualifications(match_result, processed_docs)
        executive_summary = self._generate_executive_summary(match_result, company_profile)
        
        application_package = {
            'cover_letter': cover_letter,
            'technical_approach': technical_approach,
            'past_performance': past_performance,
            'team_qualifications': team_qualifications,
            'executive_summary': executive_summary,
            'opportunity_id': opportunity.opportunity_id,
            'opportunity_title': opportunity.title,
            'opportunity_agency': opportunity.agency,
            'generated_date': datetime.now().isoformat(),
            'company_name': company_profile.get('company_name') or '',
            'signatory_name': company_profile.get('signatory_name') or os.environ.get('SIGNATORY_NAME')
        }
        
        return application_package
    
    def _generate_cover_letter(self, match_result: MatchResult, 
                             company_profile: Dict[str, Any]) -> str:
        """Generate cover letter using AI."""
        opportunity = match_result.opportunity
        
        company_name = company_profile.get('company_name', 'Our Company')
        signatory = company_profile.get('signatory_name') or os.environ.get('SIGNATORY_NAME')
        signoff_instructions = f"End with a sign-off that includes exactly: 'Sincerely,' on one line, '{company_name}' on the next line" + (f", and '{signatory}' on the following line" if signatory else "") + "."
        
        prompt = f"""
        Write a professional cover letter for this government contracting opportunity.
        
        OPPORTUNITY DETAILS:
        Title: {opportunity.title}
        Agency: {opportunity.agency}
        Description: {opportunity.description[:1000]}
        Due Date: {opportunity.due_date}
        
        OUR COMPANY:
        Name: {company_name}
        Capabilities: {', '.join(company_profile.get('technical_keywords', [])[:10])}
        
        MATCHING KEYWORDS: {', '.join(match_result.matching_keywords)}
        
        Requirements:
        - Use the company name exactly as provided above and do not mention any other company names.
        - {signoff_instructions}
        
        Write a compelling cover letter that:
        1. Expresses strong interest in the opportunity
        2. Highlights relevant capabilities and experience
        3. Demonstrates understanding of the requirements
        4. Shows value proposition
        5. Is professional and government contracting appropriate
        
        Keep it concise (2-3 paragraphs) and professional.
        """
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert in government contracting and proposal writing."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=800,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Failed to generate cover letter: {e}")
            return self._get_fallback_cover_letter(opportunity, company_profile)
    
    def _generate_technical_approach(self, match_result: MatchResult, 
                                   company_profile: Dict[str, Any]) -> str:
        """Generate technical approach section."""
        opportunity = match_result.opportunity
        
        prompt = f"""
        Write a technical approach section for this government contracting opportunity.
        
        OPPORTUNITY DETAILS:
        Title: {opportunity.title}
        Description: {opportunity.description[:1500]}
        
        OUR CAPABILITIES:
        {company_profile.get('all_content', '')[:2000]}
        
        MATCHING KEYWORDS: {', '.join(match_result.matching_keywords)}
        
        Write a technical approach that:
        1. Demonstrates understanding of the technical requirements
        2. Outlines our methodology and approach
        3. Highlights relevant technical capabilities
        4. Shows innovation and best practices
        5. Addresses key technical challenges
        
        Structure it with clear sections and bullet points.
        """
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are a technical expert in IT and cybersecurity services."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1200,
                temperature=0.6
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Failed to generate technical approach: {e}")
            return self._get_fallback_technical_approach(opportunity)
    
    def _generate_past_performance(self, match_result: MatchResult, 
                                 processed_docs: List[ProcessedDocument]) -> str:
        """Generate past performance section."""
        opportunity = match_result.opportunity
        
        # Extract relevant experience from documents
        experience_content = ""
        for doc in processed_docs:
            if 'experience' in doc.sections:
                experience_content += doc.sections['experience'] + "\n\n"
        
        prompt = f"""
        Write a past performance section for this government contracting opportunity.
        
        OPPORTUNITY DETAILS:
        Title: {opportunity.title}
        Description: {opportunity.description[:1000]}
        
        OUR EXPERIENCE:
        {experience_content[:2000]}
        
        Write a past performance section that:
        1. Highlights relevant past projects and experience
        2. Shows successful delivery of similar services
        3. Demonstrates client satisfaction and results
        4. Includes specific metrics and outcomes
        5. Relates experience to current opportunity requirements
        
        If specific experience is limited, focus on transferable skills and capabilities.
        """
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert in government contracting and past performance documentation."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.6
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Failed to generate past performance: {e}")
            return self._get_fallback_past_performance()
    
    def _generate_team_qualifications(self, match_result: MatchResult, 
                                    processed_docs: List[ProcessedDocument]) -> str:
        """Generate team qualifications section."""
        opportunity = match_result.opportunity
        
        # Extract team information from documents
        team_content = ""
        for doc in processed_docs:
            if 'team' in doc.sections:
                team_content += doc.sections['team'] + "\n\n"
            if 'certifications' in doc.sections:
                team_content += doc.sections['certifications'] + "\n\n"
        
        prompt = f"""
        Write a team qualifications section for this government contracting opportunity.
        
        OPPORTUNITY DETAILS:
        Title: {opportunity.title}
        Description: {opportunity.description[:1000]}
        
        OUR TEAM:
        {team_content[:2000]}
        
        Write a team qualifications section that:
        1. Highlights key personnel and their qualifications
        2. Shows relevant certifications and credentials
        3. Demonstrates expertise in required areas
        4. Includes years of experience and specializations
        5. Shows team's ability to deliver the required services
        
        Focus on qualifications most relevant to the opportunity.
        """
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert in team qualifications and personnel documentation."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=1000,
                temperature=0.6
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Failed to generate team qualifications: {e}")
            return self._get_fallback_team_qualifications()
    
    def _generate_executive_summary(self, match_result: MatchResult, 
                                  company_profile: Dict[str, Any]) -> str:
        """Generate executive summary."""
        opportunity = match_result.opportunity
        
        prompt = f"""
        Write an executive summary for this government contracting opportunity.
        
        OPPORTUNITY DETAILS:
        Title: {opportunity.title}
        Agency: {opportunity.agency}
        Description: {opportunity.description[:1000]}
        
        OUR COMPANY:
        Name: {company_profile.get('company_name', 'Our Company')}
        Key Capabilities: {', '.join(company_profile.get('technical_keywords', [])[:8])}
        
        MATCH SCORE: {match_result.match_score:.2f}
        MATCHING KEYWORDS: {', '.join(match_result.matching_keywords)}
        
        Write an executive summary that:
        1. Clearly states our interest and qualifications
        2. Highlights our key value proposition
        3. Shows understanding of the opportunity
        4. Demonstrates our competitive advantages
        5. Is concise and compelling (1-2 paragraphs)
        """
        
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "You are an expert in executive summaries for government contracting."},
                    {"role": "user", "content": prompt}
                ],
                max_tokens=600,
                temperature=0.7
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"Failed to generate executive summary: {e}")
            return self._get_fallback_executive_summary(opportunity, company_profile)
    
    def save_application_package(self, application_package: Dict[str, str], 
                               output_folder: str = "./applications") -> str:
        """Save the generated application package to files."""
        # Normalize company details before saving
        company_profile = {
            'company_name': application_package.get('company_name') or '',
        }
        # Prefer company name from package metadata if present; fall back to env or leave empty
        if not company_profile['company_name']:
            company_profile['company_name'] = os.environ.get('COMPANY_NAME', '')
        company_profile['signatory_name'] = os.environ.get('SIGNATORY_NAME')
        
        for key in [
            'cover_letter', 'technical_approach', 'past_performance', 'team_qualifications', 'executive_summary'
        ]:
            if key in application_package and isinstance(application_package[key], str):
                application_package[key] = self._normalize_company_details(
                    application_package[key], company_profile
                )
        
        opportunity_id = application_package.get('opportunity_id', 'UNKNOWN')
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        folder_name = f"{opportunity_id}_{timestamp}"
        app_folder = Path(output_folder) / folder_name
        app_folder.mkdir(parents=True, exist_ok=True)
        
        # Save individual sections (skip metadata keys)
        skip_keys = {'opportunity_id', 'generated_date', 'opportunity_title', 'opportunity_agency', 'company_name', 'signatory_name'}
        for section_name, content in application_package.items():
            if section_name in skip_keys:
                continue
            
            file_path = app_folder / f"{section_name}.txt"
            with open(file_path, 'w', encoding='utf-8') as f:
                f.write(content)
        
        # Create combined document
        combined_path = app_folder / "complete_application.txt"
        with open(combined_path, 'w', encoding='utf-8') as f:
            f.write("GOVERNMENT CONTRACTING APPLICATION\n")
            f.write("=" * 50 + "\n\n")
            
            for section_name, content in application_package.items():
                if section_name in skip_keys:
                    continue
                
                f.write(f"{section_name.upper().replace('_', ' ')}\n")
                f.write("-" * 30 + "\n")
                f.write(content)
                f.write("\n\n")
        
        # Write metadata.json for history
        metadata = {
            'opportunity_id': application_package.get('opportunity_id'),
            'opportunity_title': application_package.get('opportunity_title'),
            'opportunity_agency': application_package.get('opportunity_agency'),
            'generated_date': application_package.get('generated_date'),
            'folder': str(app_folder)
        }
        with open(app_folder / 'metadata.json', 'w', encoding='utf-8') as mf:
            import json as _json
            mf.write(_json.dumps(metadata, ensure_ascii=False))
        
        logger.info(f"Application package saved to: {app_folder}")
        return str(app_folder)
    
    # Fallback templates
    def _get_fallback_cover_letter(self, opportunity: BidOpportunity, 
                                 company_profile: Dict[str, Any]) -> str:
        return f"""
Dear Contracting Officer,

We are pleased to submit our proposal for {opportunity.title} (Solicitation #{opportunity.opportunity_id}).

{company_profile.get('company_name', 'Our Company')} is a qualified provider of IT and cybersecurity services with extensive experience in government contracting. We are confident that our capabilities and approach make us an ideal partner for this opportunity.

We look forward to the opportunity to discuss our proposal and demonstrate how we can deliver exceptional value for {opportunity.agency}.

Sincerely,
{company_profile.get('company_name', 'Our Company')}
        """.strip()
    
    def _get_fallback_technical_approach(self, opportunity: BidOpportunity) -> str:
        return f"""
Technical Approach for {opportunity.title}

Our technical approach is based on industry best practices and proven methodologies:

1. Requirements Analysis and Planning
   - Comprehensive analysis of technical requirements
   - Development of detailed project plan
   - Risk assessment and mitigation strategies

2. Implementation Methodology
   - Agile development approach
   - Continuous integration and deployment
   - Quality assurance and testing protocols

3. Security and Compliance
   - Implementation of security best practices
   - Compliance with government standards
   - Regular security assessments and monitoring

4. Support and Maintenance
   - 24/7 support capabilities
   - Proactive monitoring and maintenance
   - Continuous improvement processes
        """.strip()
    
    def _get_fallback_past_performance(self) -> str:
        return """
Past Performance

Our company has successfully delivered IT and cybersecurity services to various clients, demonstrating our ability to:

- Meet project deadlines and budget requirements
- Deliver high-quality solutions that exceed expectations
- Maintain strong client relationships
- Adapt to changing requirements and technologies
        """.strip()
    
    def _get_fallback_team_qualifications(self) -> str:
        return """
Team Qualifications

Our team consists of highly qualified professionals with:

- Relevant technical certifications and credentials
- Extensive experience in IT and cybersecurity
- Strong track record in government contracting
- Commitment to continuous learning and development

We are confident that our team has the expertise and dedication necessary to successfully deliver this project.
        """.strip()
    
    def _get_fallback_executive_summary(self, opportunity: BidOpportunity, 
                                      company_profile: Dict[str, Any]) -> str:
        return f"""
Executive Summary

{company_profile.get('company_name', 'Our Company')} is pleased to submit our proposal for {opportunity.title}. We bring extensive experience in IT and cybersecurity services, along with a proven track record of successful government contracting.

Our approach combines technical excellence with deep understanding of government requirements, ensuring we deliver solutions that meet and exceed expectations. We are committed to providing exceptional value and building a long-term partnership with {opportunity.agency}.
        """.strip()
    
    # Template content
    def _get_cover_letter_template(self) -> str:
        return """Dear Contracting Officer,

We are pleased to submit our proposal for [OPPORTUNITY_TITLE] (Solicitation #[OPPORTUNITY_ID]).

[COMPANY_NAME] is a qualified provider of IT and cybersecurity services with extensive experience in government contracting. Our team brings [KEY_CAPABILITIES] to this opportunity.

We are confident that our approach and capabilities make us an ideal partner for this project. We look forward to the opportunity to discuss our proposal in detail.

Sincerely,
[COMPANY_NAME]
        """
    
    def _get_technical_approach_template(self) -> str:
        return """Technical Approach

1. Requirements Analysis
   - [SPECIFIC_APPROACH]

2. Implementation Methodology
   - [SPECIFIC_METHODOLOGY]

3. Quality Assurance
   - [QUALITY_PROCESSES]

4. Risk Management
   - [RISK_MITIGATION]
        """
    
    def _get_past_performance_template(self) -> str:
        return """Past Performance

Relevant Experience:
- [PROJECT_1]
- [PROJECT_2]
- [PROJECT_3]

Key Achievements:
- [ACHIEVEMENT_1]
- [ACHIEVEMENT_2]
        """
    
    def _get_team_qualifications_template(self) -> str:
        return """Team Qualifications

Key Personnel:
- [PERSON_1]: [QUALIFICATIONS]
- [PERSON_2]: [QUALIFICATIONS]

Certifications:
- [CERTIFICATION_1]
- [CERTIFICATION_2]
        """

    def _normalize_company_details(self, text: str, company_profile: Dict[str, Any]) -> str:
        """Ensure the correct company name and signatory are present and remove stale names."""
        if not text:
            return text
        company_name = company_profile.get('company_name') or os.environ.get('COMPANY_NAME') or 'Our Company'
        signatory = company_profile.get('signatory_name') or os.environ.get('SIGNATORY_NAME') or 'TWESIGYE KEITH'
        
        # Replace known stale names with the correct one
        stale_names = [
            'TechSecure Solutions',
            'Our Company'
        ]
        for stale in stale_names:
            if stale and stale != company_name:
                text = re.sub(rf"\b{re.escape(stale)}\b", company_name, text)
        
        # If this looks like a cover letter, enforce sign-off block
        lowered = text.lower()
        if 'sincerely' in lowered:
            # Ensure company name line after 'Sincerely,' and add signatory if present
            lines = text.splitlines()
            new_lines = []
            i = 0
            while i < len(lines):
                line = lines[i]
                new_lines.append(line)
                if line.strip().lower() == 'sincerely,' and (i + 1 < len(lines)):
                    # Overwrite next line(s) as needed
                    # Ensure company name on next line
                    if lines[i+1].strip() != company_name:
                        # Replace or insert company name line
                        if i + 1 < len(lines):
                            if lines[i+1].strip():
                                lines[i+1] = company_name
                            else:
                                lines[i+1] = company_name
                        else:
                            new_lines.append(company_name)
                    # Ensure signatory on the line after company name
                    if signatory:
                        # Determine position after company name
                        if i + 2 < len(lines):
                            if lines[i+2].strip() != signatory:
                                lines[i+2] = signatory
                        else:
                            lines.append(signatory)
                i += 1
            text = "\n".join(lines)
        else:
            # Append a proper signature block at the end if not present
            signature = f"\n\nSincerely,\n{company_name}"
            if signatory:
                signature += f"\n{signatory}"
            if not text.strip().endswith(signature.strip()):
                text = text.rstrip() + signature
        
        return text
