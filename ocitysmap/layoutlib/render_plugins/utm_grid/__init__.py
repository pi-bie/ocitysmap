import cairo
import math
import os
import logging
import mapnik
import utm

from ocitysmap.draw_utils import draw_simpletext_center
from ocitysmap.layoutlib.commons import convert_pt_to_dots
from ocitysmap.layoutlib.abstract_renderer import Renderer

LOG = logging.getLogger('ocitysmap')

def render(renderer, ctx):
    def pt2px(dot):
        return dot * renderer.dpi / 72.0

    LOG.warning("-----------------------")

    bbox = renderer._map_canvas.get_actual_bounding_box()

    (lat, lon) = bbox.get_top_left()
    (west, north, zone_number, zone_letter) = utm.from_latlon(lat, lon)
    LOG.warning("UTM #1 %f %f" % (west, north))
    (lat, lon) = bbox.get_bottom_right()
    (east, south, zone_number, zone_letter) = utm.from_latlon(lat, lon)
    LOG.warning("UTM #2 %f %f" % (east, south))

    w_km = int(west/1000)
    e_km = int(east/1000)
    n_km = int(north/1000)
    s_km = int(south/1000)

    for v in range(w_km - 1, e_km + 1):
        LOG.warning("vertical line %d %d-%d", v, n_km + 1, s_km - 1)
        (lat1, lon1) = utm.to_latlon(v * 1000, (n_km + 1) * 1000, zone_number, zone_letter)
        (lat2, lon2) = utm.to_latlon(v * 1000, (s_km - 1) * 1000, zone_number, zone_letter)

        (x1, y1) = renderer._latlon2xy(lat1, lon1)
        (x2, y2) = renderer._latlon2xy(lat2, lon2)

        ctx.save()
        ctx.set_source_rgba(0, 0, 1.0, 0.5)
        ctx.set_line_width(pt2px(1))
        ctx.move_to(x1, y1)
        ctx.line_to(x2, y2)
        ctx.stroke()
        ctx.restore()
        

        
    for h in range(s_km - 1, n_km + 1):
        LOG.warning("horizontal line %d %d-%d", h, e_km, w_km)
        (lat1, lon1) = utm.to_latlon((w_km - 1) * 1000, h * 1000, zone_number, zone_letter)
        (lat2, lon2) = utm.to_latlon((e_km + 1) * 1000, h * 1000, zone_number, zone_letter)

        (x1, y1) = renderer._latlon2xy(lat1, lon1)
        (x2, y2) = renderer._latlon2xy(lat2, lon2)

        ctx.save()
        ctx.set_source_rgba(0, 0, 1.0, 0.5)
        ctx.set_line_width(pt2px(1))
        ctx.move_to(x1, y1)
        ctx.line_to(x2, y2)
        ctx.stroke()
        ctx.restore()


    LOG.warning("-----------------------")
