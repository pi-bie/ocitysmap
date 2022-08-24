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

class HealthIndexCategory(GeneralIndexCategory):
    """
    The IndexCategory represents a set of index items that belong to the same
    category, here e.g. having the same 'healthcare=...' value.
    """    

    def __init__(self, name, items=None, is_street=False):
        GeneralIndexCategory.__init__(self, name, items, is_street)


class HealthIndexItem(GeneralIndexItem):
    """
    """

class HealthIndex(GeneralIndex):
    def __init__(self, db, polygon_wkt, i18n, page_number=None):
        GeneralIndex.__init__(self,db, polygon_wkt, i18n, page_number)
        
        # Build the contents of the index
        self._categories = (self._list_amenities(db, polygon_wkt))

    def _list_amenities(self, db, polygon_wkt):
        return self.get_index_entries(db, polygon_wkt,
                                      ["point","polygon"],
                                      ["healthcare", "coalesce(name, '***???***') AS name"],
                                      # "amenity = 'health_post' AND healthcare IS NOT NULL")
                                      "healthcare IS NOT NULL AND healthcare != ''",
        )

