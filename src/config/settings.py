"""
Configuration management for the AI bid application system.
"""
import os
from typing import List, Optional
from pydantic import Field, field_validator
from pydantic_settings import BaseSettings
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class Settings(BaseSettings):
    """Application settings loaded from environment variables."""
    
    # OpenAI Configuration
    openai_api_key: str = Field("", env="OPENAI_API_KEY")
    
    # Government APIs
    sam_gov_api_key: Optional[str] = Field(None, env="SAM_GOV_API_KEY")
    govwin_api_key: Optional[str] = Field(None, env="GOVWIN_API_KEY")
    
    # Company Information
    company_name: str = Field("Your Company", env="COMPANY_NAME")
    company_duns: Optional[str] = Field(None, env="COMPANY_DUNS")
    company_naics_codes: List[str] = Field(
        default=["541511", "541512", "541519", "541690"], 
        env="COMPANY_NAICS_CODES"
    )
    
    # File Paths
    documents_folder: str = Field("./documents", env="DOCUMENTS_FOLDER")
    templates_folder: str = Field("./templates", env="TEMPLATES_FOLDER")
    
    # Application Settings
    auto_submit: bool = Field(False, env="AUTO_SUBMIT")
    review_mode: bool = Field(True, env="REVIEW_MODE")
    max_applications_per_day: int = Field(10, env="MAX_APPLICATIONS_PER_DAY")

    # New Feature Flags / Performance Tuning
    fast_mode_default: bool = Field(False, env="FAST_MODE_DEFAULT")
    openai_section_timeout_secs: int = Field(45, env="OPENAI_SECTION_TIMEOUT_SECS")
    generation_parallelism: int = Field(5, env="GENERATION_PARALLELISM")
    prewarm_on_startup: bool = Field(True, env="PREWARM_ON_STARTUP")
    background_jobs_max: int = Field(100, env="BACKGROUND_JOBS_MAX")
    
    # Logging
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_file: str = Field("./logs/bid_application.log", env="LOG_FILE")

    # SMTP / Email Settings (Gmail by default)
    smtp_host: str = Field("smtp.gmail.com", env="SMTP_HOST")
    smtp_port: int = Field(587, env="SMTP_PORT")
    smtp_username: str = Field("keithtwesigye74@gmail.com", env="SMTP_USERNAME")
    smtp_password: str = Field("", env="SMTP_PASSWORD")
    smtp_use_tls: bool = Field(True, env="SMTP_USE_TLS")
    smtp_from: Optional[str] = Field(None, env="SMTP_FROM")
    smtp_to: Optional[str] = Field(None, env="SMTP_TO")
    smtp_bcc: Optional[str] = Field(None, env="SMTP_BCC")
    
    # Email strict mode: when true, do not send unless explicit or discovered recipients exist
    email_strict_mode: bool = Field(False, env="EMAIL_STRICT_MODE")
    
    # Bid Search Keywords
    it_keywords: List[str] = [
        "information technology", "IT services", "software development",
        "system administration", "network administration", "database management",
        "cloud services", "digital transformation", "IT consulting"
    ]
    
    cybersecurity_keywords: List[str] = [
        "cybersecurity", "information security", "cyber security",
        "security assessment", "penetration testing", "vulnerability assessment",
        "security monitoring", "incident response", "security consulting",
        "compliance", "risk assessment", "security operations center"
    ]
    
    # Government Contracting Sites
    bid_sources: List[str] = [
        "https://sam.gov",
        "https://www.fbo.gov",
        "https://www.grants.gov",
        "https://www.usaspending.gov"
    ]

    # Validators
    @field_validator("smtp_password", mode="before")
    @classmethod
    def _clean_smtp_password(cls, v):
        """Normalize pasted Gmail app passwords by stripping quotes and spaces."""
        if isinstance(v, str):
            return v.strip().replace('"', '').replace("'", "").replace(" ", "")
        return v

class Config:
    env_file = ".env"
    case_sensitive = False

# Global settings instance
settings = Settings()
