"""Application-wide enumerations."""

from __future__ import annotations

from enum import Enum


class FileType(str, Enum):
    PDF = ".pdf"
    DOCX = ".docx"
    TXT = ".txt"
    MD = ".md"
    MARKDOWN = ".markdown"
    CSV = ".csv"
    XLSX = ".xlsx"