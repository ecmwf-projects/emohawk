#!/usr/bin/env python3

# (C) Copyright 2024 ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.
#

import pytest

from earthkit.data import from_source
from earthkit.data.readers.geotiff import GeoTIFFField
from earthkit.data.testing import earthkit_test_data_file
from earthkit.data.utils.projections import TransverseMercator


@pytest.mark.with_proj
def test_geotiff_reader_with_multiband():
    s = from_source("file", earthkit_test_data_file("dgm50hs_col_32_368_5616_nw.tif"))
    assert len(s) == 3
    assert isinstance(s[0], GeoTIFFField)
    assert isinstance(s[1], GeoTIFFField)
    assert s[0].metadata("band") == 1
    assert s[1].metadata("band") == 2
    assert s[2].metadata("band") == 3
    assert isinstance(s.projection(), TransverseMercator)
    assert s[0].shape == (294, 315)


if __name__ == "__main__":
    from earthkit.data.testing import main

    main(__file__)
