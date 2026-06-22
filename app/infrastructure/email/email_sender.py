import logging
import smtplib
import socket
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


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
        family, socktype, proto, _, sockaddr = addr_info[0]
        sock = socket.socket(family, socktype, proto)
        if timeout is not None:
            sock.settimeout(timeout)
        sock.connect(sockaddr)
        return sock

# Two purposes share the same mechanics (token link, single-use, expires) but
# need different copy: "reset" is a password the user already had; "invite"
# is the first password for an account an admin just created for them.
_TEMPLATES: dict[str, dict[str, dict[str, str]]] = {
    "reset": {
        "en": {
            "subject": "Reset your Jinbocho password",
            "body_text": (
                "You requested a password reset for your Jinbocho account.\n\n"
                "Click the link below to set a new password (valid for 15 minutes):\n\n"
                "{link}\n\n"
                "If you didn't request this, you can safely ignore this email."
            ),
            "body_html": (
                "<p>You requested a password reset for your Jinbocho account.</p>"
                "<p>Click the link below to set a new password (valid for 15 minutes):</p>"
                '<p><a href="{link}">{link}</a></p>'
                "<p>If you didn't request this, you can safely ignore this email.</p>"
            ),
        },
        "it": {
            "subject": "Reimposta la tua password Jinbocho",
            "body_text": (
                "Hai richiesto il reset della password per il tuo account Jinbocho.\n\n"
                "Clicca il link qui sotto per impostare una nuova password (valido 15 minuti):\n\n"
                "{link}\n\n"
                "Se non hai fatto questa richiesta, puoi ignorare questa email."
            ),
            "body_html": (
                "<p>Hai richiesto il reset della password per il tuo account Jinbocho.</p>"
                "<p>Clicca il link qui sotto per impostare una nuova password (valido 15 minuti):</p>"
                '<p><a href="{link}">{link}</a></p>'
                "<p>Se non hai fatto questa richiesta, puoi ignorare questa email.</p>"
            ),
        },
        "es": {
            "subject": "Restablece tu contraseña de Jinbocho",
            "body_text": (
                "Has solicitado restablecer la contraseña de tu cuenta Jinbocho.\n\n"
                "Haz clic en el enlace a continuación para establecer una nueva contraseña (válido 15 minutos):\n\n"
                "{link}\n\n"
                "Si no realizaste esta solicitud, puedes ignorar este correo."
            ),
            "body_html": (
                "<p>Has solicitado restablecer la contraseña de tu cuenta Jinbocho.</p>"
                "<p>Haz clic en el enlace a continuación para establecer una nueva contraseña (válido 15 minutos):</p>"
                '<p><a href="{link}">{link}</a></p>'
                "<p>Si no realizaste esta solicitud, puedes ignorar este correo.</p>"
            ),
        },
        "fr": {
            "subject": "Réinitialisez votre mot de passe Jinbocho",
            "body_text": (
                "Vous avez demandé la réinitialisation du mot de passe de votre compte Jinbocho.\n\n"
                "Cliquez sur le lien ci-dessous pour définir un nouveau mot de passe (valable 15 minutes) :\n\n"
                "{link}\n\n"
                "Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail."
            ),
            "body_html": (
                "<p>Vous avez demandé la réinitialisation du mot de passe de votre compte Jinbocho.</p>"
                "<p>Cliquez sur le lien ci-dessous pour définir un nouveau mot de passe (valable 15 minutes) :</p>"
                '<p><a href="{link}">{link}</a></p>'
                "<p>Si vous n'êtes pas à l'origine de cette demande, ignorez cet e-mail.</p>"
            ),
        },
    },
    "welcome": {
        "en": {
            "subject": "Welcome to Jinbocho!",
            "body_text": (
                'Welcome to Jinbocho! Your family "{family_name}" has been created.\n\n'
                "You can now log in and start cataloging your home library:\n\n"
                "{link}\n\n"
                "Happy reading!"
            ),
            "body_html": (
                '<p>Welcome to Jinbocho! Your family "{family_name}" has been created.</p>'
                "<p>You can now log in and start cataloging your home library:</p>"
                '<p><a href="{link}">{link}</a></p>'
                "<p>Happy reading!</p>"
            ),
        },
        "it": {
            "subject": "Benvenuto su Jinbocho!",
            "body_text": (
                'Benvenuto su Jinbocho! La tua famiglia "{family_name}" è stata creata.\n\n'
                "Puoi accedere e iniziare a catalogare la tua libreria domestica:\n\n"
                "{link}\n\n"
                "Buona lettura!"
            ),
            "body_html": (
                '<p>Benvenuto su Jinbocho! La tua famiglia "{family_name}" è stata creata.</p>'
                "<p>Puoi accedere e iniziare a catalogare la tua libreria domestica:</p>"
                '<p><a href="{link}">{link}</a></p>'
                "<p>Buona lettura!</p>"
            ),
        },
        "es": {
            "subject": "¡Bienvenido a Jinbocho!",
            "body_text": (
                '¡Bienvenido a Jinbocho! Tu familia "{family_name}" ha sido creada.\n\n'
                "Ya puedes iniciar sesión y empezar a catalogar tu biblioteca:\n\n"
                "{link}\n\n"
                "¡Feliz lectura!"
            ),
            "body_html": (
                '<p>¡Bienvenido a Jinbocho! Tu familia "{family_name}" ha sido creada.</p>'
                "<p>Ya puedes iniciar sesión y empezar a catalogar tu biblioteca:</p>"
                '<p><a href="{link}">{link}</a></p>'
                "<p>¡Feliz lectura!</p>"
            ),
        },
        "fr": {
            "subject": "Bienvenue sur Jinbocho !",
            "body_text": (
                'Bienvenue sur Jinbocho ! Votre famille « {family_name} » a été créée.\n\n'
                "Vous pouvez maintenant vous connecter et commencer à cataloguer votre bibliothèque :\n\n"
                "{link}\n\n"
                "Bonne lecture !"
            ),
            "body_html": (
                '<p>Bienvenue sur Jinbocho ! Votre famille « {family_name} » a été créée.</p>'
                "<p>Vous pouvez maintenant vous connecter et commencer à cataloguer votre bibliothèque :</p>"
                '<p><a href="{link}">{link}</a></p>'
                "<p>Bonne lecture !</p>"
            ),
        },
    },
    "invite": {
        "en": {
            "subject": "Welcome to Jinbocho — set your password",
            "body_text": (
                "An account has been created for you on Jinbocho.\n\n"
                "Click the link below to set your password and get started (valid for 7 days):\n\n"
                "{link}\n\n"
                "If you weren't expecting this, you can safely ignore this email."
            ),
            "body_html": (
                "<p>An account has been created for you on Jinbocho.</p>"
                "<p>Click the link below to set your password and get started (valid for 7 days):</p>"
                '<p><a href="{link}">{link}</a></p>'
                "<p>If you weren't expecting this, you can safely ignore this email.</p>"
            ),
        },
        "it": {
            "subject": "Benvenuto su Jinbocho — imposta la tua password",
            "body_text": (
                "È stato creato un account per te su Jinbocho.\n\n"
                "Clicca il link qui sotto per impostare la tua password e iniziare (valido 7 giorni):\n\n"
                "{link}\n\n"
                "Se non ti aspettavi questa email, puoi ignorarla."
            ),
            "body_html": (
                "<p>È stato creato un account per te su Jinbocho.</p>"
                "<p>Clicca il link qui sotto per impostare la tua password e iniziare (valido 7 giorni):</p>"
                '<p><a href="{link}">{link}</a></p>'
                "<p>Se non ti aspettavi questa email, puoi ignorarla.</p>"
            ),
        },
        "es": {
            "subject": "Bienvenido a Jinbocho — establece tu contraseña",
            "body_text": (
                "Se ha creado una cuenta para ti en Jinbocho.\n\n"
                "Haz clic en el enlace a continuación para establecer tu contraseña y comenzar (válido 7 días):\n\n"
                "{link}\n\n"
                "Si no esperabas este correo, puedes ignorarlo."
            ),
            "body_html": (
                "<p>Se ha creado una cuenta para ti en Jinbocho.</p>"
                "<p>Haz clic en el enlace a continuación para establecer tu contraseña y comenzar (válido 7 días):</p>"
                '<p><a href="{link}">{link}</a></p>'
                "<p>Si no esperabas este correo, puedes ignorarlo.</p>"
            ),
        },
        "fr": {
            "subject": "Bienvenue sur Jinbocho — définissez votre mot de passe",
            "body_text": (
                "Un compte a été créé pour vous sur Jinbocho.\n\n"
                "Cliquez sur le lien ci-dessous pour définir votre mot de passe et commencer (valable 7 jours) :\n\n"
                "{link}\n\n"
                "Si vous ne vous attendiez pas à cet e-mail, vous pouvez l'ignorer."
            ),
            "body_html": (
                "<p>Un compte a été créé pour vous sur Jinbocho.</p>"
                "<p>Cliquez sur le lien ci-dessous pour définir votre mot de passe et commencer (valable 7 jours) :</p>"
                '<p><a href="{link}">{link}</a></p>'
                "<p>Si vous ne vous attendiez pas à cet e-mail, vous pouvez l'ignorer.</p>"
            ),
        },
    },
}


class EmailSender:
    def __init__(
        self,
        host: str | None,
        port: int,
        user: str | None,
        password: str | None,
        from_address: str,
        timeout_seconds: int = 10,
    ):
        self._host = host
        self._port = port
        self._user = user
        self._password = password
        self._from = from_address
        self._timeout_seconds = timeout_seconds

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
        templates = _TEMPLATES.get(purpose, _TEMPLATES["reset"])
        lang = language if language in templates else "en"
        tmpl = templates[lang]
        self._send(
            to_email,
            subject=tmpl["subject"],
            body_text=tmpl["body_text"].format(link=link),
            body_html=tmpl["body_html"].format(link=link),
            log_context=f"{purpose} link",
            console_link=link,
        )

    def send_welcome_email(
        self,
        to_email: str,
        family_name: str,
        link: str,
        language: str | None = None,
    ) -> None:
        """Notify the admin who just registered a new family — no token
        involved, the admin already chose their password during registration."""
        templates = _TEMPLATES["welcome"]
        lang = language if language in templates else "en"
        tmpl = templates[lang]
        self._send(
            to_email,
            subject=tmpl["subject"],
            body_text=tmpl["body_text"].format(family_name=family_name, link=link),
            body_html=tmpl["body_html"].format(family_name=family_name, link=link),
            log_context="welcome email",
            console_link=link,
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
