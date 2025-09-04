"""
AI-powered opportunity matching system.
"""
import re
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from datetime import datetime
from loguru import logger
import openai
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
import numpy as np
import time

from scrapers import BidOpportunity
from processors import ProcessedDocument

@dataclass
class MatchResult:
    """Result of opportunity matching."""
    opportunity: BidOpportunity
    match_score: float
    confidence: str
    matching_keywords: List[str]
    missing_requirements: List[str]
    recommendations: List[str]
    required_documents: List[str] = field(default_factory=list)
    required_attachments: List[str] = field(default_factory=list)
    should_apply: bool = False

class OpportunityMatcher:
    """AI-powered system to match opportunities with company capabilities."""
    
    def __init__(self, openai_api_key: str):
        self.openai_api_key = openai_api_key
        openai.api_key = openai_api_key
        
        # Initialize TF-IDF vectorizer for text similarity
        self.vectorizer = TfidfVectorizer(
            max_features=1000,
            stop_words='english',
            ngram_range=(1, 2)
        )
        
        # Company profile will be set after document processing
        self.company_profile = None
        self.company_vectors = None
    
    def set_company_profile(self, company_profile: Dict[str, Any]):
        """Set the company profile for matching."""
        self.company_profile = company_profile
        
        # Create TF-IDF vectors for company capabilities
        if company_profile.get('all_content'):
            self.company_vectors = self.vectorizer.fit_transform([company_profile['all_content']])
        
        logger.info("Company profile set for opportunity matching")
    
    def match_opportunities(self, opportunities: List[BidOpportunity], analyze_ai: bool = True, max_ai_duration_secs: int = 180) -> List[MatchResult]:
        """Match opportunities against company capabilities.
        analyze_ai: when False, skip slow AI analysis and use heuristic for assessment.
        max_ai_duration_secs: hard time budget for AI analysis across ALL opportunities (defaults to 3 minutes).
        """
        if not self.company_profile:
            logger.error("Company profile not set. Call set_company_profile() first.")
            return []
        
        match_results = []
        start_ts = time.time()
        ai_enabled_global = analyze_ai
        ai_used_count = 0
        
        for opportunity in opportunities:
            try:
                # Check remaining time budget before each analysis
                remaining = max_ai_duration_secs - (time.time() - start_ts)
                use_ai_now = ai_enabled_global and (remaining > 0)
                if ai_enabled_global and not use_ai_now:
                    logger.info("AI match time budget exceeded; falling back to heuristic for remaining opportunities.")
                    ai_enabled_global = False
                
                match_result = self._match_single_opportunity(
                    opportunity,
                    analyze_ai=use_ai_now,
                    ai_timeout_secs=remaining if use_ai_now else None
                )
                if use_ai_now:
                    ai_used_count += 1
                match_results.append(match_result)
            except Exception as e:
                logger.error(f"Failed to match opportunity {opportunity.opportunity_id}: {e}")
                continue
        
        # Sort by match score
        match_results.sort(key=lambda x: x.match_score, reverse=True)
        
        logger.info(f"Matched {len(match_results)} opportunities (AI used on {ai_used_count}, budget {max_ai_duration_secs}s)")
        return match_results
    
    def match_single_opportunity(self, opportunity: BidOpportunity, analyze_ai: bool = True, ai_timeout_secs: Optional[float] = None) -> MatchResult:
        """Public wrapper to match a single opportunity with optional AI analysis."""
        return self._match_single_opportunity(opportunity, analyze_ai=analyze_ai, ai_timeout_secs=ai_timeout_secs)
    
    def _match_single_opportunity(self, opportunity: BidOpportunity, analyze_ai: bool = True, ai_timeout_secs: Optional[float] = None) -> MatchResult:
        """Match a single opportunity against company capabilities."""
        
        # Calculate text similarity score
        similarity_score = self._calculate_text_similarity(opportunity)
        
        # Calculate keyword matching score
        keyword_score, matching_keywords = self._calculate_keyword_match(opportunity)
        
        # Use AI to analyze requirements and generate recommendations (optional)
        if analyze_ai:
            ai_analysis = self._ai_analyze_opportunity(opportunity, request_timeout=ai_timeout_secs)
        else:
            ai_analysis = self._heuristic_ai_analysis(similarity_score, keyword_score)
        
        # Calculate overall match score
        overall_score = self._calculate_overall_score(
            similarity_score, keyword_score, ai_analysis
        )
        
        # Determine confidence level
        confidence = self._determine_confidence(overall_score)
        
        # Determine if should apply
        should_apply = self._should_apply(overall_score, ai_analysis)
        
        return MatchResult(
            opportunity=opportunity,
            match_score=overall_score,
            confidence=confidence,
            matching_keywords=matching_keywords,
            missing_requirements=ai_analysis.get('missing_requirements', []),
            recommendations=ai_analysis.get('recommendations', []),
            required_documents=ai_analysis.get('required_documents', []),
            required_attachments=ai_analysis.get('required_attachments', []),
            should_apply=should_apply
        )
    
    def _calculate_text_similarity(self, opportunity: BidOpportunity) -> float:
        """Calculate text similarity between opportunity and company profile."""
        if self.company_vectors is None:
            return 0.0
        
        try:
            # Combine opportunity text
            opportunity_text = f"{opportunity.title} {opportunity.description}"
            
            # Transform opportunity text
            opportunity_vector = self.vectorizer.transform([opportunity_text])
            
            # Calculate cosine similarity
            similarity = cosine_similarity(self.company_vectors, opportunity_vector)[0][0]
            
            return float(similarity)
        except Exception as e:
            logger.warning(f"Failed to calculate text similarity: {e}")
            return 0.0
    
    def _calculate_keyword_match(self, opportunity: BidOpportunity) -> Tuple[float, List[str]]:
        """Calculate keyword matching score."""
        if not self.company_profile:
            return 0.0, []
        
        company_keywords = set(self.company_profile.get('technical_keywords', []))
        opportunity_text = f"{opportunity.title} {opportunity.description}".lower()
        
        matching_keywords = []
        for keyword in company_keywords:
            if keyword.lower() in opportunity_text:
                matching_keywords.append(keyword)
        
        # Calculate score based on percentage of keywords matched
        if not company_keywords:
            return 0.0, matching_keywords
        
        match_ratio = len(matching_keywords) / len(company_keywords)
        return match_ratio, matching_keywords
    
    def _heuristic_ai_analysis(self, similarity_score: float, keyword_score: float) -> Dict[str, Any]:
        """Fast fallback analysis without external AI calls."""
        pre = 0.5 * similarity_score + 0.5 * keyword_score
        if pre >= 0.7:
            assessment = 'High'
        elif pre >= 0.5:
            assessment = 'Medium'
        else:
            assessment = 'Low'
        return {
            'missing_requirements': [],
            'recommendations': [
                'Heuristic assessment used (quick match mode) - consider running full AI analysis for top results'
            ],
            'required_documents': [],
            'required_attachments': [],
            'assessment': assessment
        }
    
    def _ai_analyze_opportunity(self, opportunity: BidOpportunity, request_timeout: Optional[float] = None) -> Dict[str, Any]:
        """Use AI to analyze opportunity requirements and generate recommendations.
        request_timeout: optional per-request timeout in seconds for the AI call.
        """
        try:
            prompt = self._create_analysis_prompt(opportunity)
            
            # Prepare kwargs with optional timeout if provided and reasonable
            kwargs: Dict[str, Any] = {
                'model': 'gpt-3.5-turbo',
                'messages': [
                    {"role": "system", "content": "You are an expert in government contracting and IT/cybersecurity services. Analyze opportunities and provide detailed recommendations."},
                    {"role": "user", "content": prompt}
                ],
                'max_tokens': 1000,
                'temperature': 0.3
            }
            if request_timeout is not None and request_timeout > 0:
                # Cap to a minimum of 5s to avoid too-small timeouts
                kwargs['request_timeout'] = max(5, float(request_timeout))
            
            try:
                response = openai.ChatCompletion.create(**kwargs)
            except TypeError:
                # Older openai library may not support request_timeout; retry without it
                kwargs.pop('request_timeout', None)
                response = openai.ChatCompletion.create(**kwargs)
            
            analysis_text = response.choices[0].message.content
            
            # Parse the AI response
            return self._parse_ai_analysis(analysis_text)
            
        except Exception as e:
            logger.error(f"AI analysis failed: {e}")
            return {
                'missing_requirements': [],
                'recommendations': ['AI analysis unavailable - manual review recommended'],
                'required_documents': [],
                'required_attachments': [],
                'assessment': 'Medium'
            }
    
    def _create_analysis_prompt(self, opportunity: BidOpportunity) -> str:
        """Create prompt for AI analysis."""
        company_capabilities = self.company_profile.get('all_content', '')[:2000]  # Limit length
        
        prompt = f"""
        Analyze this government contracting opportunity and provide recommendations for our company.
        
        OPPORTUNITY DETAILS:
        Title: {opportunity.title}
        Agency: {opportunity.agency}
        Description: {opportunity.description}
        Due Date: {opportunity.due_date}
        NAICS Codes: {', '.join(opportunity.naics_codes)}
        
        OUR COMPANY CAPABILITIES:
        {company_capabilities}
        
        Please provide:
        1. Missing requirements that we don't currently have
        2. Specific recommendations for this opportunity
        3. Overall assessment of fit (High/Medium/Low)
        4. REQUIRED_DOCUMENTS: List the mandatory narrative or compliance documents to prepare/include (e.g., technical proposal, past performance, resumes/CVs, corporate capabilities, SAM registration, W-9, certificates, insurance, tax clearance, business registration, certifications).
        5. REQUIRED_ATTACHMENTS: List the specific attachment files typically uploaded with the submission (e.g., completed forms, pricing sheets, resumes, certificates, insurance COI, signed attachments), focusing on filenames/keywords we can use to find files.
        
        Format your response as:
        MISSING_REQUIREMENTS: [list of missing requirements]
        RECOMMENDATIONS: [list of specific recommendations]
        REQUIRED_DOCUMENTS: [list of required documents]
        REQUIRED_ATTACHMENTS: [list of required attachments]
        ASSESSMENT: [High/Medium/Low]
        """
        
        return prompt
    
    def _parse_ai_analysis(self, analysis_text: str) -> Dict[str, Any]:
        """Parse AI analysis response."""
        result = {
            'missing_requirements': [],
            'recommendations': [],
            'required_documents': [],
            'required_attachments': [],
            'assessment': 'Medium'
        }
        
        try:
            # Extract missing requirements
            missing_match = re.search(r'MISSING_REQUIREMENTS:\s*(.*?)(?=RECOMMENDATIONS:|REQUIRED_DOCUMENTS:|REQUIRED_ATTACHMENTS:|ASSESSMENT:|$)', 
                                    analysis_text, re.DOTALL | re.IGNORECASE)
            if missing_match:
                missing_text = missing_match.group(1).strip()
                parts = [p.strip('-• ').strip() for p in re.split(r'\n|,', missing_text) if p.strip()]
                result['missing_requirements'] = [req for req in parts if req]
            
            # Extract recommendations
            rec_match = re.search(r'RECOMMENDATIONS:\s*(.*?)(?=REQUIRED_DOCUMENTS:|REQUIRED_ATTACHMENTS:|ASSESSMENT:|$)', 
                                analysis_text, re.DOTALL | re.IGNORECASE)
            if rec_match:
                rec_text = rec_match.group(1).strip()
                result['recommendations'] = [rec.strip('-• ').strip() for rec in re.split(r'\n|,', rec_text) if rec.strip()]
            
            # Extract required documents
            req_docs_match = re.search(r'REQUIRED_DOCUMENTS:\s*(.*?)(?=REQUIRED_ATTACHMENTS:|ASSESSMENT:|$)',
                                       analysis_text, re.DOTALL | re.IGNORECASE)
            if req_docs_match:
                docs_text = req_docs_match.group(1).strip()
                result['required_documents'] = [d.strip('-• ').strip() for d in re.split(r'\n|,', docs_text) if d.strip()]
            
            # Extract required attachments
            req_att_match = re.search(r'REQUIRED_ATTACHMENTS:\s*(.*?)(?=ASSESSMENT:|$)',
                                      analysis_text, re.DOTALL | re.IGNORECASE)
            if req_att_match:
                att_text = req_att_match.group(1).strip()
                result['required_attachments'] = [a.strip('-• ').strip() for a in re.split(r'\n|,', att_text) if a.strip()]
            
            # Extract assessment
            assessment_match = re.search(r'ASSESSMENT:\s*(High|Medium|Low)', 
                                       analysis_text, re.IGNORECASE)
            if assessment_match:
                result['assessment'] = assessment_match.group(1).title()
                
        except Exception as e:
            logger.warning(f"Failed to parse AI analysis: {e}")
        
        return result
    
    def _calculate_overall_score(self, similarity_score: float, keyword_score: float, 
                               ai_analysis: Dict[str, Any]) -> float:
        """Calculate overall match score."""
        # Weight different components
        similarity_weight = 0.3
        keyword_weight = 0.4
        ai_weight = 0.3
        
        # Convert AI assessment to numeric score
        assessment_scores = {'High': 0.9, 'Medium': 0.6, 'Low': 0.3}
        ai_score = assessment_scores.get(ai_analysis.get('assessment', 'Medium'), 0.6)
        
        # Calculate weighted average
        overall_score = (
            similarity_score * similarity_weight +
            keyword_score * keyword_weight +
            ai_score * ai_weight
        )
        
        return min(1.0, max(0.0, overall_score))  # Clamp between 0 and 1
    
    def _determine_confidence(self, score: float) -> str:
        """Determine confidence level based on score."""
        if score >= 0.8:
            return "High"
        elif score >= 0.6:
            return "Medium"
        else:
            return "Low"
    
    def _should_apply(self, score: float, ai_analysis: Dict[str, Any]) -> bool:
        """Determine if we should apply for this opportunity."""
        # Base decision on score and AI assessment
        if score >= 0.7:
            return True
        elif score >= 0.5 and ai_analysis.get('assessment') == 'High':
            return True
        else:
            return False
    
    def get_top_matches(self, match_results: List[MatchResult], 
                       limit: int = 10) -> List[MatchResult]:
        """Get top matching opportunities."""
        return [result for result in match_results if result.should_apply][:limit]
    
    def generate_application_summary(self, match_result: MatchResult) -> str:
        """Generate a summary for application decision."""
        summary = f"""
        OPPORTUNITY: {match_result.opportunity.title}
        AGENCY: {match_result.opportunity.agency}
        MATCH SCORE: {match_result.match_score:.2f} ({match_result.confidence} Confidence)
        DUE DATE: {match_result.opportunity.due_date}
        
        MATCHING KEYWORDS: {', '.join(match_result.matching_keywords)}
        
        RECOMMENDATIONS:
        {chr(10).join(f"- {rec}" for rec in match_result.recommendations)}
        
        DECISION: {'APPLY' if match_result.should_apply else 'DO NOT APPLY'}
        """
        
        return summary.strip()
