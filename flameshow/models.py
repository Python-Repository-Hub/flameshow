from dataclasses import dataclass, field
import datetime
import logging
import time
from typing import Dict, List, Set
from typing_extensions import Self

from .runtime import r


logger = logging.getLogger(__name__)


class Frame:
    def __init__(
        self, name, _id, children=None, parent=None, values=None, root=None
    ) -> None:
        self.name = name
        self._id = _id
        if children:
            self.children = children
        else:
            self.children = []
        self.parent = parent
        if not values:
            self.values = []
        else:
            self.values = values

        parts = self.name.split("/")
        if len(parts) > 1:
            self.golang_package = "/".join(parts[:-1])
        else:
            self.golang_package = "buildin"

        golang_module_function = parts[-1]
        golang_module = golang_module_function.split(".")[0]

        self.display_name = golang_module_function
        self.color_key = golang_module

        self.mapping_file = ""
        self.root = root

    def pile_up(self, childstack: Self):
        childstack.parent = self

        for exist_child in self.children:
            # added to exist, no need to create one
            if exist_child.name == childstack.name:
                # some cases, childstack.children total value not equal to
                # childstack.values
                # so, we need to add values of "parent" instead of add values
                # by every child
                exist_child.values = list(
                    map(sum, zip(exist_child.values, childstack.values))
                )

                for new_child in childstack.children:
                    exist_child.pile_up(new_child)
                return

        self.children.append(childstack)

    def __eq__(self, other):
        if isinstance(other, Frame):
            return self._id == other._id
        return False

    def render_detail(self, sample_index: int, sample_unit: str):
        raise NotImplementedError

    def render_title(self) -> str:
        raise NotImplementedError

    @property
    def display_color(self):
        return r.get_color(self.color_key)

    def __repr__(self) -> str:
        return f"<Frame #{self._id} {self.name}>"


@dataclass
class SampleType:
    sample_type: str = ""
    sample_unit: str = ""


@dataclass
class Profile:
    # required
    filename: str
    root_stack: Frame
    highest_lines: int
    # total samples is one top most sample, it's a list that contains all
    # its parents all the way up
    total_sample: int
    sample_types: List[SampleType]
    # int id mapping to Frame
    id_store: Dict[int, Frame]

    # optional
    default_sample_type_index: int = -1
    period_type: SampleType | None = None
    period: int = 0
    created_at: datetime.datetime | None = None

    # init by post_init
    lines: List = field(init=False)

    frameid_to_lineno: Dict[int, int] = field(init=False)

    # Frame grouped by same name
    name_aggr: Dict[str, List[Frame]] = field(init=False)

    def __post_init__(self):
        """
        init_lines must be called before render
        """
        t1 = time.time()
        logger.info("start to create lines...")

        root = self.root_stack

        lines = [
            [root],
        ]
        frameid_to_lineno = {0: 0}
        current = root.children
        line_no = 1

        while len(current) > 0:
            line = []
            next_line = []

            for child in current:
                line.append(child)
                frameid_to_lineno[child._id] = line_no
                next_line.extend(child.children)

            lines.append(line)
            line_no += 1
            current = next_line

        t2 = time.time()
        logger.info("create lines done, took %.2f seconds", t2 - t1)
        self.lines = lines
        self.frameid_to_lineno = frameid_to_lineno

        self.name_aggr = self.get_name_aggr(self.root_stack)

    def get_name_aggr(
        self, start_frame: Frame, names: Set[str] | None = None
    ) -> Dict[str, List[Frame]]:
        name = start_frame.name

        result = {}
        if names is None:
            names = set()
        if name not in names:
            result[name] = [start_frame]

        for child in start_frame.children:
            name_aggr = self.get_name_aggr(child, names | set([name]))
            for key, value in name_aggr.items():
                result.setdefault(key, []).extend(value)

        return result
