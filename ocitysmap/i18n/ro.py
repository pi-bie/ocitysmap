import re, gettext
from . import i18n, _install_language

class i18n_ro_generic(i18n):
    APPELLATIONS = [ ]

    DETERMINANTS = [ ]

    SPACE_REDUCE = re.compile(r"\s+")
    PREFIX_REGEXP = re.compile(r"^(?P<prefix>(%s)(%s)?)\s?\b(?P<name>.+)" %
                                    ("|".join(APPELLATIONS),
                                     "|".join(DETERMINANTS)), re.IGNORECASE
                                                                 | re.UNICODE)

    def __init__(self, language, locale_path):
        self.language = str(language)
        _install_language(language, locale_path)

    def language_code(self):
        return self.language


