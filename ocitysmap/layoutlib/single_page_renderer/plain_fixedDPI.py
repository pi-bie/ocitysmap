from gettext import gettext

import logging
LOG = logging.getLogger('ocitysmap')

import cairo
import mapnik
assert mapnik.mapnik_version() >= 300000, \
    "Mapnik module version %s is too old, see ocitysmap's INSTALL " \
    "for more details." % mapnik.mapnik_version_string()
import math
from copy import copy

from ocitysmap.layoutlib import commons
import ocitysmap
from ocitysmap.layoutlib.abstract_renderer import Renderer
from ocitysmap.layoutlib.single_page_renderers import SinglePageRenderer

class SinglePageRendererPlainFixedDPI(SinglePageRenderer):
    """
    Render single page map without index
    """
    name = 'fixedDPI'
    description = gettext(u'Full-page layout of fixed DPI')

    def __init__(self, db, rc, tmpdir, dpi, map_dpi, file_prefix):
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
           map_dpi : int
               Render resolution for the map itself
           file_prefix : str
               File name refix for all output file formats to be generated
        """
        
        Renderer.__init__(self, db, rc, tmpdir, dpi, map_dpi)

        self.file_prefix = file_prefix

        rc.indexer = None
        self.street_index = None
        self.index_position = None
        
        self._index_renderer, self._index_area = None, None
        
        # calculate remaining usable render space for the actual map
        # after taking header and footer into account
        self._usable_area_width_pt = (self.paper_width_pt -
                                      2 * Renderer.PRINT_SAFE_MARGIN_PT)
        self._usable_area_height_pt = (self.paper_height_pt -
                                       2 * Renderer.PRINT_SAFE_MARGIN_PT)
                                       
        self._map_coords = self._get_map_coords(index_position if self._index_area else None)
        
        # Prepare the map
        self._map_canvas = self._create_map_canvas(
            float(self._map_coords[2]),  # W
            float(self._map_coords[3]),  # H
            dpi,
            rc.osmid is not None )

        # Prepare overlay styles from config
        self._overlays = copy(self.rc.overlays)
        self._overlay_effects  = {}

        # Prepare overlays for all additional import files
        # we cycle through a predefined color list for gpx track colors
        gpx_colors = ['red', 'blue', 'green', 'violet', 'orange']
        gpx_color_index = 0
        if self.rc.import_files:
            for (file_type, import_file) in self.rc.import_files:
                if file_type == 'gpx':
                    try:
                        color = gpx_colors[gpx_color_index]
                        gpx_color_index += 1
                        if gpx_color_index == len(gpx_colors):
                            gpx_color_index = 0
                        gpx_style = GpxStylesheet(import_file, self.tmpdir, color)
                    except Exception as e:
                        LOG.warning("GPX stylesheet error: %s" % e)
                    else:
                        self._overlays.append(gpx_style)
                elif file_type == 'umap':
                    try:
                        umap_style = UmapStylesheet(import_file, self.tmpdir)
                    except Exception as e:
                        LOG.warning("UMAP stylesheet error: %s" % e)
                    else:
                        self._overlays.append(umap_style)
                elif file_type == 'poi':
                    # TODO: refactor this special case
                    self._overlay_effects['poi_markers'] = self.get_plugin('poi_markers')
                    self.rc.poi_file = import_file
                else:
                    LOG.warning("Unsupported file type '%s' for file '%s" % (file_type, import_file))

        # Prepare map overlays
        self._overlay_canvases = []
        for overlay in self._overlays:
            path = overlay.path.strip()
            if path.startswith('internal:'):
                # overlay plugin implemented using Python code
                plugin_name = path.lstrip('internal:')
                self._overlay_effects[plugin_name] = self.get_plugin(plugin_name)
            else:
                # Mapnix style overlay
                self._overlay_canvases.append(MapCanvas(overlay,
                                              self.rc.bounding_box,
                                              float(self._map_coords[2]),  # W
                                              float(self._map_coords[3]),  # H
                                              dpi))

        # Commit the internal rendering stack of the map
        self._map_canvas.render()
        for overlay_canvas in self._overlay_canvases:
           overlay_canvas.render()

    def render(self, cairo_surface, dpi, map_dpi, osm_date):
        """ Render the complete map page, including all components

        Renders the map, the index and all other visual map features on the
        given Cairo surface.

        Parameters
        ----------
        cairo_surface : cairo.Surface
            Cairo destination device surface to render into
        dpi : int
            Dots per inch to use with this surface
        map_dpi : int
            Dots per inch to use for map rendering
        osm_date : datetime
            Timestamp of last OSM database update

        Returns
        -------
        void
        """
        LOG.info('SinglePageRendererPlainFixedScale rendering -%s- on %dx%dmm paper at %d dpi.' %
                 (self.rc.output_format, self.rc.paper_width_mm, self.rc.paper_height_mm, dpi))

        # First determine some useful drawing parameters
        safe_margin_dots \
            = commons.convert_pt_to_dots(Renderer.PRINT_SAFE_MARGIN_PT, dpi)

        usable_area_width_dots \
            = commons.convert_pt_to_dots(self._usable_area_width_pt, dpi)

        usable_area_height_dots \
            = commons.convert_pt_to_dots(self._usable_area_height_pt, dpi)

        map_coords_dots = list(map(lambda l: commons.convert_pt_to_dots(l, dpi),
                              self._map_coords))

        # create the cairo context to draw into
        ctx = cairo.Context(cairo_surface)

        # Set a white background (so that generated bitmaps are not transparent)
        ctx.save()
        ctx.set_source_rgb(1, 1, 1)
        ctx.rectangle(0, 0,
                      commons.convert_pt_to_dots(self.paper_width_pt, dpi),
                      commons.convert_pt_to_dots(self.paper_height_pt, dpi))
        ctx.fill()
        ctx.restore()

        ##
        ## Draw the map, scaled to fit the designated area
        ##
        ctx.save()

        # prevent map background from filling the full canvas
        ctx.rectangle(map_coords_dots[0], map_coords_dots[1], map_coords_dots[2], map_coords_dots[3])
        ctx.clip()

        # Prepare to draw the map at the right location
        ctx.translate(map_coords_dots[0], map_coords_dots[1])

        # Draw the rescaled Map
        ctx.save()
        scale_factor = float(dpi) / map_dpi
        rendered_map = self._map_canvas.get_rendered_map()
        LOG.info('Map:')
        LOG.info('Mapnik scale: 1/%f' % rendered_map.scale_denominator())
        LOG.info('Actual scale: 1/%f' % self._map_canvas.get_actual_scale())
        LOG.info('Zoom factor: %d' % self.scaleDenominator2zoom(rendered_map.scale_denominator()))

        # now perform the actual map drawing
        self.rc.status_update(_("%s: rendering base map") % self.rc.output_format)
        mapnik.render(rendered_map, ctx, scale_factor, 0, 0)
        ctx.restore()

        # Draw the rescaled Overlays on top of the map one by one
        for overlay_canvas in self._overlay_canvases:
            ctx.save()
            rendered_overlay = overlay_canvas.get_rendered_map()
            LOG.info('Overlay: %s' % overlay_canvas.get_style_name())
            self.rc.status_update(_("%(format)s: rendering '%(style)s' overlay")
                                  % { 'format': self.rc.output_format,
                                      'style': overlay_canvas.get_style_name(),
                                     })
            mapnik.render(rendered_overlay, ctx, scale_factor, 0, 0)
            ctx.restore()

        ctx.restore()

        # Draw a rectangle frame around the map
        ctx.save()
        ctx.set_line_width(1)
        ctx.rectangle(map_coords_dots[0], map_coords_dots[1], map_coords_dots[2], map_coords_dots[3])
        ctx.stroke()
        ctx.restore()

        # make sure that plugins do not render outside the actual map area
        ctx.save()
        ctx.translate(map_coords_dots[0], map_coords_dots[1])
        ctx.rectangle(0, 0, map_coords_dots[2], map_coords_dots[3])
        ctx.clip()

        # apply effect plugin overlays
        for plugin_name, effect in self._overlay_effects.items():
            self.rc.status_update(_("%(format)s: rendering '%(style)s' overlay")
                                  % { 'format': self.rc.output_format,
                                      'style':  plugin_name,
                                     })
            try:
                effect.render(self, ctx)
            except Exception as e:
                # TODO better logging
                LOG.warning("Error while rendering overlay: %s\n%s" % (plugin_name, e))
        ctx.restore()

    @staticmethod
    def get_compatible_paper_sizes(bounding_box, render_context,dpi=300,
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
       
        paper_width_mm, paper_height_mm = SinglePageRendererPlainFixedDPI.get_minimal_paper_size(bounding_box, scale, dpi)
        LOG.info('Best fit is %.0fx%.0fmm.' % (paper_width_mm, paper_height_mm))
        
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
        
        paper_sizes = []
        
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
    def get_minimal_paper_size(bounding_box, scale=Renderer.DEFAULT_SCALE, dpi=300):
    
        """

        Parameters
        ----------
        bounding_box : coords.BoundingBox
        scale : float, optional
        dpi : float, optional
        index_position : str, optional

        Returns
        -------
        list of int
            Minimal necessary widht and height
        """

        # the mapnik scale depends on the latitude
        lat = bounding_box.get_top_left()[0]
        scale *= math.cos(math.radians(lat))

        # by convention, mapnik uses 90 ppi whereas cairo uses 72 ppi
        scale *= float(dpi) / 90

        geo_height_m, geo_width_m = bounding_box.spheric_sizes()
        canvas_width_mm = geo_width_m / 25.0
        canvas_height_mm = geo_height_m / 25.0

        LOG.info('Map represents %dx%dm, needs at least %.0fx%.fmm '
                 'to achieve desired fixed scale' % (geo_width_m, geo_height_m,
                                            canvas_width_mm, canvas_height_mm))

        paper_width_mm  = canvas_width_mm
        paper_height_mm = canvas_height_mm

        # Take margins into account
        paper_width_mm += 2 * commons.convert_pt_to_mm(Renderer.PRINT_SAFE_MARGIN_PT)
        paper_height_mm += 2 * commons.convert_pt_to_mm(Renderer.PRINT_SAFE_MARGIN_PT)

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
