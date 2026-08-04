# Planning Schemas

These schemas describe Xplore planning outputs, not the canonical Lectio document. They are included as review/reference artifacts. Production Python output types should be Pydantic models and should use generated canonical literal types where available.

The server must apply semantic checks that JSON Schema cannot conveniently express, including contiguous `position`, candidate closure, question-ID rules, and heading exclusion.
