import logging
import smtplib
import socket
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from app.infrastructure.email.template_renderer import EmailTemplateRenderer

logger = logging.getLogger(__name__)

_TEMPLATE_DIR = Path(__file__).parent / "templates"

# Two purposes share the same mechanics (token link, single-use, expires) but
# need different copy: "reset" is a password the user already had; "invite"
# is the first password for an account an admin just created for them.
_LINK_PURPOSES = frozenset(("reset", "invite"))


class _IPv4SMTP(smtplib.SMTP):
    """SMTP client that connects over IPv4 only.

    Many container hosts (Render, some Hetzner setups) have no outbound IPv6
    route, but DNS for smtp providers (e.g. Gmail) returns AAAA records
    first. The default socket.create_connection tries those first and fails
    immediately with ENETUNREACH instead of falling back. Resolving to an
    A record explicitly avoids that; the hostname (not the IP) is still what
    gets passed to starttls() for certificate verification.
    """

    def _get_socket(
        self, host: str, port: int, timeout: float
    ) -> socket.socket:
        addr_info = socket.getaddrinfo(host, port, socket.AF_INET, socket.SOCK_STREAM)
        library, socktype, proto, _, sockaddr = addr_info[0]
        sock = socket.socket(library, socktype, proto)
        if timeout is not None:
            sock.settimeout(timeout)
        sock.connect(sockaddr)
        return sock


class EmailSender:
    def __init__(
        self,
        host: str | None,
        port: int,
        user: str | None,
        password: str | None,
        from_address: str,
        timeout_seconds: int = 10,
        renderer: EmailTemplateRenderer | None = None,
    ):
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._from = from_address
        self._timeout_seconds = timeout_seconds
        self._renderer = renderer or EmailTemplateRenderer(_TEMPLATE_DIR)

    def send_password_setup_link(
        self,
        to_email: str,
        link: str,
        purpose: str = "reset",
        language: str | None = None,
    ) -> None:
        """Send a single-use link to set a password.

        ``purpose`` selects the copy: "reset" (the user asked to recover
        access) or "invite" (an admin created the account; this is the
        user's first password). Both share the same token/link mechanics.
        """
        template = purpose if purpose in _LINK_PURPOSES else "reset"
        email = self._renderer.render(template, language, {"link": link})
        self._send(
            to_email,
            subject=email.subject,
            body_text=email.body_text,
            body_html=email.body_html,
            log_context=f"{purpose} link",
            console_link=link,
        )

    def send_welcome_email(
        self,
        to_email: str,
        library_name: str,
        link: str,
        language: str | None = None,
    ) -> None:
        """Notify the admin who just registered a new library — no token
        involved, the admin already chose their password during registration."""
        email = self._renderer.render(
            "welcome", language, {"library_name": library_name, "link": link}
        )
        self._send(
            to_email,
            subject=email.subject,
            body_text=email.body_text,
            body_html=email.body_html,
            log_context="welcome email",
            console_link=link,
        )

    def send_library_invite_email(
        self,
        to_email: str,
        library_name: str,
        inviter_name: str,
        link: str,
        language: str | None = None,
    ) -> None:
        """Tell an existing account they've been added to another library.
        No token/link involved: they already have credentials, they just log
        in and the new library shows up in their picker/switcher."""
        email = self._renderer.render(
            "library_invite", language, {"library_name": library_name, "inviter_name": inviter_name, "link": link}
        )
        self._send(
            to_email,
            subject=email.subject,
            body_text=email.body_text,
            body_html=email.body_html,
            log_context="library invite email",
            console_link=link,
        )

    def send_loan_reminder(
        self,
        to_email: str,
        book_title: str,
        borrower_name: str,
        due_date: datetime,
        language: str | None = None,
    ) -> None:
        """Tell the library a book they lent out is due back soon. No
        token/link involved — this is informational, not actionable."""
        email = self._renderer.render(
            "loan_reminder",
            language,
            {
                "book_title": book_title,
                "borrower_name": borrower_name,
                "due_date": due_date.strftime("%Y-%m-%d"),
            },
        )
        self._send(
            to_email,
            subject=email.subject,
            body_text=email.body_text,
            body_html=email.body_html,
            log_context="loan reminder",
            console_link="",
        )

    def _send(
        self,
        to_email: str,
        *,
        subject: str,
        body_text: str,
        body_html: str,
        log_context: str,
        console_link: str,
    ) -> None:
        if not self._host:
            # SMTP not configured: print to stdout so the link is always visible
            # in the uvicorn console regardless of log-level settings.
            print(
                f"\n[EMAIL CONSOLE]\nTo:      {to_email}\nSubject: {subject}\nLink:    {console_link}\n",
                flush=True,
            )
            logger.warning("[EMAIL CONSOLE] %s for %s: %s", log_context, to_email, console_link)
            return

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = self._from
        msg["To"] = to_email
        msg.attach(MIMEText(body_text, "plain"))
        msg.attach(MIMEText(body_html, "html"))

        try:
            with _IPv4SMTP(self._host, self._port, timeout=self._timeout_seconds) as smtp:
                smtp.ehlo()
                if self._user and self._password:
                    smtp.starttls()
                    smtp.ehlo()  # required again after STARTTLS upgrade
                    smtp.login(self._user, self._password)
                smtp.sendmail(self._from, to_email, msg.as_string())
        except (TimeoutError, OSError, smtplib.SMTPException):
            logger.exception(
                "SMTP send failed (host=%s port=%s to=%s context=%s)",
                self._host,
                self._port,
                to_email,
                log_context,
            )
            raise
