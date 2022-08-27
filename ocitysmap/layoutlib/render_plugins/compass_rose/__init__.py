import cairo
import os
import sys
import logging
from ocitysmap.layoutlib.commons import convert_pt_to_dots
from ocitysmap.layoutlib.abstract_renderer import Renderer

LOG = logging.getLogger('ocitysmap')

def render(renderer, ctx):
    """ Add a compass rose to the map

    Parameters
    ----------
    renderer : ocitysmap.Renderer
        The current active renderer
    ctx : cairo.Context
        The Cairo context to draw into

    Returns
    -------
    void
    """

    # find the actual compass rose SVG image relative to the current file path
    svg_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..', '..', '..', 'images', 'compass-rose.svg'))

    # or alternatively: in system install path
    if not os.path.exists(svg_path):
        svg_path = os.path.join(
            sys.exec_prefix, 'share', 'images', 'ocitysmap', 'compass-rose.svg')

    # bail out if not found in either location
    if not os.path.exists(svg_path):
        LOG.warning("No compass rose image found")
        return

    # scale output size height to 5% of the paper size height
    h = convert_pt_to_dots(0.05 * renderer.paper_height_pt, renderer.dpi)

    # load and scale the SVG image
    rose_grp, rose_width = Renderer._get_svg(ctx, svg_path, h)

    # determine image position depending on renderer used
    if type(renderer).__name__ == "MultiPageRenderer":
        x = 0
        y = 0
    else:
        x = convert_pt_to_dots(renderer._map_coords[0], renderer.dpi)
        y = convert_pt_to_dots(renderer._map_coords[1], renderer.dpi)

    # output image on top of the current cairo context
    ctx.save()
    ctx.translate(x + h/2, y + h/2)
    ctx.set_source(rose_grp)
    ctx.paint_with_alpha(0.75)
    ctx.stroke()
    ctx.restore()

