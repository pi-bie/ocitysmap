import cairo
import math
import os
import logging
import mapnik
import utm

from shapely.geometry import Point
from shapely.ops import transform
from functools import partial

from ocitysmap.draw_utils import draw_simpletext_center
from ocitysmap.layoutlib.commons import convert_pt_to_dots
from ocitysmap.layoutlib.abstract_renderer import Renderer

LOG = logging.getLogger('ocitysmap')

def render(renderer, ctx):
    def pt2px(dot):
        return dot * renderer.dpi / 72.0

    def grid_line(lat1, lon1, lat2, lon2):
        (x1, y1) = renderer._latlon2xy(lat1, lon1)
        (x2, y2) = renderer._latlon2xy(lat2, lon2)

        ctx.save()
        ctx.set_source_rgba(0, 0, 1.0, 0.5)
        ctx.set_line_width(pt2px(1))
        ctx.move_to(x1, y1)
        ctx.line_to(x2, y2)
        ctx.stroke()
        ctx.restore()

    def utm_zonefield2epsg(number, letter):
        if letter.upper() >= 'N':
            return 'epsg:326%02d' % number
        else:
            return 'epsg:327%02d' % number

    def utm_zonefield2proj(number, letter):
        if letter.upper() <= 'M':
            south = '+south '
        else:
            south = ''

        return '+proj=utm +zone=%d %s +ellps=WGS84 +datum=WGS84 +units=m +no_defs' % (number, south)

    def show_grid(lat1, lon1, lat2, lon2):
        if (lat1 > 0 and lat2 < 0) or (lat1 < 0 and lat2 > 0):
            show_grid(lat1, lon1, 0, lon2)
            show_grid(0, lon1, lat2, lon2)
            return

        (west, north, zone1_number, zone1_letter) = utm.from_latlon(lat1, lon1)
        (east, south, zone2_number, zone2_letter) = utm.from_latlon(lat2, lon2)

        polar_zones = ['A','B','Y','Z']

        if zone1_letter in polar_zones or zone2_letter in polar_zones:
            LOG.warning('No support for UTM polar zones yet')
            return

        if zone1_number != zone2_number:
            # TODO: handle special cases for Sweden/Norway and Spitzbergen
            #       zone fileds 32N-V, 32N-X to 37N-X
            split_lon = int(math.floor(lon2/6)) * 6

            show_grid(lat1, lon1, lat2, split_lon - 0.000001)
            show_grid(lat1, split_lon+0.000001, lat2, lon2)
            return

        w_km = int(west/1000)
        e_km = int(east/1000)
        n_km = int(north/1000)
        s_km = int(south/1000)

        LOG.warning("foo %f %f - %f %f - %d %d" % (lat1, lon1, lat2, lon2, n_km, s_km))

        for v in range(w_km, e_km):
            (lat1, lon1) = utm.to_latlon(v * 1000, n_km * 1000, zone1_number, zone1_letter)
            (lat2, lon2) = utm.to_latlon(v * 1000, s_km * 1000, zone1_number, zone1_letter)
            grid_line(lat1, lon1, lat2, lon2)

        for h in range(s_km, n_km):
            (lat1, lon1) = utm.to_latlon(w_km * 1000, h * 1000, zone1_number, zone1_letter)
            (lat2, lon2) = utm.to_latlon(e_km * 1000, h * 1000, zone1_number, zone1_letter)
            grid_line(lat1, lon1, lat2, lon2)

    bbox = renderer._map_canvas.get_actual_bounding_box()

    (lat1, lon1) = bbox.get_top_left()
    (lat2, lon2) = bbox.get_bottom_right()

    show_grid(lat1, lon1, lat2, lon2)

