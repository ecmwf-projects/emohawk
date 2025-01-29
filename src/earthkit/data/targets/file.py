# (C) Copyright 2020 ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.
#

import logging
import os
import re
from io import IOBase

from . import SimpleTarget

LOG = logging.getLogger(__name__)


class FileTarget(SimpleTarget):
    """
    File target.

    Parameters:
    -----------
    file: str or file-like object
        The file path or file-like object to write to. When None, tries to guess the file name
        from the ``data`` if it is passed as a kwarg.
        When the file name cannot be constructed, a ValueError is raised.
    split_output: bool
        If True, the output file name defines a pattern containing metadata keys in the
        format of ``{key}``. Each data item (e.g. a field) will be written into a file
        with a name created by substituting the relevant metadata values in the
        filename pattern. Only used if file is a path.
    append: bool
        If True, the file is opened in append mode. Only used if file is a path.
    **kwargs:
        Additional keyword arguments passed to the parent class

    Raises:
    -------
    ValueError: If the file name is not specified and cannot be constructed.
    """

    def __init__(self, file=None, *, split_output=False, append=False, **kwargs):
        super().__init__(**kwargs)

        self._files = {}
        self.fileobj = None
        self.filename = None
        self.append = append
        self.ext = None

        if isinstance(file, IOBase):
            self.fileobj = file
            split_output = False
        else:
            self.filename = file
            if self.filename is not None:
                _, self.ext = os.path.splitext(self.filename)

            if self.filename is None:
                self.filename = self._guess_filename(*kwargs)

            if not self.filename:
                raise ValueError("Please provide an output filename")

        if split_output:
            self.split_output = re.findall(r"\{(.*?)\}", self.filename)
        else:
            self.split_output = None

    def close(self):
        for f in self._files.values():
            f.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, trace):
        self.close()

    def _f(self, data):
        if self.fileobj:
            return self.fileobj, None

        if self.split_output:
            path = self.filename.format(**{k: data.metadata(k) for k in self.split_output})
        else:
            path = self.filename

        if path not in self._files:
            flag = "wb" if not self.append else "ab"
            self._files[path] = open(path, flag)

        return self._files[path], path

    def _guess_filename(self, data=None):
        """Try to guess filename from data when not provided"""
        if data is not None:
            for attr in ["source_filename", "path"]:
                if hasattr(self, attr) and getattr(self, attr) is not None:
                    return [os.path.basename(getattr(self, attr))]

    def _check_overwrite(self, data):
        """Ensure we do not overwrite file that is being read"""
        if (
            data is not None
            and self.filename is not None
            and os.path.isfile(self.filename)
            and hasattr(data, "path")
            and data.path is not None
            and os.path.isfile(data.path)
            and os.path.samefile(self.filename, data.path)
        ):
            import warnings

            warnings.warn(UserWarning(f"Earthkit refusing to overwrite the file being read: {self.filename}"))
            return False
        return True

    def write(self, data=None, **kwargs):
        if not self._check_overwrite(data):
            return
        super().write(data, **kwargs)

    def _write(self, data, **kwargs):
        r = self._encode(data, suffix=self.ext, **kwargs)
        if hasattr(r, "__iter__"):
            for d in r:
                f, _ = self._f(d)
                d.to_file(f)
        else:
            f, _ = self._f(r)
            r.to_file(f)

    def _write_reader(self, reader, **kwargs):
        f, _ = self._f(None)

        if not reader.appendable:
            assert f.tell() == 0
        mode = "rb" if reader.binary else "r"
        with open(reader.path, mode) as g:
            while True:
                chunk = g.read(1024 * 1024)
                if not chunk:
                    break
                f.write(chunk)


target = FileTarget
