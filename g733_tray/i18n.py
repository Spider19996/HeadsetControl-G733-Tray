"""Übersetzungen. Im Code steht an jeder Textstelle eine Text-ID: tr("menu.quit") liefert den Text in der gewählten Sprache.

Jede Sprache (auch Deutsch) ist ein Modul g733_tray/lang/<code>.py mit dem Wörterbuch STRINGS (Schlüssel = Text-ID).
Fehlt eine ID in der gewählten Sprache, wird der englische Text angezeigt, fehlt sie auch dort, die ID selbst.
N_("id") markiert eine ID nur zum Übersetzen (wird erst bei der Anzeige mit tr() übersetzt), z. B. für Konstanten.
"""
import importlib
import logging

log = logging.getLogger("g733.i18n")

FALLBACK_LANGUAGE = "en"  # Ersatz für fehlende Einträge und wenn die Systemsprache nicht angeboten wird
AUTO = "auto"

# Sprachcode -> Eigenname (wird in der Auswahl in der jeweiligen Sprache angezeigt)
LANGUAGES = {
    "de": "Deutsch",
    "en": "English",
    "es": "Español",
    "fr": "Français",
    "it": "Italiano",
    "pt": "Português",
    "nl": "Nederlands",
    "pl": "Polski",
    "ru": "Русский",
    "tr": "Türkçe",
    "zh": "简体中文",
    "ja": "日本語",
}

_catalog = {}
_fallback = {}
_current = FALLBACK_LANGUAGE


def N_(text_id):
    """Markiert eine Text-ID zum Übersetzen, ohne sie jetzt zu übersetzen."""
    return text_id


def tr(text_id):
    try:
        return _catalog[text_id]
    except KeyError:
        return _fallback.get(text_id, text_id)


def current_language():
    return _current


def system_language():
    """Sprachcode der Systemsprache, sonst Englisch."""
    from PyQt6.QtCore import QLocale
    for tag in QLocale.system().uiLanguages():
        code = tag.replace("_", "-").split("-")[0].lower()
        if code in LANGUAGES:
            return code
    return FALLBACK_LANGUAGE


def resolve(setting):
    """"auto" -> Systemsprache; unbekannte Codes -> Englisch."""
    if setting == AUTO:
        return system_language()
    return setting if setting in LANGUAGES else FALLBACK_LANGUAGE


def _load(code):
    return importlib.import_module(f"{__package__}.lang.{code}").STRINGS


def set_language(setting):
    """Stellt die Sprache ein (Code oder "auto") und gibt den tatsächlich verwendeten Code zurück."""
    global _catalog, _fallback, _current
    code = resolve(setting)
    fallback = _load(FALLBACK_LANGUAGE)
    try:
        catalog = _load(code)
    except (ImportError, AttributeError) as err:
        log.warning("language file %s not loadable: %s", code, err)
        code, catalog = FALLBACK_LANGUAGE, fallback
    _catalog, _fallback, _current = catalog, fallback, code
    return code


set_language(FALLBACK_LANGUAGE)  # bis das Programm die Sprache wählt
