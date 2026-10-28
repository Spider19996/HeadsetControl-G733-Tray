"""Übersetzungen. Quelltexte im Code sind deutsch: tr("Text") liefert die Übersetzung in der gewählten Sprache.

Jede Sprache ist ein Modul g733_tray/lang/<code>.py mit dem Wörterbuch STRINGS (Schlüssel = deutscher Text).
Fehlt ein Eintrag, wird der deutsche Text angezeigt. N_("Text") markiert einen Text nur zum Übersetzen
(wird erst bei der Anzeige mit tr() übersetzt), z. B. für Konstanten.
"""
import importlib
import logging

log = logging.getLogger("g733.i18n")

SOURCE_LANGUAGE = "de"
FALLBACK_LANGUAGE = "en"  # wenn die Systemsprache nicht angeboten wird
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
_current = SOURCE_LANGUAGE


def N_(text):
    """Markiert einen Text zum Übersetzen, ohne ihn jetzt zu übersetzen."""
    return text


def tr(text):
    return _catalog.get(text, text)


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


def set_language(setting):
    """Stellt die Sprache ein (Code oder "auto") und gibt den tatsächlich verwendeten Code zurück."""
    global _catalog, _current
    code = resolve(setting)
    catalog = {}
    if code != SOURCE_LANGUAGE:
        try:
            catalog = importlib.import_module(f"{__package__}.lang.{code}").STRINGS
        except (ImportError, AttributeError) as err:
            log.warning("language file %s not loadable: %s", code, err)
            code = SOURCE_LANGUAGE
    _catalog, _current = catalog, code
    return code
