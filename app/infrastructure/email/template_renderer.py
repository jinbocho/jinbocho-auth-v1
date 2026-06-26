from dataclasses import dataclass
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, StrictUndefined, TemplateNotFound, select_autoescape

_SUPPORTED_LANGUAGES = frozenset(("en", "it", "es", "fr"))
_DEFAULT_LANGUAGE = "en"


@dataclass(frozen=True)
class RenderedEmail:
    subject: str
    body_text: str
    body_html: str


class EmailTemplateRenderer:
    """Loads and renders email templates from the filesystem.

    Each template lives under {template_dir}/{type}/{lang}/ as three files:
    subject.txt, body.txt, body.html. Variables use Jinja2 syntax {{ var }}.
    HTML files are auto-escaped; plain-text files are not.
    """

    def __init__(self, template_dir: Path) -> None:
        self._env = Environment(
            loader=FileSystemLoader(str(template_dir)),
            autoescape=select_autoescape(["html"]),
            undefined=StrictUndefined,
            trim_blocks=False,
            lstrip_blocks=False,
        )

    def render(
        self,
        template: str,
        language: str | None,
        context: dict[str, object],
    ) -> RenderedEmail:
        lang = language if language in _SUPPORTED_LANGUAGES else _DEFAULT_LANGUAGE
        try:
            subject = self._env.get_template(f"{template}/{lang}/subject.txt").render(context)
            body_text = self._env.get_template(f"{template}/{lang}/body.txt").render(context)
            body_html = self._env.get_template(f"{template}/{lang}/body.html").render(context)
        except TemplateNotFound as exc:
            raise RuntimeError(
                f"Email template not found: {exc.name!r} "
                f"(template={template!r}, lang={lang!r})"
            ) from exc
        return RenderedEmail(
            subject=subject.strip(),
            body_text=body_text,
            body_html=body_html,
        )
