# (C) Copyright 2020 ECMWF.
#
# This software is licensed under the terms of the Apache Licence Version 2.0
# which can be obtained at http://www.apache.org/licenses/LICENSE-2.0.
# In applying this licence, ECMWF does not waive the privileges and immunities
# granted to it by virtue of its status as an intergovernmental organisation
# nor does it submit to any jurisdiction.
#

import logging

from earthkit.data.utils import ensure_iterable

LOG = logging.getLogger(__name__)


TIME_DIM = 0
DATE_DIM = 1
STEP_DIM = 2
Z_DIM = 1
Y_DIM = 2
X_DIM = 3
N_DIM = 4

DIM_ORDER = [N_DIM, TIME_DIM, DATE_DIM, STEP_DIM, Z_DIM, Y_DIM, X_DIM]


class CompoundKey:
    name = None
    keys = []

    def remapping(self):
        return {self.name: "".join([str(k) for k in self.keys])}

    @staticmethod
    def make(key):
        ck = COMPOUND_KEYS.get(key, None)
        return ck() if ck is not None else None


class ParamLevelKey(CompoundKey):
    name = "param_level"
    keys = ["param", "level", "levelist"]


# class LevelAndTypeKey(CompoundKey):
#     name = "level_and_type"
#     keys = ["level", "levtype"]


COMPOUND_KEYS = {v.name: v for v in [ParamLevelKey]}
LEVEL_KEYS = ["level", "levelist", "topLevel", "bottomLevel", "levels", "typeOfLevel", "levtype"]


def find_alias(key):
    keys = [LEVEL_KEYS]
    r = []
    for k in keys:
        if key in k:
            r.extend(k)
    return r


class Vocabulary:
    @staticmethod
    def make(name):
        return VOCABULARIES[name]()


class MarsVocabulary(Vocabulary):
    def level(self):
        return "levelist"

    def level_type(self):
        return "levtype"


class CFVocabulary(Vocabulary):
    def level(self):
        return "level"

    def level_type(self):
        return "typeOfLevel"


VOCABULARIES = {"mars": MarsVocabulary, "cf": CFVocabulary}


class Dim:
    name = None
    key = None
    alias = None
    drop = None
    # predefined_index = -1

    def __init__(self, owner, name=None, key=None, active=True):
        self.owner = owner
        self.profile = owner.profile
        self.active = active
        self.alias = ensure_iterable(self.alias)
        self.drop = ensure_iterable(self.drop)
        if name is not None:
            self.name = name

        if self.key is None:
            self.key = self.name

        self.coords = {}

    def copy(self):
        return self.__class__(self.owner)

    def _replace_dim(self, key_src, key_dst):
        if key_dst not in self.profile.dim_keys:
            try:
                idx = self.profile.dim_keys.index(key_src)
                self.profile.dim_keys[idx] = key_dst
            except ValueError:
                self.profile.dim_keys.append(key_dst)

    def __contains__(self, key):
        return key == self.name or key in self.alias

    def allowed(self, key):
        return key not in self and key not in self.drop

    def check(self):
        if self.active:
            self.active = self.condition()
            if self.active:
                self.deactivate_drop_list()

    def condition(self):
        return True

    def update(self, ds, attributes, squeeze=True):
        # if self.key in ds.indices():
        #     print(f"-> {self.name} key={self.key} active={self.active} ds={ds.index(self.key)}")

        if not self.active:
            return

        # sanity check
        if self.profile.variable_key in self:
            raise ValueError(
                (
                    f"Variable key {self.profile.var_key} cannot be in "
                    f"dimension={self.name} group={self.group}"
                )
            )

        # assert self.name in self.profile.dim_keys, f"self.name={self.name}"
        if self.key not in self.profile.ensure_dims:
            if squeeze:
                if not (self.key in ds.indices() and len(ds.index(self.key)) > 1):
                    self.active = False
            else:
                if not (self.key in ds.indices() and len(ds.index(self.key)) >= 1):
                    self.active = False

        self.deactivate_drop_list()

    def deactivate_drop_list(self):
        self.owner.deactivate([self.name, self.key] + self.drop, ignore_dim=self)

    def as_coord(self, key, values, tensor):
        if key not in self.coords:
            from .coord import Coord

            self.coords[key] = Coord.make(key, values, ds=tensor.source)
        return key, self.coords[key]

    def __repr__(self):
        return f"{self.__class__.__name__}(name={self.name}, key={self.key})"


class DateDim(Dim):
    name = "date"
    drop = ["valid_datetime", "base_datetime", "forecast_reference_time"]


class TimeDim(Dim):
    name = "time"
    drop = ["valid_datetime", "base_datetime"]


class StepDim(Dim):
    name = "step"
    drop = ["valid_datetime", "stepRange"]


class ValidTimeDim(Dim):
    name = "valid_time"
    # key = "valid_datetime"
    drop = ["time", "date", "step", "base_datetime", "validityTime", "validityDate", "valid_datetime"]
    rank = 1


class ForecastRefTimeDim(Dim):
    name = "forecast_reference_time"
    drop = ["time", "date", "valid_datetime", "dataTime", "dataDate"]
    alias = ["base_datetime"]


class IndexingTimeDim(Dim):
    name = "indexing_time"
    drop = ["indexingTime", "indexingDate"]


class ReferenceTimeDim(Dim):
    name = "reference_time"
    drop = ["referenceTime", "referenceDate"]


class CustomForecastRefDim(Dim):
    @staticmethod
    def _datetime(val):
        if not val:
            return None
        else:
            from earthkit.data.utils.dates import datetime_from_grib

            try:
                date, time = val.split("_")
                return datetime_from_grib(int(date), int(time)).isoformat()
            except Exception:
                return val

    def __init__(self, owner, keys, *args, active=True, **kwargs):
        if isinstance(keys, str):
            self.key = keys
        elif isinstance(keys, list) and len(keys) == 2:
            date = keys[0]
            time = keys[1]
            self.key = f"{date}_{time}"
            self.drop = [date, time]
            if active:
                owner.register_remapping(
                    {self.key: "{" + date + "}_{" + time + "}"},
                    patch={self.key: CustomForecastRefDim._datetime},
                )
        else:
            raise ValueError(f"Invalid keys={keys}")
        super().__init__(owner, *args, active=active, **kwargs)

    def copy(self):
        return self.__class__(self.owner, self.key)


class LevelDim(Dim):
    drop = ["levelist", "level"]
    alias = "levelist"

    def __init__(self, owner, key, *args, **kwargs):
        self.key = key
        self.name = key
        super().__init__(owner, *args, **kwargs)

    def copy(self):
        return self.__class__(self.owner, self.key)


class LevelPerTypeDim(Dim):
    name = "level_per_type"
    drop = ["levelist", "levtype", "typeOfLevel"]

    def __init__(self, owner, level_key, level_type_key, *args, **kwargs):
        self.key = level_key
        self.level_key = level_key
        self.level_type_key = level_type_key
        super().__init__(owner, *args, **kwargs)

    def copy(self):
        return self.__class__(self.owner, self.level_key, self.level_type_key)

    def as_coord(self, key, values, tensor):
        lev_type = tensor.source[0].metadata(self.level_type_key)
        if not lev_type:
            raise ValueError(f"{d.type_key} not found in metadata")

        if lev_type not in self.coords:
            from .coord import Coord

            coord = Coord.make(lev_type, list(values), ds=tensor.source)
            self.coords[lev_type] = coord
        return lev_type, self.coords[lev_type]


class LevelAndTypeDim(Dim):
    name = "level_and_type"
    drop = ["level", "levelist", "typeOfLevel", "levtype"]

    def __init__(self, owner, level_key, level_type_key, active=True, *args, **kwargs):
        self.level_key = level_key
        self.level_type_key = level_type_key
        if active:
            owner.register_remapping(
                {self.name: "{" + self.level_key + "}{" + self.level_type_key + "}"},
            )
        super().__init__(owner, *args, active=active, **kwargs)

    def copy(self):
        return self.__class__(self.owner, self.level_key, self.level_type_key, active=self.active)


class LevelTypeDim(Dim):
    name = "levtype"
    drop = ["typeOfLevel"]

    def update(self, ds, attributes, squeeze=True):
        # print("UPDATE levtype", ds.index("levtype"))
        super().update(ds, attributes, squeeze)
        if self.active and not squeeze and len(ds.index(self.name)) < 2:
            self.active = False


class TypeOfLevelDim(Dim):
    name = "typeOfLevel"
    drop = ["levtype"]

    def update(self, ds, attributes, squeeze=True):
        # print("UPDATE typeOfLevel", ds.index("typeOfLevel"))
        super().update(ds, attributes, squeeze)
        if self.active and not squeeze and len(ds.index(self.name)) < 2:
            self.active = False


class NumberDim(Dim):
    name = "number"
    drop = []


class RemappingDim(Dim):
    def __init__(self, owner, name, keys):
        self.name = name
        self.drop = self.build_drop(keys)
        super().__init__(owner)

    def build_drop(self, keys):
        r = list(keys)
        for k in keys:
            r.extend(find_alias(k))
        return r


class CompoundKeyDim(RemappingDim):
    def __init__(self, owner, ck):
        # self.name = ck.name
        # # self.ck = ck
        # self.drop = ck.keys
        super().__init__(owner, ck.name, ck.keys)


class OtherDim(Dim):
    drop = []

    def __init__(self, owner, name, *args, **kwargs):
        self.name = name
        super().__init__(owner, *args, **kwargs)

    def copy(self):
        return self.__class__(self.owner, self.name)


class DimMode:
    def make_dim(self, owner, name, *args, **kwargs):
        if name in PREDEFINED_DIMS:
            return PREDEFINED_DIMS[name](owner, *args, **kwargs)
        return OtherDim(owner, name, *args, **kwargs)

    def build(self, profile, owner, active=True):
        return {name: self.make_dim(owner, name, active=active) for name in self.default}


class ForecastTimeDimMode(DimMode):
    name = "forecast"
    default = ["forecast_reference_time", "step"]
    mappings = {"seasonal": {"datetime": "indexing_time", "step": "forecastMonth"}}

    def build(self, profile, owner, active=True):
        mapping = profile.time_dim_mapping
        if mapping:
            if isinstance(mapping, str):
                mapping = self.mappings.get(mapping, None)
                if mapping is None:
                    raise ValueError(f"Unknown mapping={mapping}")

            if isinstance(mapping, dict):
                step = mapping.get("step", None)
                if step is None:
                    raise ValueError(f"step is required in mapping={mapping}")

                datetime = mapping.get("datetime", None)
                if datetime:
                    return {name: self.make_dim(owner, name, active=active) for name in [datetime, step]}
                else:
                    datetime = [mapping["date"], mapping["time"]]
                    dim1 = CustomForecastRefDim(owner, datetime, active=active)
                    dim2 = self.make_dim(owner, step, active=active)
                    return {d.name: d for d in [dim1, dim2]}
            else:
                raise ValueError(f"Unsupported mapping type={type(mapping)}")

        else:
            return {name: self.make_dim(owner, name, active=active) for name in self.default}


class ValidTimeDimMode(DimMode):
    name = "valid_time"
    default = ["valid_time"]


class RawTimeDimMode(DimMode):
    name = "raw"
    default = ["date", "time", "step"]


class LevelDimMode(DimMode):
    name = "level"
    default = ["level"]
    dim = LevelDim
    alias = LEVEL_KEYS

    def build(self, profile, owner, **kwargs):
        level_key = profile.vocabulary.level()
        level_type_key = profile.vocabulary.level_type()
        return {self.name: self.dim(owner, level_key, level_type_key, **kwargs)}


class LevelPerTypeDimMode(LevelDimMode):
    name = "level_per_type"
    default = ["level_per_type"]
    dim = LevelPerTypeDim


class LevelAndTypeDimMode(LevelDimMode):
    name = "level_and_type"
    default = ["level_and_type"]
    dim = LevelAndTypeDim


TIME_DIM_MODES = {v.name: v for v in [ForecastTimeDimMode, ValidTimeDimMode, RawTimeDimMode]}
LEVEL_DIM_MODES = {v.name: v for v in [LevelDimMode, LevelPerTypeDimMode, LevelAndTypeDimMode]}


class DimGroup:
    used = {}
    ignored = {}

    def dims(self):
        return self.used, self.ignored


class NumberDimGroup(DimGroup):
    name = "number"

    def __init__(self, profile, owner):
        self.used = {self.name: NumberDim(owner)}


class TimeDimGroup(DimGroup):
    name = "time"

    def __init__(self, profile, owner):
        mode = TIME_DIM_MODES.get(profile.time_dim_mode, None)
        if mode is None:
            raise ValueError(f"Unknown time_dim_mode={profile.time_dim_mode}")

        mode = mode()
        self.used = mode.build(profile, owner)
        self.ignored = {
            k: v().build(profile, owner, active=False) for k, v in TIME_DIM_MODES.items() if v != mode
        }


class LevelDimGroup(DimGroup):
    name = "level"

    def __init__(self, profile, owner):
        mode = LEVEL_DIM_MODES.get(profile.level_dim_mode, None)
        if mode is None:
            raise ValueError(f"Unknown level_dim_mode={profile.level_dim_mode}")

        mode = mode()
        self.used = mode.build(profile, owner)
        self.ignored = {
            k: v().build(profile, owner, active=False) for k, v in LEVEL_DIM_MODES.items() if v != mode
        }


DIM_GROUPS = {v.name: v for v in [NumberDimGroup, TimeDimGroup, LevelDimGroup]}


class Dims:
    def __init__(self, profile, dims=None):
        self.profile = profile
        # self.extra_remappings = {}
        # self.extra_patches = {}

        if dims is not None:
            self.dims = dims
            return

        self.dims = {}
        ignored = {}

        # print("INIT index_keys", self.profile.index_keys)

        # initial check for variable-related keys
        from .profile import VARIABLE_KEYS

        var_keys = [self.profile.variable_key] + VARIABLE_KEYS
        keys = list(self.profile.index_keys)
        if self.profile.variable_key in keys:
            keys.remove(self.profile.variable_key)
        keys += self.profile.extra_dims + self.profile.fixed_dims
        for k in keys:
            if k in var_keys:
                print("index_keys=", self.profile.index_keys)
                print("extra_dims=", self.profile.extra_dims)
                print("fixed_dims=", self.profile.fixed_dims)
                raise ValueError(f"Variable-related key {k} cannot be a dimension")

        # each remapping is a dimension. They can contain variable related keys.
        remapping = self.profile.remapping.build()
        if remapping:
            for k in remapping.lists:
                self.dims[k] = RemappingDim(self, k, remapping.lists[k])

        # search for compound keys. Note: the variable key can be a compound key
        # so has to added here. If a remapping uses the same key name, the compound
        # key is not added.
        for k in [self.profile.variable_key] + keys:
            if not remapping or k not in remapping.lists:
                ck = CompoundKey.make(k)
                if ck is not None:
                    self.dims[k] = CompoundKeyDim(self, ck)

        # add predefined dimensions
        self.core_dim_order = []
        groups = {}
        for k, v in DIM_GROUPS.items():
            gr = v(self.profile, self)
            groups[k] = gr
            used, ignored = gr.dims()
            for k, v in used.items():
                print(f"ADD DIM {k} {v}")
                if k not in self.dims:
                    self.dims[k] = v
                    self.core_dim_order.append(k)
                else:
                    ignored[k] = v
            ignored.update(ignored)

        # each key can define a dimension
        for k in keys:
            if k not in self.dims and k not in ignored:
                if not remapping or k not in remapping.lists:
                    self.dims[k] = OtherDim(self, name=k)

        # check dims consistency. The ones can be used
        # marked as active
        for k, d in self.dims.items():
            d.check()

        # check for any dimensions related to variable keys. These have to
        # be removed from the list of active dims.
        self.deactivate(var_keys, others=True, collect=True)

        # only the active dims are used
        self.dims = {k: v for k, v in self.dims.items() if v.active}

        # # ignored dims are used for later checks?
        # self.ignore = ignored
        # self.ignore.update({k: v for k, v in self.dims.items() if not v.active})

        print(f"INIT dims={self.dims.keys()}")

        # ensure all the required keys are in the profile
        keys = []
        for d in self.dims.values():
            keys.append(d.key)

        self.profile.add_keys(keys)

    def register_remapping(self, remapping, patch=None):
        self.profile.remapping.add(remapping, patch)

    def deactivate(self, keys, ignore_dim=None, others=False, collect=False):
        names = []
        for d in self.dims.values():
            if d.active and d != ignore_dim:
                if any(key in d for key in keys):
                    # print(f"deactivate name={self.name} d={d.name} self.group={self.all_dims}")
                    d.active = False
                    if others:
                        d.deactivate_drop_list()
                    if collect:
                        names.append(d.name)

        if collect:
            return names

            # if d.active and self.same(d):
            #     d.active = False

    def remove(self, keys, ignore_dim=None, others=False, collect=False):
        self.deactivate(keys, ignore_dim, others, collect)
        self.dims = {k: v for k, v in self.dims.items() if v.active}

    def update(self, ds, attributes, variable_keys):
        for k, d in self.dims.items():
            d.update(ds, attributes, self.profile.squeeze)

        self.dims = {k: v for k, v in self.dims.items() if v.active}

    def allowed(self, key):
        return all(d.allowed(key) for d in self.dims.values())

    @property
    def active_dim_keys(self):
        return [d.key for d in self.dims.values() if d.active]

    def make_coords(self):
        r = {d.coord.name: d.coord.make_var(self.profile) for d in self.dims.values() if d.coord is not None}
        return r

    def as_coord(self, tensor):
        r = {}

        def _get(k):
            for d in self.dims.values():
                if k == d.key:
                    return d

        for k, v in tensor.user_coords.items():
            for d in self.dims.values():
                d = _get(k)
                name, coord = d.as_coord(k, v, tensor)
                r[name] = coord
        return r

    def to_list(self, copy=True):
        if copy:
            return [d.copy() for d in self.dims.values()]
        return list(self.dims.values())


PREDEFINED_DIMS = {}
for i, d in enumerate(
    [
        NumberDim,
        ForecastRefTimeDim,
        DateDim,
        TimeDim,
        StepDim,
        ValidTimeDim,
        LevelDim,
        LevelPerTypeDim,
        LevelAndTypeDim,
    ]
):
    PREDEFINED_DIMS[d.name] = d
    d.predefined_index = i
