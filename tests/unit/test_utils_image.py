from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from caipture.utils import image_dimensions
from tests.test_utils import make_png


class ImageDimensionTests(unittest.TestCase):
    def test_png_dimensions_detected(self) -> None:
        with tempfile.TemporaryDirectory() as td:
            p = Path(td) / "sample.png"
            make_png(p, 123, 456)
            self.assertEqual(image_dimensions(p), (123, 456))

    def test_jpeg_dimensions_detected(self) -> None:
        fixture = Path(__file__).resolve().parents[1] / "fixtures" / "front.png"
        dims = image_dimensions(fixture)
        self.assertEqual(dims, (360, 480))
