from gettext import gettext

import cairo
import os
import gi
gi.require_version('Rsvg', '2.0')
gi.require_version('Pango', '1.0')
gi.require_version('PangoCairo', '1.0')
from gi.repository import Rsvg, Pango, PangoCairo
import shapely.wkt
import logging
import mapnik
assert mapnik.mapnik_version() >= 300000, \
    "Mapnik module version %s is too old, see ocitysmap's INSTALL " \
    "for more details." % mapnik.mapnik_version_string()
import math
from ocitysmap.layoutlib import commons
import ocitysmap
from ocitysmap.layoutlib.abstract_renderer import Renderer
from ocitysmap.indexlib.GeneralIndex import GeneralIndexRenderer
from ocitysmap.layoutlib.single_page_renderers import SinglePageRenderer
from ocitysmap.indexlib.commons import IndexDoesNotFitError
import draw_utils
from ocitysmap import draw_utils, maplib
from ocitysmap.maplib.map_canvas import MapCanvas

LOG = logging.getLogger('ocitysmap')

class SinglePageRendererIndexFoldable(SinglePageRenderer):
    """
    This renderer adds a side index to the basic SinglePageRenderer
    """
    name = 'single_page_index_foldable'
    description = gettext(u'Full-page layout with title in top left corner and the index on the side.')

    def __init__(self, db, rc, tmpdir, dpi, file_prefix):
        """
        Create the renderer.

        Parameters
        ----------
           db : psycopg2 DB
               GIS database connection handle
           rc : RenderingConfiguration
               Rendering configurationparameters.
           tmpdir : str
               Path to a temp dir that can hold temp files the renderer creates.
           dpi : int
               Output resolution for bitmap formats
           file_prefix : str
               File name refix for all output file formats to be generated
        """
        SinglePageRenderer.__init__(self, db, rc, tmpdir, dpi, file_prefix, 'side', True)

    def _get_map_coords(self, index_position):
        """ Determine actual map output dimensions

        Parameters
        ----------
        index_position : str, optional
            One of 'side' or 'bottom' if an index is to be rendered
            on the same page.

        Returns
        -------
        list of float
            A list containing x and y coordinates of the upper left
            of the actual map render area, and its widht and height.
        """

        x = Renderer.PRINT_SAFE_MARGIN_PT + self._cover_width_pt
        y = Renderer.PRINT_SAFE_MARGIN_PT
        w = self._usable_area_width_pt
        h = self._usable_area_height_pt

        if index_position is None or index_position == 'extra_page':
            # No index displayed
            pass
        elif index_position == 'side':
            # Index present, displayed on the side
            pass
        elif index_position == 'bottom':
            # Index present, displayed at the bottom -> map on top
            h = h - self._index_area.h
        else:
            raise AssertionError("Invalid index position %s"
                                 % repr(index_position))

        return (x, y, w, h)

    def _draw_title(self, ctx, w_dots, h_dots, font_face):
        """ Draw map title

        Draw the title as a cover in the top left corner, in a 
        cover_width * cover_height rectangle.

        Parameters
        ----------
        ctx : cairo.Context
            The context to draw into
        w_dots : float
            ignored
        h_dots : float
            ignored
        font_face : str
            Pango font name

        Returns
        -------
        void
        """

        w_dots = commons.convert_pt_to_dots(self._cover_width_pt, self.dpi)
        h_dots = commons.convert_pt_to_dots(self._cover_height_pt, self.dpi)
        margin_dots = 0.0625 * min(w_dots, h_dots)
        cover_usable_height_dots = h_dots - 2 * margin_dots
        cover_usable_width_dots = w_dots - 2 * margin_dots

        # Title background bar
        ctx.save()
        ctx.set_source_rgb(0.8, 0.9, 0.96) # TODO: make title bar color configurable?
        ctx.rectangle(0, 0, w_dots, h_dots)
        ctx.fill()
        ctx.restore()

        # Retrieve and paint logo to put to the right of the title
        logo_width = 0
        if self.rc.logo:
            ctx.save()
            grp, logo_width, logo_height = self._get_logo(ctx, self.rc.logo, 0.45 * cover_usable_width_dots, cover_usable_height_dots * 0.2)
            # TODO catch exceptions and just print warning instead?
            ctx.translate(margin_dots, margin_dots + (0.2 * cover_usable_height_dots - logo_height)/2 )
            ctx.set_source(grp)
            ctx.paint_with_alpha(0.5)
            ctx.restore()

        # Retrieve and paint the extra logo to put to the left of the title
        logo_width2 = 0
        if self.rc.extra_logo:
            ctx.save()
            grp, logo_width2, logo_height2 = self._get_logo(ctx, self.rc.extra_logo, 0.45 * cover_usable_width_dots, cover_usable_height_dots * 0.2)
            # TODO catch exceptions and just print warning instead?
            ctx.translate(margin_dots + cover_usable_width_dots - logo_width2, margin_dots + (0.2 * cover_usable_height_dots - logo_height2)/2)
            ctx.set_source(grp)
            ctx.paint_with_alpha(0.5)
            ctx.restore()

        # Prepare the title
        pc = PangoCairo.create_context(ctx)
        layout = PangoCairo.create_layout(ctx)
        layout.set_width(int(cover_usable_width_dots * Pango.SCALE))
        if not self.rc.i18n.isrtl():
            layout.set_alignment(Pango.Alignment.LEFT)
        else:
            layout.set_alignment(Pango.Alignment.RIGHT)
        fd = Pango.FontDescription(font_face)
        fd.set_size(Pango.SCALE)
        layout.set_font_description(fd)
        layout.set_text(self.rc.title, -1)
        draw_utils.adjust_font_size(layout, fd, cover_usable_width_dots, 0.2 * cover_usable_height_dots)

        # Draw the title
        ctx.save()
        ctx.set_line_width(1)
        ctx.rectangle(0, 0, w_dots, h_dots)
        ctx.stroke()
        ctx.translate((w_dots - layout.get_size()[0] / Pango.SCALE)/2,
                      margin_dots + 0.2 * cover_usable_height_dots)
        PangoCairo.update_layout(ctx, layout)
        PangoCairo.show_layout(ctx, layout)
        ctx.restore()

        # Draw the mini map on the cover
        ctx.save()
        ctx.translate(margin_dots,margin_dots + 0.4 * cover_usable_height_dots)
        self._prepare_cover_map(cover_usable_width_dots, 0.6 * cover_usable_height_dots)
        self._render_cover_map(ctx, cover_usable_width_dots, 0.6 * cover_usable_height_dots)
        ctx.restore()

    def _prepare_cover_map(self, w, h):
        dpi = self.dpi
        self.rc.status_update(_("Preparing cover"))
        cover_map_w = w
        cover_map_h = h

        # Create the nice small map
        cover_map = \
            MapCanvas(self.rc.stylesheet,
                      self.rc.bounding_box,
                      cover_map_w,
                      cover_map_h,
                      dpi,
                      extend_bbox_to_ratio=True)

        # Add the shape that greys out everything that is outside of
        # the administrative boundary.
        exterior = shapely.wkt.loads(cover_map.get_actual_bounding_box().as_wkt())
        interior = shapely.wkt.loads(self.rc.polygon_wkt)
        shade_wkt = exterior.difference(interior).wkt
        shade = maplib.shapes.PolyShapeFile(self.rc.bounding_box,
                os.path.join(self.tmpdir, 'shape_overview_cover.shp'),
                             'shade-overview-cover')
        shade.add_shade_from_wkt(shade_wkt)
        cover_map.add_shape_file(shade)
        self.rc.status_update(_("Preparing front page: base map"))
        cover_map.render()
        self._cover_map = cover_map

        self._frontpage_overlay_canvases = []
        self._frontpage_overlay_effects  = {}
        for overlay in self._overlays:
            path = overlay.path.strip()
            if path.startswith('internal:'):
                plugin_name = path.lstrip('internal:')
                self._frontpage_overlay_effects[plugin_name] = self.get_plugin(plugin_name)
            else:
                ov_canvas = MapCanvas(overlay,
                                      self.rc.bounding_box,
                                      cover_map_w,
                                      cover_map_h,
                                      dpi,
                                      extend_bbox_to_ratio=True)
                self.rc.status_update(_("Preparing front page: %s") % ov_canvas._style_name)
                ov_canvas.render()
                self._frontpage_overlay_canvases.append(ov_canvas)

    def _render_cover_map(self, ctx, w, h):

        # ~ dpi = self.dpi

        # ~ # We will render the map slightly below the title
        # ~ ctx.save()
        # ~ ctx.translate(0, 0.3 * h + Renderer.PRINT_SAFE_MARGIN_PT)

        # prevent map background from filling the full canvas
        ctx.rectangle(0, 0, w, h)
        ctx.clip()

        # Render the map !
        self.rc.status_update(_("Rendering front page: base map"))
        mapnik.render(self._cover_map.get_rendered_map(), ctx)

        for ov_canvas in self._frontpage_overlay_canvases:
            self.rc.status_update(_("Rendering front page: %s") % ov_canvas._style_name)
            rendered_map = ov_canvas.get_rendered_map()
            mapnik.render(rendered_map, ctx)

        # TODO offsets are not correct here, so we skip overlay plugins for now
        # apply effect overlays
        # ctx.save()
        # we have to undo border adjustments here
        # ctx.translate(0, -(0.3 * h + Renderer.PRINT_SAFE_MARGIN_PT))
        # self._map_canvas = self._cover_map;
        # for plugin_name, effect in self._frontpage_overlay_effects.items():
        #    try:
        #        effect.render(self, ctx)
        #    except Exception as e:
        #        # TODO better logging
        #        LOG.warning("Error while rendering overlay: %s\n%s" % (plugin_name, e))
        # ctx.restore()



        # ~ ctx.restore()

    def _render_cover(self, ctx, cairo_surface, dpi, osm_date):
        self.rc.status_update(_("Rendering cover"))
        ctx.save()
        self._prepare_page(ctx)

        # Translate into the working area, taking another
        # PRINT_SAFE_MARGIN_PT inside the grey area.
        ctx.translate(Renderer.PRINT_SAFE_MARGIN_PT,Renderer.PRINT_SAFE_MARGIN_PT)
        w = self._usable_area_width_pt - 2 * Renderer.PRINT_SAFE_MARGIN_PT
        h = self._usable_area_height_pt - 2 * Renderer.PRINT_SAFE_MARGIN_PT

        self._render_cover_map(ctx, dpi, w, h)
        # ~ self._render_cover_header(ctx, w, h)
        # ~ self._render_cover_footer(ctx, w, h, osm_date)

        # ~ try: # set_page_label() does not exist in older pycairo versions
            # ~ cairo_surface.set_page_label(_(u'Cover'))
        # ~ except:
            # ~ pass

        ctx.restore()
        cairo_surface.show_page()

    def _create_index_rendering(self, index_position):
        """Prepare to render the index.

        Parameters
        ----------
           index_position : str, optional
               None, "side", "bottom" or "extra_page"

        Returns
        -------
        List of (IndexRenderer, IndexRenderingArea).
            The actual index renderer and the area it will cover.
        """

        index_area = None

        # Now we determine the actual occupation of the index
        # TODO: index type choice should not be hard coded here
        if self.rc.indexer == 'Poi':
            # a special index is createad when a POI file is attached
            index_renderer = PoiIndexRenderer(self.rc.i18n,
                                                 self.street_index.categories)
        else:
            # TODO: use actual renderer type here?
            index_renderer = GeneralIndexRenderer(self.rc.i18n,
                                                 self.street_index.categories)

        # We use a fake vector device to determine the actual
        # rendering characteristics
        fake_surface = cairo.PDFSurface(None,
                                        self.paper_width_pt,
                                        self.paper_height_pt)

        # calculate the area required for the index, depending on its position
        try:
            if index_position == 'side':
                index_max_width_pt = self._cover_width_pt
                # RTL: Index is on the left
                tmp_y =  Renderer.PRINT_SAFE_MARGIN_PT + self._cover_height_pt
                index_area = index_renderer.precompute_occupation_area(
                    fake_surface,
                    Renderer.PRINT_SAFE_MARGIN_PT,
                    tmp_y,
                    index_max_width_pt,
                    self._usable_area_height_pt - self._cover_height_pt,
                    'width', 'left')
            elif index_position == 'bottom':
                # Index at the bottom of the page
                index_max_height_pt \
                    = self.MAX_INDEX_OCCUPATION_RATIO * self._usable_area_height_pt

                index_area = index_renderer.precompute_occupation_area(
                    fake_surface,
                    Renderer.PRINT_SAFE_MARGIN_PT,
                    ( self.paper_height_pt
                      - Renderer.PRINT_SAFE_MARGIN_PT
                      - self._copyright_margin_pt
                      - index_max_height_pt ),
                    self._cover_width_pt + self._usable_area_width_pt,
                    index_max_height_pt,
                    'height', 'bottom')
        except IndexDoesNotFitError:
            index_area = None

        return index_renderer, index_area

    @staticmethod
    def get_compatible_paper_sizes(bounding_box, render_context,
                                   scale=Renderer.DEFAULT_SCALE):
        """Returns a list of the compatible paper sizes for the given bounding
        box. The list is sorted, smaller papers first, and a "custom" paper
        matching the dimensions of the bounding box is added at the end.

        Args:
            bounding_box (coords.BoundingBox): the map geographic bounding box.
            paper_sizes (list): the complete list of configured paper sizes
            scale (int): minimum mapnik scale of the map.

        Returns a list of tuples (paper name, width in mm, height in
        mm, portrait_ok, landscape_ok). Paper sizes are represented in
        portrait mode.
        """
        # ~ return SinglePageRenderer._generic_get_compatible_paper_sizes(
            # ~ bounding_box, render_context.get_all_paper_sizes(), scale, 'side')

        paper_width_mm, paper_height_mm = SinglePageRendererIndexFoldable.get_minimal_paper_size(bounding_box, scale)
        LOG.info('Best fit including decorations is %.0fx%.0fmm.' % (paper_width_mm, paper_height_mm))

        paper_sizes = render_context.get_all_paper_sizes()

        valid_sizes = []

        # Add a 'Custom' paper format to the list that perfectly matches the
        # bounding box.
        best_fit_is_portrait = paper_width_mm < paper_height_mm
        valid_sizes.append({
            "name": 'Best fit',
            "width": paper_width_mm,
            "height": paper_height_mm,
            "portrait_ok": best_fit_is_portrait,
            "portrait_scale": scale if best_fit_is_portrait else None,
            "portrait_zoom": Renderer.scaleDenominator2zoom(scale) if best_fit_is_portrait else None,
            "landscape_ok": not best_fit_is_portrait,
            "landscape_scale": scale if not best_fit_is_portrait else None,
            "landscape_zoom": Renderer.scaleDenominator2zoom(scale) if not best_fit_is_portrait else None,
        })

        # Test both portrait and landscape orientations when checking for paper
        # sizes.
        for name, w, h in paper_sizes:
            if w is None:
                continue

            portrait_ok  = paper_width_mm <= w and paper_height_mm <= h
            landscape_ok = paper_width_mm <= h and paper_height_mm <= w

            if portrait_ok:
                portrait_scale = scale / min(w / paper_width_mm, h / paper_height_mm)
                portrait_zoom = Renderer.scaleDenominator2zoom(portrait_scale)
            else:
                portrait_scale = None
                portrait_zoom = None

            if landscape_ok:
                landscape_scale = scale / min(h / paper_width_mm, w / paper_height_mm)
                landscape_zoom = Renderer.scaleDenominator2zoom(landscape_scale)
            else:
                landscape_scale = None
                landscape_zoom = None

            if portrait_ok or landscape_ok:
                valid_sizes.append({
                    "name": name,
                    "width": w,
                    "height": h,
                    "portrait_ok": portrait_ok,
                    "portrait_scale": portrait_scale,
                    "portrait_zoom": portrait_zoom,
                    "landscape_ok": landscape_ok,
                    "landscape_scale": landscape_scale,
                    "landscape_zoom": landscape_zoom,
                })

        return valid_sizes

    @staticmethod
    def get_minimal_paper_size(bounding_box, scale=Renderer.DEFAULT_SCALE):
        """

        Parameters
        ----------
        bounding_box : coords.BoundingBox
        scale : float, optional

        Returns
        -------
        list of int
            Minimal necessary width and height
        """
        # ~ return SinglePageRenderer._generic_get_minimal_paper_size(
            # ~ bounding_box, scale, 'side')

        # the mapnik scale depends on the latitude
        lat = bounding_box.get_top_left()[0]
        scale *= math.cos(math.radians(lat))

        # by convention, mapnik uses 90 ppi whereas cairo uses 72 ppi
        scale *= float(72) / 90

        geo_height_m, geo_width_m = bounding_box.spheric_sizes()
        canvas_width_mm = geo_width_m * 1000 / scale
        canvas_height_mm = geo_height_m * 1000 / scale

        LOG.info('Map represents %dx%dm, needs at least %.0fx%.fmm '
                 'on paper at scale %f.' % (geo_width_m, geo_height_m,
                                            canvas_width_mm, canvas_height_mm, scale))

        paper_width_mm  = canvas_width_mm
        paper_height_mm = canvas_height_mm

        # Take cover and index into account
        paper_width_mm /= (1. -
                           SinglePageRenderer.COVER_OCCUPATION_RATIO)
        # Take margins into account
        paper_width_mm += 2 * commons.convert_pt_to_mm(Renderer.PRINT_SAFE_MARGIN_PT)
        paper_height_mm += 2 * commons.convert_pt_to_mm(Renderer.PRINT_SAFE_MARGIN_PT)

        # Take grid legend, title and copyright into account
        paper_width_mm /= 1 - Renderer.GRID_LEGEND_MARGIN_RATIO
        paper_height_mm /= 1 - (Renderer.GRID_LEGEND_MARGIN_RATIO
                                + Renderer.ANNOTATION_MARGIN_RATIO)

        # enforce minimal paper size
        if paper_width_mm < Renderer.MIN_PAPER_WIDTH:
            paper_height_mm = paper_height_mm * Renderer.MIN_PAPER_WIDTH / paper_width_mm
            paper_width_mm = Renderer.MIN_PAPER_WIDTH
        if paper_height_mm < Renderer.MIN_PAPER_HEIGHT:
            paper_width_mm = paper_width_mm * Renderer.MIN_PAPER_HEIGHT / paper_height_mm
            paper_height_mm = Renderer.MIN_PAPER_HEIGHT

        # Transform the values into integers
        paper_width_mm  = int(math.ceil(paper_width_mm))
        paper_height_mm = int(math.ceil(paper_height_mm))

        return (paper_width_mm, paper_height_mm)
