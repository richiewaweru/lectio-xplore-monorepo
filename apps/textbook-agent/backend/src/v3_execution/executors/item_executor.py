"""Compatibility re-export. Current callers should import curriculum.items.generator."""

import sys
from curriculum.items.generator import *  # noqa: F403
import curriculum.items.generator as _generator


class _ItemExecutorModule(sys.modules[__name__].__class__):  # type: ignore[misc]
    @property
    def run_llm(self):
        return _generator.run_llm

    @run_llm.setter
    def run_llm(self, value):
        _generator.run_llm = value

    @run_llm.deleter
    def run_llm(self):
        pass

    @property
    def execute_items_with_diagnostics(self):
        return _generator.execute_items_with_diagnostics

    @execute_items_with_diagnostics.setter
    def execute_items_with_diagnostics(self, value):
        _generator.execute_items_with_diagnostics = value

    @execute_items_with_diagnostics.deleter
    def execute_items_with_diagnostics(self):
        pass


sys.modules[__name__].__class__ = _ItemExecutorModule
