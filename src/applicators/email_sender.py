"""
SMTP-based email sender for application packages.
"""
from __future__ import annotations
import os
import smtplib
import mimetypes
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from email.message import EmailMessage
from datetime import datetime
from loguru import logger

from config import settings

class EmailSender:
    """Handles sending application packages via SMTP email."""

    def __init__(self):
        self.host = settings.smtp_host
        self.port = settings.smtp_port
        self.username = settings.smtp_username
        self.password = settings.smtp_password
        self.use_tls = settings.smtp_use_tls
        self.default_from = settings.smtp_from or self.username
        self.default_to = settings.smtp_to
        self.default_bcc = settings.smtp_bcc

    def _build_message(self, subject: str, body: str, from_addr: str, to_addrs: List[str], bcc_addrs: List[str] | None, attachments: List[Path]) -> EmailMessage:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = ", ".join(to_addrs)
        if bcc_addrs:
            msg["Bcc"] = ", ".join(bcc_addrs)
        msg.set_content(body)

        for path in attachments:
            try:
                if not path.exists() or not path.is_file():
                    logger.warning(f"Attachment not found, skipping: {path}")
                    continue
                ctype, encoding = mimetypes.guess_type(str(path))
                if ctype is None or encoding is not None:
                    ctype = "application/octet-stream"
                maintype, subtype = ctype.split("/", 1)
                with open(path, "rb") as fp:
                    file_data = fp.read()
                msg.add_attachment(file_data, maintype=maintype, subtype=subtype, filename=path.name)
            except Exception as e:
                logger.error(f"Failed to attach {path}: {e}")
        return msg

    def _connect(self) -> smtplib.SMTP:
        server = smtplib.SMTP(self.host, self.port, timeout=30)
        try:
            if self.use_tls:
                server.starttls()
            if self.username and self.password:
                server.login(self.username, self.password)
            return server
        except Exception:
            server.quit()
            raise

    def send_email(self, subject: str, body: str, to: Optional[List[str]] = None,
                   attachments: Optional[List[Path]] = None, from_addr: Optional[str] = None,
                   bcc: Optional[List[str]] = None) -> Dict[str, Any]:
        """Send an email with optional attachments."""
        from_address = from_addr or (self.default_from or self.username)
        if not from_address:
            return {"status": "error", "message": "No sender address configured. Set SMTP_FROM or SMTP_USERNAME."}
        to_addrs = to or ([self.default_to] if self.default_to else [from_address])
        bcc_addrs = bcc or ([self.default_bcc] if self.default_bcc else [])

        attachments = attachments or []
        msg = self._build_message(subject, body, from_address, to_addrs, bcc_addrs, attachments)

        try:
            with self._connect() as server:
                server.send_message(msg)
            logger.info(f"Email sent to {to_addrs} with {len(attachments)} attachment(s)")
            return {"status": "success", "message": "Email sent successfully"}
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return {"status": "error", "message": str(e)}

    def find_latest_application_folder(self, opportunity_id: str) -> Optional[Path]:
        apps_dir = Path("applications")
        if not apps_dir.exists():
            return None
        candidates: List[Tuple[datetime, Path]] = []
        for sub in apps_dir.iterdir():
            if not sub.is_dir():
                continue
            meta = sub / "metadata.json"
            if not meta.exists():
                continue
            try:
                import json
                with open(meta, "r", encoding="utf-8") as f:
                    data = json.load(f)
                if data.get("opportunity_id") == opportunity_id:
                    # Prefer generated_date when available
                    gen_date = data.get("generated_date")
                    dt = datetime.fromisoformat(gen_date) if gen_date else datetime.fromtimestamp(sub.stat().st_mtime)
                    candidates.append((dt, sub))
            except Exception:
                continue
        if not candidates:
            return None
        candidates.sort(key=lambda x: x[0], reverse=True)
        return candidates[0][1]

    def find_documents_by_keywords(self, keywords: List[str]) -> List[Path]:
        """Find documents in settings.documents_folder whose names contain all tokens of any keyword phrase (case-insensitive)."""
        docs_dir = Path(settings.documents_folder)
        if not docs_dir.exists():
            return []
        matches: List[Path] = []
        files = [p for p in docs_dir.iterdir() if p.is_file()]
        for phrase in keywords:
            tokens = [t for t in phrase.lower().split() if t]
            for f in files:
                name = f.name.lower()
                if all(tok in name for tok in tokens):
                    matches.append(f)
        # Deduplicate
        seen = set()
        unique: List[Path] = []
        for p in matches:
            if p.resolve() not in seen:
                unique.append(p)
                seen.add(p.resolve())
        return unique

    def find_documents_by_names(self, names: List[str]) -> List[Path]:
        """Find documents in settings.documents_folder by exact filename match (case-sensitive)."""
        docs_dir = Path(settings.documents_folder)
        if not docs_dir.exists():
            return []
        name_set = set(names or [])
        results: List[Path] = []
        for f in docs_dir.iterdir():
            if f.is_file() and f.name in name_set:
                results.append(f)
        return results

    def send_application_package(self, opportunity_id: str, opportunity_title: str, opportunity_agency: str,
                                 extra_doc_keywords: Optional[List[str]] = None,
                                 extra_doc_names: Optional[List[str]] = None,
                                 to: Optional[List[str]] = None) -> Dict[str, Any]:
        """Send the generated application package and extra documents via email."""
        app_folder = self.find_latest_application_folder(opportunity_id)
        if not app_folder:
            return {"status": "error", "message": "Application folder not found for the given opportunity."}

        attachments: List[Path] = []
        complete_app = app_folder / "complete_application.txt"
        if complete_app.exists():
            attachments.append(complete_app)
        # Optionally include section files
        for section in [
            "cover_letter.txt",
            "technical_approach.txt",
            "past_performance.txt",
            "team_qualifications.txt",
            "executive_summary.txt",
        ]:
            sec_path = app_folder / section
            if sec_path.exists():
                attachments.append(sec_path)

        # Include requested extra docs by keywords
        keywords = extra_doc_keywords or []
        if keywords:
            attachments.extend(self.find_documents_by_keywords(keywords))

        # Include additional docs by explicit names
        if extra_doc_names:
            attachments.extend(self.find_documents_by_names(extra_doc_names))

        # Deduplicate attachments
        dedup: List[Path] = []
        seen_paths = set()
        for p in attachments:
            rp = p.resolve()
            if rp not in seen_paths:
                dedup.append(p)
                seen_paths.add(rp)
        attachments = dedup

        subject = f"Application Package: {opportunity_title} - {opportunity_agency}"
        body = (
            f"Please find attached the generated application package for '{opportunity_title}' (Agency: {opportunity_agency}).\n\n"
            f"This email was sent automatically by the AI Bid Application System."
        )

        return self.send_email(subject=subject, body=body, to=to, attachments=attachments)