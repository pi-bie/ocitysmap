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
import cairo
import gi
gi.require_version('Rsvg', '2.0')
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Rsvg, Pango, PangoCairo
import ocitysmap.layoutlib.commons as UTILS
from ocitysmap.layoutlib.abstract_renderer import Renderer
import draw_utils

from . import commons
import ocitysmap
import ocitysmap.layoutlib.commons as UTILS

from .commons import IndexCategory, IndexItem, IndexDoesNotFitError 
from .StreetIndex import StreetIndexCategory, StreetIndexItem
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
        cursor = db.cursor()

        sep = "','"
        result = {}

        query = self._build_query(polygon_wkt,
                                  ["point","polygon"],
                                  "healthcare, name",
                                  "amenity = 'health_post' AND healthcare IS NOT NULL")

        self._run_query(cursor, query)

        for amenity_type, amenity_name, linestring in cursor.fetchall():
            # Parse the WKT from the largest linestring in shape
            try:
                s_endpoint1, s_endpoint2 = map(lambda s: s.split(),
                                               linestring[11:-1].split(','))
            except (ValueError, TypeError):
                LOG.exception("Error parsing %s for %s/%s/%s"
                              % (repr(linestring), catname, db_amenity,
                                 repr(amenity_name)))
                continue
            endpoint1 = ocitysmap.coords.Point(s_endpoint1[1], s_endpoint1[0])
            endpoint2 = ocitysmap.coords.Point(s_endpoint2[1], s_endpoint2[0])

            catname = amenity_type

            if not catname in result:
                result[catname] = GeneralIndexCategory(catname, is_street=False)

            result[catname].items.append(StreetIndexItem(amenity_name,
                                                          endpoint1,
                                                          endpoint2,
                                                          self._page_number))

        return [category for catname, category in sorted(result.items()) if (category.items and len(category.items) <= MAX_INDEX_CATEGORY_ITEMS)]

