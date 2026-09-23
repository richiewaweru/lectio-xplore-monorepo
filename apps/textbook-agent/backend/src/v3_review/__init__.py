"""Persisted coherence-report helpers still read by generation documents.

The legacy coherence reviewer and section-writer repair loop are retired.
"""

from v3_review.report_summary import coherence_report_to_generation_summary

__all__ = [
    "coherence_report_to_generation_summary",
]
