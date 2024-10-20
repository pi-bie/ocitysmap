# -*- coding: utf-8 -*-

# ocitysmap, city map and street index generator from OpenStreetMap data
# Copyright (C) 2022 Hartmut Holzgraefe

# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU Affero General Public License as
# published by the Free Software Foundation, either version 3 of the
# License, or any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU Affero General Public License for more details.

# You should have received a copy of the GNU Affero General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import psycopg2
from gettext import gettext

from . import commons
import ocitysmap
import ocitysmap.layoutlib.commons as UTILS

from .GeneralIndex import GeneralIndex, GeneralIndexCategory, GeneralIndexItem

import logging
LOG = logging.getLogger('ocitysmap')

# FIXME: refactoring
# We use the same 10mm as GRAYED_MARGIN_MM in the map multi-page renderer
PAGE_NUMBER_MARGIN_PT  = UTILS.convert_mm_to_pt(10)

# FIXME: make truely configurable
MAX_INDEX_CATEGORY_ITEMS = 300

class TownIndex(GeneralIndex):
    name = "Town"
    description = gettext(u"Cities and towns index")

    def __init__(self, db, renderer, bbox, polygon_wkt, i18n, page_number=None):
        GeneralIndex.__init__(self, db, renderer, bbox, polygon_wkt, i18n, page_number)
        
        # Build the contents of the index
        self._categories = (self._list_villages(db))

    def _list_villages(self, db):
        """Get the list of villages inside the given polygon. Don't
        try to map them onto the grid of squares (there location_str
        field remains undefined).

        Args:
           db (psycopg2 DB): The GIS database

        Returns a list of commons.IndexCategory objects, with their IndexItems
        having no specific grid square location
        """

        # ~ cursor = db.cursor()
        LOG.debug("Getting towns...")

        # ~ result = []
        # ~ current_category = StreetIndexCategory(_(u"Towns"),
                                               # ~ is_street=False)
        # ~ result.append(current_category)

        places = ['city',
		          'town',
                  'municipality']
        sep = "','"
        places_in = "'" + sep.join(places) + "'"
        
        umlaut = {
            "Ä":          _(u"A"),
            "Ö":          _(u"O"),
            "Ü":          _(u"U"),
		}

        return self.get_index_entries(db,
                                      ["point"],
                                      ["Substring(name,1,1)", "name"],
                                      ("TRIM(name) != '' AND place IN (%s)" % places_in),
                                      category_mapping = umlaut,
        )
