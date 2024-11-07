# -*- coding: utf-8 -*-

# ocitysmap, city map and street index generator from OpenStreetMap data
# Copyright (C) 2010  David Decotigny
# Copyright (C) 2010  Frédéric Lehobey
# Copyright (C) 2010  Pierre Mauduit
# Copyright (C) 2010  David Mentré
# Copyright (C) 2010  Maxime Petazzoni
# Copyright (C) 2010  Thomas Petazzoni
# Copyright (C) 2010  Gaël Utard

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

import logging
import math

from . import shapes

LOG = logging.getLogger('ocitysmap')

class FixedGrid:
    """
    The FixedGrid class defines a grid overlayed on a rendered map. It creates
    the grid based on the number of rows and cols in it,
    generating the size of squares, etc.
    """

    def __init__(self, bounding_box, scale, rows=4, cols=3, rtl=False):
        """Creates a new grid for the given bounding box with the given
        numbers of columns and rows.

        Args:
            bounding_box (coords.BoundingBox): the map bounding box.
            rows (integer): the number of rows of the grid
            cols (integer): the number of columns of the grid
            rtl (boolean): whether the map is rendered in right-to-left mode or
                not. Defaults to False.
        """

        self._bbox = bounding_box
        self.rtl   = rtl
        self.scale = scale
        self.rows = rows
        self.cols = cols
        self._height_m, self._width_m = bounding_box.spheric_sizes()

        LOG.info('Laying out grid on %.1fx%.1fm area...' %
               (self._width_m, self._height_m))

        self.horiz_count = self.cols
        self.vert_count = self.rows
        self.grid_width_m = self._width_m / self.horiz_count
        self.grid_height_m = self._height_m / self.vert_count

        self._horiz_angle_span = abs(self._bbox.get_top_left()[1] -
                                     self._bbox.get_bottom_right()[1])
        self._vert_angle_span  = abs(self._bbox.get_top_left()[0] -
                                     self._bbox.get_bottom_right()[0])

        self._horiz_unit_angle = (self._horiz_angle_span / self.horiz_count)
        self._vert_unit_angle  = (self._vert_angle_span / self.vert_count)

        self._horizontal_lines = [ ( self._bbox.get_top_left()[0] -
                                     (x+1) * self._vert_unit_angle)
                                   for x in range(int(math.floor(self.vert_count))-1)]
        if rtl:
            self._vertical_lines   = [ (self._bbox.get_bottom_right()[1] -
                                        (x+1) * self._horiz_unit_angle)
                                       for x in range(int(math.floor(self.horiz_count))-1)]
        else:
            self._vertical_lines   = [ (self._bbox.get_top_left()[1] +
                                        (x+1) * self._horiz_unit_angle)
                                       for x in range(int(math.floor(self.horiz_count))-1)]

        self.horizontal_labels = list(map(self._gen_horizontal_square_label,
                                      range(int(math.ceil(self.horiz_count)))))
        self.vertical_labels = list(map(self._gen_vertical_square_label,
                                   range(int(math.ceil(self.vert_count)))))

        LOG.info('Using %dx%dm grid (%.2fx%.2f squares).' %
               (self.grid_width_m, self.grid_height_m,
                self.horiz_count, self.vert_count))

    def generate_shape_file(self, filename):
        """Generates the grid shapefile with all the horizontal and
        vertical lines added.

        Args:
            filename (string): path to the temporary shape file that will be
                generated.
        Returns the ShapeFile object.
        """

        # Use a slightly larger bounding box for the shape file to accomodate
        # for the small imprecisions of re-projecting and the extra gray margin
        # area in multi page maps
        LOG.debug("Generating shapefile")
        g = shapes.LineShapeFile(self._bbox.create_expanded(self.scale/6000000, self.scale/6000000),
                                 filename, 'grid')
        for x in self._vertical_lines:
            g.add_vert_line(x)
        for y in self._horizontal_lines:
            g.add_horiz_line(y)
        return g

    def _gen_horizontal_square_label(self, x):
        """Generate a human-readable label for the given horizontal square
        number. """

        label = '%d' % (x + 1)
        return label

    def _gen_vertical_square_label(self, y):
        """Generate a human-readable label for the given vertical square
        number. """
        
        label = '%d' % (y * self.cols)
        return label

    def get_location_str(self, latitude, longitude):
        """
        Translate the given latitude/longitude (EPSG:4326) into the
        number of the grid square, counting left to right,
        top to bottom, in a zigzag-manner
        """
        if self.rtl:
            hdelta = min(abs(self._bbox.get_bottom_right()[1]-longitude),
                         self._horiz_angle_span)
        else:
            hdelta = min(abs(longitude - self._bbox.get_top_left()[1]),
                         self._horiz_angle_span)

        hno = int(hdelta / self._horiz_unit_angle)

        vdelta = min(abs(latitude - self._bbox.get_top_left()[0]),
                     self._vert_angle_span)
        vno = int(vdelta / self._vert_unit_angle)

        return "%d" % (1 + hno + vno * self.cols)


if __name__ == "__main__":
    import ocitysmap

    logging.basicConfig(level=logging.DEBUG)
    grid = Grid(ocitysmap.coords.BoundingBox(44.4883, -1.0901, 44.4778, -1.0637))
    shape = grid.generate_shape_file('/tmp/mygrid.shp')
