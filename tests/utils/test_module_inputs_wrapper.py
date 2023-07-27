# (C) Copyright 2020 ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.
#

import numpy as np
import pandas as pd
import xarray as xr

from earthkit.data import from_object, from_source
from earthkit.data.readers import Reader
from earthkit.data.utils import module_inputs_wrapper

from . import dummy_module
from .dummy_module import XR_TYPES

TEST_NP = np.arange(10)
TEST_NP2 = np.arange(10)

TEST_DF = pd.DataFrame({"index": TEST_NP, "data": TEST_NP2}).set_index("index")

TEST_DA = xr.DataArray(TEST_NP, name="test")
TEST_DA2 = xr.DataArray(TEST_NP2, name="test2")
TEST_DS = TEST_DA.to_dataset()
TEST_DS["test2"] = TEST_DA2

EK_GRIB_READER = from_source("file", "tests/data/test_single.grib")
EK_XARRAY_WRAPPER = from_object(TEST_DS)
EK_NUMPY_WRAPPER = from_object(TEST_NP)

WRAPPED_XR_ONES_LIKE = module_inputs_wrapper.transform_function_inputs(
    xr.ones_like, kwarg_types={"other": XR_TYPES}
)

WRAPPED_NP_MEAN = module_inputs_wrapper.transform_function_inputs(
    np.mean,
    kwarg_types={"a": np.ndarray},
    convert_types=(
        Reader
    ),  # Only convert Earthkit.data.Reader (np.mean can handle xarray and pandas)
)

WRAPPED_DUMMY_MODULE = module_inputs_wrapper.transform_module_inputs(
    dummy_module, kwarg_types={"dataarray": XR_TYPES}
)


def test_transform_function_inputs_reader_to_xarray():
    # Check EK GribReader object
    ek_reader_result = WRAPPED_XR_ONES_LIKE(EK_GRIB_READER)
    assert isinstance(ek_reader_result, XR_TYPES)
    assert ek_reader_result.equals(xr.ones_like(EK_GRIB_READER.to_xarray()))


def test_transform_module_inputs_reader_to_xarray():
    # Check EK GribReader object
    ek_reader_result = WRAPPED_DUMMY_MODULE.xarray_ones_like(EK_GRIB_READER)
    assert isinstance(ek_reader_result, XR_TYPES)
    assert ek_reader_result.equals(xr.ones_like(EK_GRIB_READER.to_xarray()))


def test_transform_function_inputs_wrapper_to_xarray():
    # EK XarrayWrapper object
    ek_wrapper_result = WRAPPED_XR_ONES_LIKE(EK_XARRAY_WRAPPER)
    assert isinstance(ek_wrapper_result, XR_TYPES)
    assert ek_wrapper_result.equals(xr.ones_like(EK_XARRAY_WRAPPER.data))
    # EK NumpyWrapper object
    ek_wrapper_result = WRAPPED_XR_ONES_LIKE(EK_NUMPY_WRAPPER)
    assert isinstance(ek_wrapper_result, XR_TYPES)
    assert ek_wrapper_result.equals(xr.ones_like(TEST_DA))


def test_transform_function_inputs_reader_to_numpy():
    # Test with Earthkit.data GribReader object
    assert WRAPPED_NP_MEAN(EK_GRIB_READER) == np.mean(EK_GRIB_READER.to_numpy())
    assert isinstance(WRAPPED_NP_MEAN(EK_GRIB_READER), np.float64)


def test_transform_function_inputs_wrapper_to_numpy():
    # Test with Earthkit.data XarrayWrapper object
    ek_object_result = WRAPPED_NP_MEAN(EK_XARRAY_WRAPPER)
    assert ek_object_result == np.mean(TEST_DS)
    assert isinstance(ek_object_result, type(EK_XARRAY_WRAPPER.data))

    # Test with Earthkit.data NumpyWrapper object
    ek_object_result = WRAPPED_NP_MEAN(EK_NUMPY_WRAPPER)
    assert ek_object_result == np.mean(TEST_NP)
    assert isinstance(ek_object_result, np.float64)


def test_transform_function_inputs_xarray_to_numpy():
    # Test with xarray.DataArray object
    assert WRAPPED_NP_MEAN(TEST_DA) == np.mean(TEST_NP)
    assert WRAPPED_NP_MEAN(TEST_DA) == np.mean(TEST_DA)
    assert isinstance(WRAPPED_NP_MEAN(TEST_DA), xr.DataArray)


def test_transform_function_inputs_pandas_to_numpy():
    # Test with pandas.DataFrame object
    result = WRAPPED_NP_MEAN(TEST_DF)
    assert result.equals(np.mean(TEST_DF))
    assert isinstance(result, pd.core.series.Series)
