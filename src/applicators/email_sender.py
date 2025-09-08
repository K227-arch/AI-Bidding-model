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
                   bcc: Optional[List[str]] = None, body_html: Optional[str] = None) -> Dict[str, Any]:
        """Send an email with optional attachments and optional HTML body."""
        from_address = from_addr or (self.default_from or self.username)
        if not from_address:
            return {"status": "error", "message": "No sender address configured. Set SMTP_FROM or SMTP_USERNAME."}
        to_addrs = to or ([self.default_to] if self.default_to else [from_address])
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

    def _truncate(self, text: str, limit: int = 700) -> str:
        if len(text) <= limit:
            return text
        return text[:limit].rsplit(" ", 1)[0] + "…"

    def _read_section(self, app_folder: Path, filename: str) -> Optional[str]:
        p = app_folder / filename
        if p.exists():
            try:
                return p.read_text(encoding="utf-8", errors="ignore").strip()
            except Exception:
                return None
        return None

    def _build_html_package_email(self, meta: Dict[str, Any], app_folder: Path, attachments: List[Path]) -> Tuple[str, str]:
        """Return (plain_text, html) body for the application email."""
        title = meta.get("opportunity_title") or meta.get("title") or "Bid/Application"
        agency = meta.get("opportunity_agency") or meta.get("agency") or ""
        opp_id = meta.get("opportunity_id") or meta.get("id") or ""
        view_url = meta.get("view_url") or meta.get("opportunity_url") or ""

        cover = self._read_section(app_folder, "cover_letter.txt")
        exec_summ = self._read_section(app_folder, "executive_summary.txt")
        tech = self._read_section(app_folder, "technical_approach.txt")
        team = self._read_section(app_folder, "team_qualifications.txt")
        past = self._read_section(app_folder, "past_performance.txt")

        # Plain-text fallback
        lines = [
            f"Application Package: {title}",
            (f"Agency: {agency}" if agency else None),
            (f"Opportunity ID: {opp_id}" if opp_id else None),
            (f"View Online: {view_url}" if view_url else None),
            "",
            "Attached documents:",
        ]
        for att in attachments:
            lines.append(f" - {att.name}")
        lines.append("")
        if cover:
            lines.append("Cover Letter (preview):")
            lines.append(self._truncate(cover, 600))
            lines.append("")
        if exec_summ:
            lines.append("Executive Summary (preview):")
            lines.append(self._truncate(exec_summ, 600))
            lines.append("")
        plain_text = "\n".join([l for l in lines if l is not None])

        # HTML body with inline CSS
        styles = """
        <style>
          body { background:#f6f8fb; margin:0; padding:0; font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, Cantarell, 'Helvetica Neue', Arial, 'Noto Sans', sans-serif; color:#1f2937; }
          .container { max-width: 760px; margin: 24px auto; background:#ffffff; border-radius: 12px; box-shadow: 0 2px 10px rgba(0,0,0,0.06); overflow:hidden; }
          .header { background: linear-gradient(135deg, #2563eb, #1e40af); color:#fff; padding: 20px 24px; }
          .header h1 { margin:0; font-size: 22px; letter-spacing: 0.2px; }
          .subtle { opacity: 0.9; font-size: 13px; }
          .content { padding: 22px 24px; }
          .meta { display:flex; flex-wrap: wrap; gap: 12px; margin-bottom: 16px; }
          .chip { background:#eef2ff; color:#3730a3; border:1px solid #c7d2fe; padding:6px 10px; border-radius: 999px; font-size:12px; }
          .card { border:1px solid #e5e7eb; border-radius:10px; padding:14px; margin: 14px 0; }
          .card h3 { margin:0 0 8px 0; font-size:15px; color:#111827; }
          .attachments ul { padding-left: 18px; margin: 8px 0 0 0; }
          .cta { margin-top: 16px; }
          .btn { display:inline-block; background:#2563eb; color:#fff !important; text-decoration:none; padding:10px 14px; border-radius:8px; }
          .footer { color:#6b7280; font-size:12px; padding: 14px 24px 22px; }
          a { color:#2563eb; }
          pre { white-space: pre-wrap; word-wrap: break-word; font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, 'Liberation Mono', monospace; background:#f9fafb; padding:12px; border-radius:8px; border:1px solid #e5e7eb; }
        </style>
        """
        safe = lambda s: (s or "").replace("<", "&lt;").replace(">", "&gt;")
        attach_list = "".join([f"<li>{safe(a.name)}</li>" for a in attachments])
        cover_block = f"<div class='card'><h3>Cover Letter (preview)</h3><pre>{safe(self._truncate(cover,700))}</pre></div>" if cover else ""
        exec_block = f"<div class='card'><h3>Executive Summary (preview)</h3><pre>{safe(self._truncate(exec_summ,700))}</pre></div>" if exec_summ else ""
        tech_block = f"<div class='card'><h3>Technical Approach (preview)</h3><pre>{safe(self._truncate(tech,700))}</pre></div>" if tech else ""
        team_block = f"<div class='card'><h3>Team Qualifications (preview)</h3><pre>{safe(self._truncate(team,700))}</pre></div>" if team else ""
        past_block = f"<div class='card'><h3>Past Performance (preview)</h3><pre>{safe(self._truncate(past,700))}</pre></div>" if past else ""
        cta = f"<div class='cta'><a class='btn' href='{view_url}' target='_blank' rel='noopener'>View Opportunity Online</a></div>" if view_url else ""

        html = f"""
        <!doctype html>
        <html>
          <head>
            <meta charset='utf-8'>
            <meta name='viewport' content='width=device-width, initial-scale=1'>
            {styles}
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

        return self.send_email(subject=subject, body=plain_text, body_html=html, to=to, attachments=attachments)