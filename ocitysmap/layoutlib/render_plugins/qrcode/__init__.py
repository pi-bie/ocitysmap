import cairo
import os
import sys
import qrcode
import qrcode.image.svg
import gi
gi.require_version('Rsvg', '2.0')
from gi.repository import Rsvg

from io import BytesIO

from ocitysmap.layoutlib.commons import convert_pt_to_dots
from ocitysmap.layoutlib.abstract_renderer import Renderer

import logging
LOG = logging.getLogger('ocitysmap')

def render(renderer, ctx):
    if renderer.rc.qrcode_text:
        LOG.info("QR text: %s" % renderer.rc.qrcode_text)
        x  = convert_pt_to_dots(renderer._map_coords[0], renderer.dpi)
        y  = convert_pt_to_dots(renderer._map_coords[1], renderer.dpi)
        w  = convert_pt_to_dots(renderer._map_coords[2], renderer.dpi)
        h  = convert_pt_to_dots(renderer._map_coords[3], renderer.dpi)
        W  = convert_pt_to_dots(renderer.paper_width_pt)
        
        size = convert_pt_to_dots(max(renderer.paper_width_pt, renderer.paper_height_pt),
                                  renderer.dpi) / 12
        
        img = qrcode.make(renderer.rc.qrcode_text,
                          image_factory=qrcode.image.svg.SvgPathFillImage)
        svgstr = BytesIO()
        img.save(svgstr);
        
        rsvg = Rsvg.Handle()
        svg = rsvg.new_from_data(svgstr.getvalue())
        svgstr.close()
        
        ctx.save()
        ctx.translate(x + w - size,
                      y + h - size)
        ctx.move_to(0, 0)
        factor = size / svg.props.height
        ctx.scale(factor, factor)
        svg.render_cairo(ctx)
        ctx.restore()
