# (C) Copyright 2020 ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.
#

import datetime
import re

import numpy as np

from earthkit.data.wrappers import get_wrapper

ECC_SECONDS_FACTORS = {"s": 1, "m": 60, "h": 3600}
NUM_STEP_PATTERN = re.compile(r"\d+")
SUFFIX_STEP_PATTERN = re.compile(r"\d+[a-zA-Z]{1}")


def to_datetime(dt):
    if isinstance(dt, datetime.datetime):
        return dt

    if isinstance(dt, datetime.date):
        return datetime.datetime(dt.year, dt.month, dt.day)

    if isinstance(dt, np.datetime64):
        # Looks like numpy dates conversion vary
        dt = dt.astype(datetime.datetime)

        if isinstance(dt, datetime.datetime):
            return dt

        if isinstance(dt, datetime.date):
            return to_datetime(dt)

        if isinstance(dt, int):
            return datetime.datetime.utcfromtimestamp(dt * 1e-9)

        raise ValueError("Failed to convert numpy datetime {}".format((dt, type(dt))))

    dt = get_wrapper(dt)

    return to_datetime(dt.to_datetime())


def mars_like_date_list(start, end, by):
    """Return a list of datetime objects from start to end .

    Parameters
    ----------
    start : [type]
        [description]
    end : [type]
        [description]
    by : [type]
        [description]

    Returns
    -------
    [type]
        [description]
    """
    assert by > 0, by
    assert end >= start
    result = []
    while start <= end:
        result.append(start)
        start = start + datetime.timedelta(days=by)
    return result


def to_datetime_list(datetimes):  # noqa C901
    if isinstance(datetimes, (datetime.datetime, np.datetime64)):
        return to_datetime_list([datetimes])

    if isinstance(datetimes, (list, tuple)):
        if len(datetimes) == 3 and isinstance(datetimes[1], str) and datetimes[1].lower() == "to":
            return mars_like_date_list(to_datetime(datetimes[0]), to_datetime(datetimes[2]), 1)

        if (
            len(datetimes) == 5
            and isinstance(datetimes[1], str)
            and isinstance(datetimes[3], str)
            and datetimes[1].lower() == "to"
            and datetimes[3].lower() == "by"
        ):
            return mars_like_date_list(
                to_datetime(datetimes[0]), to_datetime(datetimes[2]), int(datetimes[4])
            )

        return [to_datetime(x) for x in datetimes]

    datetimes = get_wrapper(datetimes)

    return to_datetime_list(datetimes.to_datetime_list())


def to_date_list(obj):
    return sorted(set(to_datetime_list(obj)))


def to_time(dt):
    if isinstance(dt, float):
        dt = int(dt)

    if isinstance(dt, int):
        h = int(dt / 100)
        m = dt % 100
        return datetime.time(hour=h, minute=m)

    if isinstance(dt, datetime.time):
        return dt

    if isinstance(dt, datetime.datetime):
        return datetime.time

    if isinstance(dt, datetime.date):
        return datetime.time()

    if isinstance(dt, np.datetime64):
        # Looks like numpy dates conversion vary
        dt = dt.astype(datetime.datetime)

        if isinstance(dt, datetime.datetime):
            return dt.time

        if isinstance(dt, datetime.date):
            return to_datetime(dt)

        raise ValueError("Failed to convert numpy datetime {}".format((dt, type(dt))))


def to_time_list(times):
    if not isinstance(times, (list, tuple)):
        return to_time_list([times])
    return [to_time(x) for x in times]


def step_to_delta(step):
    # TODO: make it work for all the ecCodes step formats
    if isinstance(step, int):
        return datetime.timedelta(hours=step)
    elif isinstance(step, str):
        if re.fullmatch(NUM_STEP_PATTERN, step):
            sec = int(step) * 3600
            return datetime.timedelta(seconds=sec)
        elif re.fullmatch(SUFFIX_STEP_PATTERN, step):
            factor = ECC_SECONDS_FACTORS.get(step[-1], None)
            if factor is None:
                raise ValueError(f"Unsupported ecCodes step units in step: {step}")
            sec = int(step[:-1]) * factor
            return datetime.timedelta(seconds=sec)
    elif isinstance(step, datetime.timedelta):
        return step

    raise ValueError(f"Unsupported ecCodes step: {step}")


def datetime_from_grib(date, time):
    date = int(date)
    time = int(time)

    return datetime.datetime(
        date // 10000,
        date % 10000 // 100,
        date % 100,
        time // 100,
        time % 100,
    )


def datetime_to_grib(dt):
    date = int(dt.strftime("%Y%m%d"))
    time = dt.hour * 100 + dt.minute
    return date, time
