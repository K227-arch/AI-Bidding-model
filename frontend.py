#!/usr/bin/env python3
"""
Web frontend for the AI bid application system.
"""
import os
import sys
import json
import re
from pathlib import Path
from typing import List, Dict, Any, Optional
from datetime import datetime
import uvicorn
from fastapi import FastAPI, Request, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel
import asyncio
from loguru import logger
from uuid import uuid4
from typing import Tuple

# Add src to path
sys.path.insert(0, str(Path(__file__).parent / "src"))

from config import settings
from scrapers import SAMGovScraper, FBOScraper, SampleScraper, RemotiveScraper, RemoteOKScraper, UgandaSampleScraper
from processors import DocumentProcessor
from ai import OpportunityMatcher, MatchResult
from applicators import ApplicationGenerator, ApplicationSubmitter, EmailSender

# Initialize FastAPI app
app = FastAPI(title="AI Bid Application System", version="1.0.0")

# Create static and templates directories
static_dir = Path("static")
templates_dir = Path("templates")
static_dir.mkdir(exist_ok=True)
templates_dir.mkdir(exist_ok=True)

# Mount static files
app.mount("/static", StaticFiles(directory="static"), name="static")
# Serve documents as static files for preview/download
try:
    app.mount("/documents", StaticFiles(directory=settings.documents_folder), name="documents")
except Exception:
    pass

# Setup templates
templates = Jinja2Templates(directory="templates")

# Global system instance
bid_system = None

class BidSystem:
    """Web-enabled bid application system."""
    
    def __init__(self):
        self.document_processor = DocumentProcessor(settings.documents_folder)
        self.opportunity_matcher = OpportunityMatcher(settings.openai_api_key)
        self.application_generator = ApplicationGenerator(
            settings.openai_api_key, 
            settings.templates_folder
        )
        self.application_submitter = ApplicationSubmitter(headless=True)
        self.email_sender = EmailSender()
        
        # Initialize scrapers
        self.scrapers = [
            SampleScraper(),  # Add sample scraper first for demo
            SAMGovScraper(),
            FBOScraper(),
            RemotiveScraper(),
            RemoteOKScraper(),
            UgandaSampleScraper(),
        ]
        
        self.company_profile = None
        self.processed_docs = []
        self.current_opportunities = []
        self.match_results = []
        
        # Background job store
        self.jobs: Dict[str, Dict[str, Any]] = {}
        
        logger.info("Web Bid Application System initialized")

    async def process_documents(self) -> Dict[str, Any]:
        """Process company documents."""
        try:
            self.processed_docs = self.document_processor.process_all_documents()
            
            if not self.processed_docs:
                return {
                    'status': 'warning',
                    'message': 'No documents found. Please upload company documents.',
                    'documents_processed': 0
                }
            
            # Create company profile
            self.company_profile = self.document_processor.get_company_profile(self.processed_docs)
            self.opportunity_matcher.set_company_profile(self.company_profile)
            
            return {
                'status': 'success',
                'message': f'Processed {len(self.processed_docs)} documents successfully',
                'documents_processed': len(self.processed_docs),
                'company_name': self.company_profile.get('company_name', 'Unknown'),
                'technical_keywords': len(self.company_profile.get('technical_keywords', []))
            }
            
        except Exception as e:
            logger.error(f"Document processing failed: {e}")
            return {
                'status': 'error',
                'message': f'Document processing failed: {str(e)}',
                'documents_processed': 0
            }

    async def search_opportunities(self, days_back: int = 7, max_opportunities: int = 50, quick_search: bool = False, run_parallel: bool = False) -> Dict[str, Any]:
        """Search for opportunities."""
        try:
            all_opportunities = []
            
            # Combine keywords
            search_keywords = settings.it_keywords + settings.cybersecurity_keywords
            
            # Quick search: limit the number of keywords to speed up network calls
            if quick_search:
                MAX_QS_KEYWORDS = 8
                search_keywords = search_keywords[:MAX_QS_KEYWORDS]
                logger.info(f"Quick search enabled: limiting keywords to {len(search_keywords)}")
            
            if run_parallel:
                logger.info("Running scrapers in parallel")
                tasks = [
                    asyncio.to_thread(scraper.search_opportunities, search_keywords, days_back)
                    for scraper in self.scrapers
                ]
                results = await asyncio.gather(*tasks, return_exceptions=True)
                for scraper, result in zip(self.scrapers, results):
                    if isinstance(result, Exception):
                        logger.error(f"Scraper {scraper.name} failed: {result}")
                    else:
                        all_opportunities.extend(result)
                        logger.info(f"{scraper.name}: Found {len(result)} opportunities")
            else:
                # Sequential execution
                for scraper in self.scrapers:
                    try:
                        opportunities = scraper.search_opportunities(search_keywords, days_back)
                        all_opportunities.extend(opportunities)
                        logger.info(f"{scraper.name}: Found {len(opportunities)} opportunities")
                    except Exception as e:
                        logger.error(f"Scraper {scraper.name} failed: {e}")
            
            if not all_opportunities:
                return {
                    'status': 'warning',
                    'message': 'No opportunities found. This may be due to API limitations or network issues.',
                    'opportunities_found': 0
                }
            
            # Remove duplicates and limit
            unique_opportunities = self._remove_duplicate_opportunities(all_opportunities)
            self.current_opportunities = unique_opportunities[:max_opportunities]
            
            return {
                'status': 'success',
                'message': f'Found {len(self.current_opportunities)} unique opportunities',
                'opportunities_found': len(self.current_opportunities)
            }
            
        except Exception as e:
            logger.error(f"Opportunity search failed: {e}")
            return {
                'status': 'error',
                'message': f'Opportunity search failed: {str(e)}',
                'opportunities_found': 0
            }

    async def match_opportunities(self, analyze_ai: bool = True, max_ai_duration_secs: int = 180) -> Dict[str, Any]:
        """Match opportunities with company capabilities."""
        try:
            if not self.current_opportunities:
                return {
                    'status': 'warning',
                    'message': 'No opportunities to match. Please search for opportunities first.',
                    'opportunities_matched': 0
                }
            
            if not self.company_profile:
                return {
                    'status': 'warning',
                    'message': 'No company profile available. Please process documents first.',
                    'opportunities_matched': 0
                }
            
            # Match opportunities
            self.match_results = self.opportunity_matcher.match_opportunities(self.current_opportunities, analyze_ai=analyze_ai, max_ai_duration_secs=max_ai_duration_secs)
            
            # Filter for applicable opportunities
            applicable_opportunities = [result for result in self.match_results if result.should_apply]

            # Prepare simplified results for API including required docs/attachments if present
            simplified = []
            for r in self.match_results:
                simplified.append({
                    'opportunity_id': r.opportunity.opportunity_id,
                    'title': r.opportunity.title,
                    'agency': r.opportunity.agency,
                    'due_date': r.opportunity.due_date.isoformat() if r.opportunity.due_date else None,
                    'match_score': r.match_score,
                    'confidence': r.confidence,
                    'should_apply': r.should_apply,
                    'missing_requirements': r.missing_requirements,
                    'recommendations': r.recommendations,
                    'required_documents': getattr(r, 'required_documents', []),
                    'required_attachments': getattr(r, 'required_attachments', []),
                })
            
            return {
                'status': 'success',
                'message': f'Matched {len(self.match_results)} opportunities, {len(applicable_opportunities)} are applicable',
                'opportunities_matched': len(self.match_results),
                'applicable_opportunities': len(applicable_opportunities),
                'results': simplified
            }
            
        except Exception as e:
            logger.error(f"Opportunity matching failed: {e}")
            return {
                'status': 'error',
                'message': f'Opportunity matching failed: {str(e)}',
                'opportunities_matched': 0
            }
    
    async def generate_application(self, opportunity_id: str, fast_mode: Optional[bool] = None) -> Dict[str, Any]:
        """Generate application for a specific opportunity (blocking call)."""
        try:
            # Ensure documents and company profile are available
            if not self.processed_docs:
                self.processed_docs = self.document_processor.process_all_documents()
            if not self.company_profile:
                self.company_profile = self.document_processor.get_company_profile(self.processed_docs)
                self.opportunity_matcher.set_company_profile(self.company_profile)

            # Find the opportunity via prior match results first
            match_result = None
            for result in self.match_results:
                if result.opportunity.opportunity_id == opportunity_id:
                    match_result = result
                    break

            # If not found, attempt to locate the raw opportunity and synthesize a MatchResult
            if not match_result:
                target_opp = None
                for opp in self.current_opportunities:
                    if getattr(opp, 'opportunity_id', None) == opportunity_id:
                        target_opp = opp
                        break
                if target_opp is None:
                    return {
                        'status': 'error',
                        'message': 'Opportunity not found',
                        'application_generated': False
                    }

                # Build simple matching keywords heuristic
                matching_keywords: List[str] = []
                try:
                    opp_text = f"{getattr(target_opp, 'title', '')} {getattr(target_opp, 'description', '')}".lower()
                    for kw in (self.company_profile.get('technical_keywords', []) if self.company_profile else []):
                        if isinstance(kw, str) and kw.lower() in opp_text:
                            matching_keywords.append(kw)
                    matching_keywords = list(dict.fromkeys(matching_keywords))[:15]
                except Exception:
                    matching_keywords = []
                match_result = MatchResult(
                    opportunity=target_opp,
                    match_score=0.5,
                    confidence="medium",
                    matching_keywords=matching_keywords,
                    missing_requirements=[],
                    recommendations=[],
                    should_apply=True
                )

            # Generate application
            application_package = self.application_generator.generate_application(
                match_result, self.company_profile or {}, self.processed_docs or [], fast_mode=fast_mode
            )

            # Save application package
            output_folder = self.application_generator.save_application_package(application_package)

            return {
                'status': 'success',
                'message': f'Application generated successfully',
                'application_generated': True,
                'output_folder': output_folder,
                'opportunity_title': match_result.opportunity.title,
                'required_documents': getattr(match_result, 'required_documents', []),
                'required_attachments': getattr(match_result, 'required_attachments', []),
            }

        except Exception as e:
            logger.error(f"Application generation failed: {e}")
            return {
                'status': 'error',
                'message': f'Application generation failed: {str(e)}',
                'application_generated': False
            }

    # Background job helpers
    def start_generation_job(self, opportunity_id: str, fast_mode: Optional[bool] = None, enhance_after: bool = False) -> str:
        if len(self.jobs) >= settings.background_jobs_max:
            raise HTTPException(status_code=429, detail="Too many background jobs. Please try again later.")
        job_id = str(uuid4())
        self.jobs[job_id] = {
            'status': 'pending',
            'opportunity_id': opportunity_id,
            'fast_mode': fast_mode,
            'enhance_after': enhance_after,
            'started_at': datetime.now().isoformat(),
            'finished_at': None,
            'output_folder': None,
            'enhanced_output_folder': None,
            'error': None,
        }
        asyncio.create_task(self._run_generation_job(job_id))
        return job_id

    async def _run_generation_job(self, job_id: str):
        job = self.jobs.get(job_id)
        if not job:
            return
        job['status'] = 'running'
        opp_id = job['opportunity_id']
        fast_mode = job.get('fast_mode', None)
        enhance_after = bool(job.get('enhance_after'))
        try:
            # Ensure preconditions
            if not self.processed_docs:
                self.processed_docs = self.document_processor.process_all_documents()
            if not self.company_profile:
                self.company_profile = self.document_processor.get_company_profile(self.processed_docs)
                self.opportunity_matcher.set_company_profile(self.company_profile)
            # Blocking call to reuse existing logic
            result = await self.generate_application(opp_id, fast_mode=fast_mode)
            if result.get('application_generated'):
                job['output_folder'] = result.get('output_folder')
                # Optional enhancement: run full AI generation and save separately
                if enhance_after and (fast_mode is True or fast_mode is None and settings.fast_mode_default):
                    try:
                        full_result = await self.generate_application(opp_id, fast_mode=False)
                        if full_result.get('application_generated'):
                            job['enhanced_output_folder'] = full_result.get('output_folder')
                    except Exception as e:
                        logger.warning(f"Enhancement failed for job {job_id}: {e}")
            job['status'] = 'completed'
            job['finished_at'] = datetime.now().isoformat()
        except Exception as e:
            job['status'] = 'failed'
            job['error'] = str(e)
            job['finished_at'] = datetime.now().isoformat()

    def get_job_status(self, job_id: str) -> Dict[str, Any]:
        job = self.jobs.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Job not found")
        # Return a shallow copy to avoid mutation outside
        return dict(job)

    async def email_application(self, opportunity_id: str, to: Optional[List[str]] = None,
                                extra_doc_keywords: Optional[List[str]] = None,
                                extra_doc_names: Optional[List[str]] = None) -> Dict[str, Any]:
        """Send the most recent application for an opportunity via email with specified attachments."""
        # Find opportunity details and match_result if available
        title = None
        agency = None
        matched: Optional[MatchResult] = None
        for result in self.match_results:
            if result.opportunity.opportunity_id == opportunity_id:
                title = result.opportunity.title
                agency = result.opportunity.agency
                matched = result
                break
        if title is None:
            for opp in self.current_opportunities:
                if getattr(opp, 'opportunity_id', None) == opportunity_id:
                    title = getattr(opp, 'title', None)
                    agency = getattr(opp, 'agency', None)
                    break
        if title is None:
            title = opportunity_id
            agency = agency or ''

        # Build keywords from required docs/attachments when available
        def _expand_keywords(phrases: List[str]) -> List[str]:
            expanded: List[str] = []
            for p in phrases or []:
                try:
                    lower = (p or '').lower().strip()
                    if not lower:
                        continue
                    expanded.append(lower)
                    # Normalize punctuation -> spaces
                    tokens = re.sub(r"[^a-z0-9]+", " ", lower).split()
                    if tokens:
                        expanded.append(" ".join(tokens))
                        # Join alnums without spaces for patterns like w9, 1099, etc.
                        expanded.append("".join(tokens))
                        # Special-case W-9 variants
                        if any(t in {"w", "w9", "w-9"} or (t == "9") for t in tokens) or "w-9" in lower or "w9" in lower:
                            expanded.extend(["w9", "w 9", "w-9", "irs w9", "irs form w9"])
                        # SAM registration variants
                        if "sam" in tokens or "sam" in lower:
                            expanded.extend(["sam", "sam registration", "sam.gov", "active sam"])
                        # Insurance certificate variants
                        if "insurance" in tokens:
                            expanded.extend(["insurance", "insurance certificate", "certificate of insurance", "coi"])
                        # Resume/CV variants
                        if any(t in {"resume", "resumes", "cv"} for t in tokens):
                            expanded.extend(["resume", "cv", "curriculum vitae"])
                except Exception:
                    continue
            # Dedup while preserving order
            seen = set()
            uniq: List[str] = []
            for kw in expanded:
                if kw not in seen:
                    uniq.append(kw)
                    seen.add(kw)
            return uniq

        required_keywords: List[str] = []
        if matched is not None:
            required_keywords = _expand_keywords(getattr(matched, 'required_documents', []) + getattr(matched, 'required_attachments', []))

        # Merge requested extra keywords with defaults and required
        default_keywords = ["wic", "company profile", "technical capabilities"]
        merged_keywords = (extra_doc_keywords or []) + required_keywords + default_keywords

        result = self.email_sender.send_application_package(
            opportunity_id=opportunity_id,
            opportunity_title=title or opportunity_id,
            opportunity_agency=agency or '',
            extra_doc_keywords=merged_keywords,
            extra_doc_names=extra_doc_names or [],
            to=to
        )
        return result

        # If missing application folder, try generating on-the-fly then retry sending
        if result.get('status') != 'success' and 'Application folder not found' in (result.get('message') or ''):
            try:
                gen = await self.generate_application(opportunity_id)
                if gen.get('status') == 'success':
                    result = self.email_sender.send_application_package(
                        opportunity_id=opportunity_id,
                        opportunity_title=title or opportunity_id,
                        opportunity_agency=agency or '',
                        extra_doc_keywords=extra_keywords,
                        extra_doc_names=extra_doc_names or [],
                        to=to
                    )
            except Exception as _e:
                logger.error(f"Auto-generate before email failed: {_e}")

        # Append to submission history log
        logs_dir = Path("logs")
        logs_dir.mkdir(exist_ok=True)
        log_path = logs_dir / "submissions.json"
        entry = {
            'timestamp': datetime.now().isoformat(),
            'method': 'email',
            'opportunity_id': opportunity_id,
            'opportunity_title': title,
            'status': result.get('status'),
            'message': result.get('message'),
            'to': to or ([settings.smtp_to] if settings.smtp_to else [settings.smtp_from or settings.smtp_username]),
            'extra_doc_names': extra_doc_names or [],
            'extra_doc_keywords': extra_keywords,
        }
        try:
            with open(log_path, 'a', encoding='utf-8') as f:
                f.write(json.dumps(entry) + "\n")
        except Exception as e:
            logger.error(f"Failed to write submission log: {e}")

        # Map to API response
        if result.get('status') == 'success':
            return {
                'status': 'success',
                'message': 'Email sent successfully',
                'opportunity_id': opportunity_id
            }
        else:
            return {
                'status': 'error',
                'message': result.get('message', 'Failed to send email'),
                'opportunity_id': opportunity_id
            }
    
    def _remove_duplicate_opportunities(self, opportunities: List) -> List:
        """Remove duplicate opportunities based on opportunity_id."""
        seen_ids = set()
        unique_opportunities = []
        
        for opp in opportunities:
            if opp.opportunity_id not in seen_ids:
                seen_ids.add(opp.opportunity_id)
                unique_opportunities.append(opp)
        
        return unique_opportunities

# Initialize system and prewarm on startup
@app.on_event("startup")
async def on_startup():
    global bid_system
    bid_system = BidSystem()
    if settings.prewarm_on_startup:
        try:
            await bid_system.process_documents()
            logger.info("Prewarm completed: company profile cached")
        except Exception as e:
            logger.warning(f"Prewarm failed: {e}")

class SearchRequest(BaseModel):
    days_back: int = 7
    max_opportunities: int = 50
    quick_search: bool = False
    run_parallel: bool = False

class ApplicationRequest(BaseModel):
    opportunity_id: str

class GenerationRequest(BaseModel):
    opportunity_id: str
    fast_mode: Optional[bool] = None
    background: bool = True
    enhance_after: bool = False

class EmailApplicationRequest(BaseModel):
    opportunity_id: str
    to: Optional[List[str]] = None
    extra_doc_keywords: Optional[List[str]] = None
    extra_doc_names: Optional[List[str]] = None

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/api/status")
async def get_status():
    return JSONResponse(content={
        'message': 'Backend is running',
        'timestamp': datetime.now().isoformat(),
        'jobs_total': len(bid_system.jobs) if bid_system else 0,
        'jobs_running': sum(1 for j in (bid_system.jobs.values() if bid_system else []) if j.get('status') == 'running')
    })

@app.get("/api/test")
async def test_endpoint():
    return JSONResponse(content={
        'message': 'Backend is running',
        'timestamp': datetime.now().isoformat()
    })

@app.post("/api/documents/process")
async def process_documents():
    result = await bid_system.process_documents()
    return JSONResponse(content=result)

@app.post("/api/opportunities/search")
async def search_opportunities(request: SearchRequest):
    result = await bid_system.search_opportunities(
        days_back=request.days_back,
        max_opportunities=request.max_opportunities,
        quick_search=request.quick_search,
        run_parallel=request.run_parallel
    )
    return JSONResponse(content=result)

@app.get("/api/opportunities")
async def get_opportunities():
    """Get current opportunities (basic info only, no AI matching)."""
    opportunities = []
    for opp in bid_system.current_opportunities:
        opportunities.append({
            'opportunity_id': opp.opportunity_id,
            'title': opp.title,
            'agency': opp.agency,
            'due_date': opp.due_date.isoformat() if opp.due_date else None,
            'url': opp.url
        })
    
    return JSONResponse(content={
        'opportunities': opportunities,
        'total': len(opportunities)
    })

@app.post("/api/opportunities/match")
async def match_opportunities_route(analyze_ai: bool = True, max_ai_duration_secs: int = 180):
    """Match current opportunities against company profile."""
    result = await bid_system.match_opportunities(
        analyze_ai=analyze_ai,
        max_ai_duration_secs=max_ai_duration_secs
    )
    return JSONResponse(content=result)

@app.get("/api/history/applications")
async def get_application_history():
    """Return list of generated applications from applications folder (using metadata.json)."""
    history: List[Dict[str, Any]] = []
    apps_dir = Path("applications")
    if apps_dir.exists():
        for item in apps_dir.iterdir():
            try:
                if item.is_dir():
                    meta_path = item / "metadata.json"
                    if meta_path.exists():
                        with open(meta_path, 'r', encoding='utf-8') as mf:
                            meta = json.load(mf)
                        folder_rel = os.path.relpath(str(item), start='.')
                        combined_path = str(Path(folder_rel) / 'complete_application.txt')
                        history.append({
                            'opportunity_id': meta.get('opportunity_id'),
                            'opportunity_title': meta.get('opportunity_title'),
                            'opportunity_agency': meta.get('opportunity_agency'),
                            'generated_date': meta.get('generated_date'),
                            'folder': folder_rel,
                            'combined_path': combined_path
                        })
            except Exception as e:
                logger.warning(f"Failed to read application history from {item}: {e}")
                continue
    # Sort by generated_date desc if available, else by folder name desc
    def sort_key(entry: Dict[str, Any]):
        try:
            return datetime.fromisoformat(entry.get('generated_date') or '1970-01-01T00:00:00')
        except Exception:
            return datetime.min
    history.sort(key=sort_key, reverse=True)
    return JSONResponse(content={'applications': history, 'total': len(history)})

@app.get("/api/history/submissions")
async def get_submission_history():
    """Return submission attempts history from logs/submissions.json (newline-delimited JSON)."""
    log_file = Path("logs/submissions.json")
    entries: List[Dict[str, Any]] = []
    if log_file.exists():
        try:
            with open(log_file, 'r', encoding='utf-8') as f:
                for line in f:
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        entries.append(json.loads(line))
                    except json.JSONDecodeError:
                        logger.warning("Skipping malformed submission log line")
        except Exception as e:
            logger.error(f"Failed to read submission history: {e}")
    # Sort by timestamp desc
    def sort_key2(entry: Dict[str, Any]):
        try:
            return datetime.fromisoformat(entry.get('timestamp'))
        except Exception:
            return datetime.min
    entries.sort(key=sort_key2, reverse=True)
    return JSONResponse(content={'submissions': entries, 'total': len(entries)})

@app.post("/api/applications/generate")
async def generate_application(request: GenerationRequest):
    """Generate application for an opportunity. Defaults to background job with optional fast_mode."""
    if request.background:
        job_id = bid_system.start_generation_job(request.opportunity_id, fast_mode=request.fast_mode, enhance_after=request.enhance_after)
        return JSONResponse(content={'status': 'accepted', 'job_id': job_id})
    else:
        result = await bid_system.generate_application(request.opportunity_id, fast_mode=request.fast_mode)
        return JSONResponse(content=result)

@app.get("/api/jobs/{job_id}")
async def get_job(job_id: str):
    status = bid_system.get_job_status(job_id)
    return JSONResponse(content=status)

@app.post("/api/applications/email")
async def email_application(request: EmailApplicationRequest):
    """Send generated application via email (with preconfigured attachments)."""
    result = await bid_system.email_application(
        request.opportunity_id,
        request.to,
        extra_doc_keywords=request.extra_doc_keywords,
        extra_doc_names=request.extra_doc_names
    )
    return JSONResponse(content=result)

@app.post("/api/documents/upload")
async def upload_document(file: List[UploadFile] = File(...)):
    """Upload one or more company documents (supports multiple files)."""
    try:
        if not isinstance(file, list):
            files = [file]
        else:
            files = file

        uploaded = []
        failed = []

        allowed_extensions = {'.pdf', '.docx', '.doc', '.txt', '.xlsx', '.xls'}

        # Ensure documents folder exists
        documents_folder = Path(settings.documents_folder)
        documents_folder.mkdir(exist_ok=True)

        for f in files:
            try:
                logger.info(f"Uploading file: {f.filename}, content_type: {f.content_type}")

                file_extension = Path(f.filename).suffix.lower()
                if file_extension not in allowed_extensions:
                    failed.append({
                        'filename': f.filename,
                        'reason': f'Unsupported type {file_extension}'
                    })
                    continue

                # Unique filename to avoid conflicts
                timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
                safe_filename = f"{timestamp}_{f.filename}"
                file_path = documents_folder / safe_filename

                content = await f.read()
                with open(file_path, "wb") as buffer:
                    buffer.write(content)

                logger.info(f"File saved to: {file_path}")

                uploaded.append({
                    'filename': f.filename,
                    'saved_as': safe_filename,
                    'file_size': len(content)
                })
            except Exception as inner_e:
                logger.error(f"Failed to save {f.filename}: {inner_e}")
                failed.append({'filename': f.filename, 'reason': str(inner_e)})

        status = 'success' if uploaded else ('warning' if failed else 'error')
        message = (
            f"Uploaded {len(uploaded)} file(s)." if uploaded else "No files uploaded."
        )
        if failed:
            message += f" Failed: {len(failed)} file(s)."

        return JSONResponse(content={
            'status': status,
            'message': message,
            'uploaded': uploaded,
            'failed': failed
        })

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/documents")
async def get_documents():
    """List documents in the documents folder."""
    docs_dir = Path(settings.documents_folder)
    docs = []
    if docs_dir.exists():
        for p in docs_dir.iterdir():
            if p.is_file():
                docs.append({'name': p.name, 'path': str(p)})
    return JSONResponse(content={'documents': docs, 'total': len(docs)})

@app.get("/applications/{path:path}")
async def serve_application_files(path: str):
    file_path = Path("applications") / path
    if not file_path.exists():
        raise HTTPException(status_code=404, detail="File not found")
    return FileResponse(str(file_path))

if __name__ == "__main__":
    # Create default templates if not exist
    def create_templates():
        templates_needed = {
            'cover_letter.txt': "Dear [Agency],...",
            'technical_approach.txt': "Our approach...",
            'past_performance.txt': "We have delivered...",
            'team_qualifications.txt': "Our team includes..."
        }
        for filename, content in templates_needed.items():
            path = templates_dir / filename
            if not path.exists():
                with open(path, 'w', encoding='utf-8') as f:
                    f.write(content)

    create_templates()

    uvicorn.run(
        "frontend:app",
        host="0.0.0.0",
        port=8000,
        reload=True,
        log_level="info"
    )
