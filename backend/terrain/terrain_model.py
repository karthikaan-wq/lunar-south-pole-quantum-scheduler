
import numpy as np

from .projection import xy_to_lonlat


class Terrain:
    """
    A square or rectangular terrain raster.

    Coordinate convention:
        x increases from left to right.
        y decreases from top to bottom.
        x0, y0 identify the map coordinates of pixel [0, 0].
    """

    def __init__(
        self,
        heights: np.ndarray,
        x0: float,
        y0: float,
        pixel_m: float,
    ):
        heights = np.asarray(heights, dtype=np.float32)

        if heights.ndim != 2:
            raise ValueError("Terrain heights must be a 2D array.")

        if heights.shape[0] < 2 or heights.shape[1] < 2:
            raise ValueError("Terrain must contain at least 2 rows and 2 columns.")

        if not np.isfinite(pixel_m) or pixel_m <= 0:
            raise ValueError("Pixel size must be a positive finite number.")

        if not np.isfinite(x0) or not np.isfinite(y0):
            raise ValueError("Terrain origin coordinates must be finite.")

        self.heights = heights
        self.x0 = float(x0)
        self.y0 = float(y0)
        self.pixel_m = float(pixel_m)

    def height_at(self, x: float, y: float) -> float:
        """
        Return terrain elevation at map coordinates (x, y).

        Bilinear interpolation is used between four neighbouring
        pixels. Returns NaN outside the raster or when any of the
        four required pixels contains missing data.
        """
        x = float(x)
        y = float(y)

        if not np.isfinite(x) or not np.isfinite(y):
            return float("nan")

        # Convert map coordinates to fractional raster coordinates.
        col = (x - self.x0) / self.pixel_m
        row = (self.y0 - y) / self.pixel_m

        rows, cols = self.heights.shape

        # Reject coordinates outside the raster.
        if col < 0 or row < 0:
            return float("nan")

        if col > cols - 1 or row > rows - 1:
            return float("nan")

        # Select the surrounding four pixels.
        c0 = min(int(np.floor(col)), cols - 2)
        r0 = min(int(np.floor(row)), rows - 2)

        c1 = c0 + 1
        r1 = r0 + 1

        # Fractional position inside the pixel square.
        dx = col - c0
        dy = row - r0

        h00 = float(self.heights[r0, c0])
        h10 = float(self.heights[r0, c1])
        h01 = float(self.heights[r1, c0])
        h11 = float(self.heights[r1, c1])

        values = np.array([h00, h10, h01, h11])

        if not np.all(np.isfinite(values)):
            return float("nan")

        # Bilinear interpolation.
        top = h00 * (1.0 - dx) + h10 * dx
        bottom = h01 * (1.0 - dx) + h11 * dx

        height = top * (1.0 - dy) + bottom * dy

        return float(height)


def make_synthetic_terrain(
    height_function,
    half_size_m: float,
    pixel_m: float,
) -> Terrain:
    """
    Create a synthetic square terrain raster for testing.

    height_function receives:
        latitude_deg array
        longitude_deg array

    It must return an elevation array in metres with the same shape.

    The generated map is centred on the lunar south pole.
    """

    if not np.isfinite(half_size_m) or half_size_m <= 0:
        raise ValueError("Map half-size must be positive and finite.")

    if not np.isfinite(pixel_m) or pixel_m <= 0:
        raise ValueError("Pixel size must be positive and finite.")

    coordinates = np.arange(
        -half_size_m,
        half_size_m + pixel_m * 0.5,
        pixel_m,
        dtype=np.float64,
    )

    x_values = coordinates
    y_values = coordinates[::-1]

    xx, yy = np.meshgrid(x_values, y_values)

    latitudes = np.empty_like(xx)
    longitudes = np.empty_like(yy)

    for row in range(xx.shape[0]):
        for col in range(xx.shape[1]):
            latitudes[row, col], longitudes[row, col] = (
                xy_to_lonlat(xx[row, col], yy[row, col])
            )

    heights = np.asarray(
        height_function(latitudes, longitudes),
        dtype=np.float32,
    )

    if heights.shape != xx.shape:
        raise ValueError(
            "Height function must return an array matching the terrain grid."
        )

    return Terrain(
        heights=heights,
        x0=float(x_values[0]),
        y0=float(y_values[0]),
        pixel_m=float(pixel_m),
    )
