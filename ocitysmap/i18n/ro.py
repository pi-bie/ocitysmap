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

    def user_readable_street(self, name):
        return name

    def upper_unaccent_string(self, s):
        return s.upper()

    def first_letter_equal(self, a, b):
        return self.upper_unaccent_string(a) == self.upper_unaccent_string(b)
