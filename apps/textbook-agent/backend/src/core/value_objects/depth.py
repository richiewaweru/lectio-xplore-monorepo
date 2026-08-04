from enum import Enum


class Depth(str, Enum):
    LIGHT = "light"
    STANDARD = "standard"
    DEEP = "deep"
