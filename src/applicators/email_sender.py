"""
SMTP-based email sender for application packages.
"""
from __future__ import annotations
import os
import smtplib
import mimetypes
import ssl
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
from email.message import EmailMessage
from datetime import datetime
from loguru import logger
import re
import requests
from urllib.parse import urlparse

from config import settings

class EmailSender:
    """Handles sending application packages via SMTP email."""

    def __init__(self):
        self.host = settings.smtp_host
        self.port = settings.smtp_port
        self.username = settings.smtp_username
        self.password = settings.smtp_password
        self.use_tls = settings.smtp_use_tls
        # Fallbacks: our Settings defines smtp_use_tls but not smtp_use_ssl nor smtp_timeout
        self.use_ssl = False
        self.timeout = 30
        self.default_from = settings.smtp_from or self.username
        self.default_to = settings.smtp_to
        self.default_bcc = settings.smtp_bcc

    def _build_message(self, subject: str, body_text: str, from_addr: str, to_addrs: List[str], bcc_addrs: List[str] | None, attachments: List[Path], body_html: Optional[str] = None) -> EmailMessage:
        msg = EmailMessage()
        msg["Subject"] = subject
        msg["From"] = from_addr
        msg["To"] = ", ".join(to_addrs)
        if bcc_addrs:
            msg["Bcc"] = ", ".join(bcc_addrs)
        # Set plain text content first, then add HTML alternative if provided
        msg.set_content(body_text)
        if body_html:
            msg.add_alternative(body_html, subtype="html")

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
        server: Optional[smtplib.SMTP] = None
        ctx = ssl.create_default_context()
        try:
            if self.use_ssl:
                # SMTPS (implicit TLS), typically port 465
                server = smtplib.SMTP_SSL(self.host, self.port, timeout=self.timeout)
            else:
                # Start unencrypted and upgrade with STARTTLS if enabled (typically port 587)
                server = smtplib.SMTP(self.host, self.port, timeout=self.timeout)
                server.ehlo()
                if self.use_tls:
                    server.starttls(context=ctx)
                    server.ehlo()
            if self.username and self.password:
                server.login(self.username, self.password)
            return server
        except Exception:
            try:
                if server is not None:
                    server.quit()
            except Exception:
                pass
            raise

    def send_email(self, subject: str, body: str, to: Optional[List[str]] = None,
                   attachments: Optional[List[Path]] = None, from_addr: Optional[str] = None,
                   bcc: Optional[List[str]] = None, body_html: Optional[str] = None) -> Dict[str, Any]:
        """Send an email with optional attachments and optional HTML body."""
        from_address = from_addr or (self.default_from or self.username)
        if not from_address:
            return {"status": "error", "message": "No sender address configured. Set SMTP_FROM or SMTP_USERNAME."}
        # Determine recipients based on strict mode
        if to and len(to) > 0:
            to_addrs = to
        elif settings.email_strict_mode:
            return {"status": "error", "message": "No recipient found and EMAIL_STRICT_MODE is enabled."}
        else:
            to_addrs = ([self.default_to] if self.default_to else [from_address])
        bcc_addrs = bcc or ([self.default_bcc] if self.default_bcc else [])

        attachments = attachments or []
        msg = self._build_message(subject, body, from_address, to_addrs, bcc_addrs, attachments, body_html=body_html)

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
        results: List[Path] = []
        try:
            for entry in docs_dir.iterdir():
                if not entry.is_file():
                    continue
                name = entry.name.lower()
                for phrase in keywords:
                    tokens = [t for t in re.split(r"[^a-z0-9]+", phrase.lower()) if t]
                    if tokens and all(t in name for t in tokens):
                        results.append(entry)
                        break
        except Exception as e:
            logger.warning(f"Error scanning documents by keywords: {e}")
        return results

    def find_documents_by_names(self, names: List[str]) -> List[Path]:
        docs_dir = Path(settings.documents_folder)
        if not docs_dir.exists():
            return []
        results: List[Path] = []
        try:
            normalized = {n.lower().strip() for n in names if isinstance(n, str)}
            for entry in docs_dir.iterdir():
                if not entry.is_file():
                    continue
                if entry.name.lower() in normalized:
                    results.append(entry)
        except Exception as e:
            logger.warning(f"Error scanning documents by names: {e}")
        return results

    def _truncate(self, text: str, limit: int = 700) -> str:
        text = text or ""
        if len(text) <= limit:
            return text
        return text[:limit - 3] + "..."

    def _build_html_package_email(self, meta: Dict[str, Any], app_folder: Path, attachments: List[Path]) -> Tuple[str, str]:
        def safe(s: Optional[str]) -> str:
            return (s or "").replace("<", "&lt;").replace(">", "&gt;")

        opp_id = meta.get("opportunity_id") or ""
        title = meta.get("opportunity_title") or ""
        agency = meta.get("opportunity_agency") or meta.get("agency") or ""

        def read_section(name: str) -> str:
            try:
                p = app_folder / name
                if p.exists():
                    return p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                pass
            return ""

        # Build attachment list
        attach_list = "\n".join(f"<li>{safe(p.name)}</li>" for p in attachments)

        cover = read_section("cover_letter.txt")
        exec_sum = read_section("executive_summary.txt")
        tech = read_section("technical_approach.txt")
        team = read_section("team_qualifications.txt")
        past = read_section("past_performance.txt")

        def block(title: str, content: str) -> str:
            if not content.strip():
                return ""
            return f"<div class='card'><h3>{safe(title)}</h3><pre>{safe(content)}</pre></div>"

        cover_block = block("Cover Letter", cover)
        exec_block = block("Executive Summary", exec_sum)
        tech_block = block("Technical Approach", tech)
        team_block = block("Team Qualifications", team)
        past_block = block("Past Performance", past)

        cta = ""
        try:
            url = meta.get("opportunity_url")
            if url:
                parsed = urlparse(url)
                # Only include simple CTAs for http/https
                if parsed.scheme in {"http", "https"}:
                    cta = f"<div class='cta'><a href='{url}' target='_blank' rel='noopener noreferrer'>View Opportunity</a></div>"
        except Exception:
            pass

        plain_text = (
            f"Application Package for: {title}\n"
            + (f"Agency: {agency}\n" if agency else "")
            + (f"ID: {opp_id}\n" if opp_id else "")
            + "\nAttached Documents:\n"
            + "\n".join(f" - {p.name}" for p in attachments)
        )

        html = f"""
        <html>
          <head>
            <meta charset='utf-8'>
            <style>
              body {{ font-family: Arial, sans-serif; color: #222; }}
              .container {{ max-width: 800px; margin: auto; padding: 24px; }}
              .header h1 {{ margin: 0 0 4px 0; }}
              .subtle {{ color: #666; font-size: 14px; }}
              .meta {{ margin: 12px 0; }}
              .chip {{ display: inline-block; padding: 4px 8px; background: #eef; border-radius: 12px; margin-right: 6px; font-size: 12px; }}
              .content {{ margin-top: 16px; }}
              .card {{ border: 1px solid #ddd; border-radius: 8px; padding: 12px; margin-bottom: 12px; }}
              .cta a {{ display: inline-block; padding: 8px 12px; background: #1976d2; color: #fff; text-decoration: none; border-radius: 6px; }}
              pre {{ white-space: pre-wrap; word-wrap: break-word; font-family: ui-monospace, Menlo, Consolas, monospace; }}
            </style>
          </head>
          <body>
            <div class='container'>
              <div class='header'>
                <h1>Application Package</h1>
                <div class='subtle'>{safe(title)}</div>
              </div>
              <div class='content'>
                <div class='meta'>
                  {f"<span class='chip'>Agency: {safe(agency)}</span>" if agency else ''}
                  {f"<span class='chip'>ID: {safe(opp_id)}</span>" if opp_id else ''}
                </div>
                <div class='card attachments'>
                  <h3>Attached Documents</h3>
                  <ul>{attach_list}</ul>
                  {cta}
                </div>
                {cover_block}
                {exec_block}
                {tech_block}
                {team_block}
                {past_block}
              </div>
              <div class='footer'>
                Sent automatically by your AI Bid Application System.
              </div>
            </div>
          </body>
        </html>
        """
        return plain_text, html

    def send_application_package(self, opportunity_id: str, opportunity_title: str, opportunity_agency: str,
                                 extra_doc_keywords: Optional[List[str]] = None,
                                 extra_doc_names: Optional[List[str]] = None,
                                 to: Optional[List[str]] = None,
                                 selected_only: bool = False) -> Dict[str, Any]:
        """Send the generated application package and extra documents via email."""
        app_folder = self.find_latest_application_folder(opportunity_id)
        if not app_folder:
            return {"status": "error", "message": "Application folder not found for the given opportunity."}

        attachments: List[Path] = []

        if selected_only:
            # Only attach the explicitly selected names, searching both the application folder and documents folder
            names = extra_doc_names or []
            # From the application folder
            for name in names:
                try:
                    p = (app_folder / name)
                    if p.exists() and p.is_file():
                        attachments.append(p)
                except Exception:
                    continue
            # From the documents folder
            if names:
                attachments.extend(self.find_documents_by_names(names))
        else:
            # Default behavior: include the complete application and section files
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
            try:
                rp = p.resolve()
            except Exception:
                # Fallback to string path if resolution fails
                rp = Path(str(p))
            if rp not in seen_paths:
                dedup.append(p)
                seen_paths.add(rp)
        attachments = dedup

        # Load metadata for richer email
        meta: Dict[str, Any] = {
            "opportunity_id": opportunity_id,
            "opportunity_title": opportunity_title,
            "opportunity_agency": opportunity_agency,
        }
        try:
            import json
            meta_path = app_folder / "metadata.json"
            if meta_path.exists():
                with open(meta_path, "r", encoding="utf-8") as f:
                    file_meta = json.load(f)
                # Shallow merge prioritizing existing keys
                for k, v in file_meta.items():
                    meta.setdefault(k, v)
        except Exception as e:
            logger.warning(f"Failed to load metadata.json for email enrichment: {e}")

        # Build beautiful HTML + robust plain text
        plain_text, html = self._build_html_package_email(meta, app_folder, attachments)

        subject = f"Application Package: {opportunity_title} - {opportunity_agency}" if opportunity_agency else f"Application Package: {opportunity_title}"
        # Auto-derive recipients when not explicitly provided
        recipients = to
        if not recipients:
            try:
                recipients = self._derive_recipients(meta, app_folder)
            except Exception as e:
                logger.warning(f"Failed to derive recipients automatically: {e}")
                recipients = None
        # If still no recipients, apply strict mode policy
        if not recipients:
            if settings.email_strict_mode:
                return {"status": "error", "message": "No recipient found; EMAIL_STRICT_MODE prevents fallback sending."}
            # Non-strict: fallback to default_to or from
            if self.default_to:
                recipients = [self.default_to]
            else:
                recipients = [self.default_from or self.username]

        return self.send_email(subject=subject, body=plain_text, body_html=html, to=recipients, attachments=attachments)