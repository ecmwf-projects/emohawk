# (C) Copyright 2020 ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.
#
import collections.abc
import itertools

import cdsapi
import yaml

from earthkit.data.core.thread import SoftThreadPool
from earthkit.data.decorators import normalize
from earthkit.data.utils import tqdm

from .file import FileSource
from .prompt import APIKeyPrompt


def ensure_iterable(obj):
    if isinstance(obj, str) or not isinstance(obj, collections.abc.Iterable):
        return [obj]
    return obj


class CDSAPIKeyPrompt(APIKeyPrompt):
    register_or_sign_in_url = "https://cds.climate.copernicus.eu/"
    retrieve_api_key_url = "https://cds.climate.copernicus.eu/api-how-to"

    prompts = [
        dict(
            name="url",
            default="https://cds.climate.copernicus.eu/api/v2",
            title="API url",
            validate=r"http.?://.*",
        ),
        dict(
            name="key",
            example="123:abcdef01-0000-1111-2222-0123456789ab",
            title="API key",
            hidden=True,
            validate=r"\d+:[\-0-9a-f]+",
        ),
    ]

    rcfile = "~/.cdsapirc"

    def save(self, input, file):
        yaml.dump(input, file, default_flow_style=False)


def client():
    prompt = CDSAPIKeyPrompt()
    prompt.check()

    try:
        return cdsapi.Client()
    except Exception as e:
        if ".cdsapirc" in str(e):
            prompt.ask_user_and_save()
            return cdsapi.Client()

        raise


EXTENSIONS = {
    "grib": ".grib",
    "netcdf": ".nc",
}


class CdsRetriever(FileSource):
    sphinxdoc = """
    CdsRetriever
    """

    def client(self):
        return client()

    def __init__(self, dataset, *args, **kwargs):
        super().__init__()

        assert isinstance(dataset, str)
        if len(args):
            assert len(args) == 1
            assert isinstance(args[0], dict)
            assert not kwargs
            kwargs = args[0]

        requests = self.requests(**kwargs)

        self.client()  # Trigger password prompt before thraeding

        nthreads = min(self.settings("number-of-download-threads"), len(requests))

        if nthreads < 2:
            self.path = [self._retrieve(dataset, r) for r in requests]
        else:
            with SoftThreadPool(nthreads=nthreads) as pool:
                futures = [pool.submit(self._retrieve, dataset, r) for r in requests]

                iterator = (f.result() for f in futures)
                self.path = list(tqdm(iterator, leave=True, total=len(requests)))

    def _retrieve(self, dataset, request):
        def retrieve(target, args):
            self.client().retrieve(args[0], args[1], target)

        return self.cache_file(
            retrieve,
            (dataset, self._normalize_request(**request)),
            extension=EXTENSIONS.get(request.get("format"), ".cache"),
        )

    @normalize("date", "date-list(%Y-%m-%d)")
    @normalize("area", "bounding-box(list)")
    def requests(self, **kwargs):
        split_on = kwargs.pop("split_on", None)
        if split_on is None:
            return [kwargs]
        split_on = ensure_iterable(split_on)

        result = []
        for values in itertools.product(
            *[sorted(ensure_iterable(kwargs[k])) for k in split_on]
        ):
            subrequest = dict(zip(split_on, values))
            result.append(kwargs | subrequest)
        return result or [kwargs]

    @staticmethod
    def _normalize_request(**request):
        result = {}
        for k, v in sorted(request.items()):
            v = ensure_iterable(v)
            if k not in ("area", "grid"):
                v = sorted(v)
            result[k] = v[0] if len(v) == 1 else v
        return result


source = CdsRetriever
