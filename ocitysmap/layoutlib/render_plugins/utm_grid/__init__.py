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

    def superscript(i):
        if i == 0:
            return '\N{SUPERSCRIPT ZERO}'
        if i == 1:
            return '\N{SUPERSCRIPT ONE}'
        elif i == 2:
            return '\N{SUPERSCRIPT TWO}'
        elif i == 3:
            return '\N{SUPERSCRIPT THREE}'
        elif i == 4:
            return '\N{SUPERSCRIPT FOUR}'
        elif i == 5:
            return '\N{SUPERSCRIPT FIVE}'
        elif i == 6:
            return '\N{SUPERSCRIPT SIX}'
        elif i == 7:
            return '\N{SUPERSCRIPT SEVEN}'
        elif i == 8:
            return '\N{SUPERSCRIPT EIGHT}'
        elif i == 9:
            return '\N{SUPERSCRIPT NINE}'
        else:
            return i

    def beautify_km(km):
        txt = ''

        t1 = int(km/100)
        t2 = int(km)%100

        t11 =int(t1/10)
        t12 =int(t1)%10

        if t11 > 0:
            txt = txt + superscript(t11)
        txt = txt + superscript(t12)

        txt = txt + ("%02d" % t2)

        return txt

    def utm_zonefield2proj(number, letter):
        if letter.upper() <= 'M':
            south = '+south '
        else:
            south = ''

        return '+proj=utm +zone=%d %s +ellps=WGS84 +datum=WGS84 +units=m +no_defs' % (number, south)

    def show_grid(lat1, lon1, lat2, lon2):
        if (lat1 > 0 and lat2 < 0):
            show_grid(lat1, lon1, 0.000001, lon2)
            show_grid(-0.000001, lon1, lat2, lon2)
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

        (x1, y1) = renderer._latlon2xy(lat1, lon1)
        (x2, y2) = renderer._latlon2xy(lat2, lon2)

        ctx.save()
        ctx.rectangle(x1, y1, x2, y2)
        ctx.clip()

        w_km = math.floor(west/1000)
        e_km = math.ceil(east/1000)
        n_km = math.ceil(north/1000)
        s_km = math.floor(south/1000)

        for v in range(w_km, e_km):
            (lat1, lon1) = utm.to_latlon(v * 1000, n_km * 1000, zone1_number, zone1_letter)
            (lat2, lon2) = utm.to_latlon(v * 1000, s_km * 1000, zone1_number, zone1_letter)
            grid_line(lat1, lon1, lat2, lon2)

        for h in range(s_km, n_km):
            (lat1, lon1) = utm.to_latlon(w_km * 1000, h * 1000, zone1_number, zone1_letter)
            (lat2, lon2) = utm.to_latlon(e_km * 1000, h * 1000, zone1_number, zone1_letter)
            grid_line(lat1, lon1, lat2, lon2)

        ctx.save()
        ctx.set_source_rgba(0, 0, 0.5, 0.5)
        draw_simpletext_center(ctx, ("%d%s" % (zone1_number, zone1_letter)), 27, 20)
        ctx.restore()

        for v in range(w_km, e_km):
            (lat1, lon1) = utm.to_latlon(v * 1000, n_km * 1000, zone1_number, zone1_letter)
            (x1, y1) = renderer._latlon2xy(lat1, lon1)

            ctx.save()
            ctx.set_source_rgba(0, 0, 0.5, 0.5)
            draw_simpletext_center(ctx, beautify_km(v), x1 + 12, 20)
            ctx.restore()

        for h in range(s_km, n_km):
            (lat1, lon1) = utm.to_latlon(w_km * 1000, h * 1000, zone1_number, zone1_letter)
            (x1, y1) = renderer._latlon2xy(lat1, lon1)

            ctx.save()
            ctx.set_source_rgba(0, 0, 0.5, 0.5)
            draw_simpletext_center(ctx, beautify_km(h), 27, y1 + 5)
            ctx.restore()

        ctx.restore()

    bbox = renderer._map_canvas.get_actual_bounding_box()

    (lat1, lon1) = bbox.get_top_left()
    (lat2, lon2) = bbox.get_bottom_right()

    show_grid(lat1, lon1, lat2, lon2)

