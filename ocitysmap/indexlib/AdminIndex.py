# -*- coding: utf-8 -*-

# ocitysmap, city map and street index generator from OpenStreetMap data
# Copyright (C) 2022 Hartmut Holzgraefe
# Copyright (C) 2025 pi-bie

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
from sys import maxsize
from gettext import gettext

import draw_utils

from . import commons
import ocitysmap
import ocitysmap.layoutlib.commons as UTILS
from ocitysmap.coords import Point

from .GeneralIndex import GeneralIndex, GeneralIndexCategory, GeneralIndexItem

import logging
LOG = logging.getLogger('ocitysmap')

# FIXME: refactoring
# We use the same 10mm as GRAYED_MARGIN_MM in the map multi-page renderer
PAGE_NUMBER_MARGIN_PT  = UTILS.convert_mm_to_pt(10)

# FIXME: make truely configurable
MAX_INDEX_CATEGORY_ITEMS = 300

class AdminIndex(GeneralIndex):
    name = "Admin"
    description = gettext(u"Administrative boundaries index")

    def __init__(self, db, renderer, bbox, polygon_wkt, i18n, page_number=None):
        GeneralIndex.__init__(self, db, renderer, bbox, polygon_wkt, i18n, page_number)

        # Build the contents of the index
        self._categories = (self._list_boundaries(db))

    def get_index_entries(self, db, tables, columns, where, group=False, category_mapping=None, max_category_items=maxsize, join=None, debug=False):
        """
        Generates an index entry from query snippets. The generated query is supposed
        to return three columns: category name, index entry text, and the entries geometry.

        Parameters
        ----------
        db : psycopg2 database connection
	    The database to retrieve the information from
	tables: list of str
	    osm2pgsql model tables to retrive data from, one or more of
	    "point", "line", "polygon", "roads"
	columns: list of str
            Two SQL expressions returning the category name (1st) and
	    actual index entry text (2nd)
	where: str
	    WHERE condition to filter for valid index entries
	group: bool, optional
	    Whether to merge multiple items of same category and entry text
    category_mapping: dict, optional
            Map SQL category results to more readable values
    max_category_items: int, optional
            Maximum number of entries before a categorie is dismissed

        Returns
        -------
        dict
            A dictionary of IndexCategory objects with category name as key
        """
        cursor = db.cursor()
        result = {}

        query = self._build_query(tables, columns, where, group, join=join)

        self._run_query(cursor, query, debug)

        for amenity_type, amenity_name, linestring in cursor.fetchall():
            # Parse the WKT from the largest linestring in shape
            try:
                s_endpoint1, s_endpoint2 = map(lambda s: s.split(),
                                               linestring[11:-1].split(','))
            except (ValueError, TypeError):
                LOG.exception("Error parsing %s for %s"
                              % (repr(linestring),
                                 repr(amenity_name)))
                continue
            endpoint1 = Point(s_endpoint1[1], s_endpoint1[0])
            endpoint2 = Point(s_endpoint2[1], s_endpoint2[0])

            if category_mapping is not None and amenity_type in category_mapping:
                catname = category_mapping[amenity_type]
            else:
                catname = amenity_type

            if not catname in result:
                result[catname] = GeneralIndexCategory(catname, is_street=False)

            result[catname].items.append(AdminIndexItem(amenity_name,
                                                          endpoint1,
                                                          endpoint2,
                                                          self._page_number))

        return [category for catname, category in sorted(result.items()) if (category.items and len(category.items) <= max_category_items)]

    def _list_boundaries(self, db):
        """Get the list of administrative boundaries inside the given polygon. Don't
        try to map them onto the grid of squares (their location_str
        field remains undefined).

        Args:
           db (psycopg2 DB): The GIS database

        Returns a list of commons.IndexCategory objects, with their IndexItems
        having no specific grid square location
        """

        # ~ cursor = db.cursor()
        LOG.debug("Getting boundaries...")

        levels = ['6']
        sep = "','"
        levels_in = "'" + sep.join(levels) + "'"

        return self.get_index_entries(db,
                                      ["polygon"],
                                      ["'Politische Grenzen'", "Coalesce(tags->'license_plate_code','') ||'\t'|| name || Coalesce(', ' || (SELECT name FROM planet_osm_polygon p WHERE ST_Covers(p.way, tab1.way) AND boundary = 'administrative' AND admin_level = '5' LIMIT 1),'') || Coalesce(', '||(SELECT name FROM planet_osm_polygon p WHERE ST_Covers(p.way, tab1.way) AND boundary = 'administrative' AND admin_level = '4' LIMIT 1),'')"],
                                      ("TRIM(name) != '' AND boundary = 'administrative' AND admin_level IN (%s)" % levels_in),
        )

class AdminIndexItem(GeneralIndexItem):
    """
    An AdminIndexItem represents one item in the admin index (a county/Kreis). It
    contains the item label (street name, POI name or description) and the
    humanized squares description, but doesn't print the latter.
    """
    def draw(self, rtl, ctx, pc, column_layout, fascent, fheight,
             baseline_x, baseline_y,
             label_layout=None, label_height=0, location_width=0):
        """Draw this index item to the provided Cairo context. It prints the
        label, with respect to the
        RTL setting.

        Args:
            rtl (boolean): right-to-left localization.
            ctx (cairo.Context): the Cairo context to draw to.
            pc (pangocairo.PangoCairo): the PangoCairo context for text
                drawing.
            column_layout (pango.Layout): the Pango layout to use for text
                rendering, pre-configured with the appropriate font.
            fascent (int): font ascent.
            fheight (int): font height.
            baseline_x (int): X axis coordinate of the baseline.
            baseline_y (int): Y axis coordinate of the baseline.
        Optional args (in case of label wrapping):
            label_layout (pango.Layout): the Pango layout to use for text
                rendering, in case the label should be wrapped
            label_height (int): height of the big label
            location_width (int): width of the 'location' part
        """

        # Fallbacks in case we dont't have a wrapping label
        if label_layout == None:
            label_layout = column_layout
        if label_height == 0:
            label_height = fheight

        ctx.save()
        ctx.set_source_rgb(0.0, 0.0, 0.0)
        if not rtl:
            # _, _,
            _, line_start = draw_utils.draw_text_left(ctx, label_layout,
                                            fascent,
                                            baseline_x, baseline_y,
                                            self.label)
        else:
            line_end, _ = draw_utils.draw_text_right(ctx, label_layout,
                                                     fascent,
                                                     (baseline_x
                                                      + location_width),
                                                     baseline_y,
                                                     self.label)
        ctx.restore()
