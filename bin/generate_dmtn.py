import textwrap
import os.path
import subprocess

from abc import ABC, abstractmethod
from datetime import datetime
from io import StringIO
from contextlib import contextmanager

from milestones import (
    write_output,
    get_latest_pmcs_path,
    get_local_data_path,
    load_milestones,
)


HEADING_CHARS = '#=-^"'

WBS_DEFINITIONS = {
    "02C.00": "Data Management Level 2 Milestones",
    "02C.01": "System Management",
    "02C.02": "Systems Engineering",
    "02C.03": "Alert Production",
    "02C.04": "Data Release Production",
    "02C.05": "Science User Interface and Tools",
    "02C.06": "Science Data Archive and Application Services",
    "02C.07": "LSST Data Facility",
    "02C.08": "International Communications and Base Site",
    "02C.09": "System Level Testing & Science Validation (Obsolete)",
    "02C.10": "Science Quality and Reliability Engineering",
}


def underline(text, character, overline=False):
    line = character * len(text) + "\n"
    return f"{line if overline else ''}{text}\n{line}".strip()


def add_context(context_name, context_manager, *, needs_level=False):
    def wrapper(cls):
        @contextmanager
        def new_method(self, *args, **kwargs):
            if needs_level:
                level = self._level + 1 if hasattr(self, "_level") else 1
                manager = context_manager(level, *args, **kwargs)
            else:
                manager = context_manager(*args, **kwargs)
            yield manager
            self._buffer.write(manager.get_result())

        setattr(cls, context_name, new_method)
        return cls

    return wrapper


class TextAccumulator(ABC):
    def __init__(self):
        self._buffer = StringIO()

    @abstractmethod
    def get_result(self):
        return self._buffer.getvalue()


class Paragraph(TextAccumulator):
    def write_line(self, line):
        self._buffer.write(line + "\n")

    def get_result(self):
        return super().get_result() + "\n"


@add_context("paragraph", Paragraph)
class Admonition(TextAccumulator):
    def __init__(self, admonition_type, title):
        super().__init__()
        self._buffer.write(admonition_type + ":: " + title if title else "")
        self._buffer.write("\n\n")

    def get_result(self):
        return ".." + textwrap.indent(self._buffer.getvalue(), "   ")[2:] + "\n"


@add_context("paragraph", Paragraph)
class BulletListItem(TextAccumulator):
    def get_result(self):
        line_start = "-"
        indented_result = textwrap.indent(
            self._buffer.getvalue(), " " * (len(line_start) + 1)
        )
        return line_start + indented_result[len(line_start) :]


@add_context("bullet", BulletListItem)
class BulletList(TextAccumulator):
    def get_result(self):
        return super().get_result()


# Can't reference BulletList before it is defined
BulletListItem = add_context("bullet_list", BulletList)(BulletListItem)


@add_context("paragraph", Paragraph)
@add_context("admonition", Admonition)
@add_context("bullet_list", BulletList)
class Section(TextAccumulator):
    def __init__(self, level, title, anchor=None):
        super().__init__()
        self._level = level
        if anchor:
            self._buffer.write(f".. _{anchor}:\n\n")
        self._buffer.write(underline(title, HEADING_CHARS[self._level]) + "\n\n")

    def get_result(self):
        return super().get_result()


# Can't reference Section before it is defined.
Section = add_context("section", Section, needs_level=True)(Section)


@add_context("paragraph", Paragraph)
@add_context("section", Section, needs_level=True)
@add_context("admonition", Admonition)
@add_context("bullet_list", BulletList)
class ReSTDocument(TextAccumulator):
    def __init__(self, title=None, subtitle=None, options=None):
        super().__init__()
        if title:
            self._buffer.write(underline(title, HEADING_CHARS[0], True) + "\n")
        if subtitle:
            self._buffer.write(underline(subtitle, HEADING_CHARS[1], True) + "\n")

        options = options or {}
        for name, value in options.items():
            self._buffer.write(f":{name}:")
            if value:
                self._buffer.write(f" {value}")
            self._buffer.write("\n")

        if title or subtitle or options:
            self._buffer.write("\n")

    def get_result(self):
        return super().get_result()


def get_version_info():
    pmcs_path = get_latest_pmcs_path()
    git_dir = os.path.dirname(pmcs_path)
    sha, date = (
        subprocess.check_output(
            ["git", "log", "-1", "--pretty=format:'%H %ad'", "--date=unix"], cwd=git_dir
        )
        .decode("utf-8")
        .strip("'")
        .split()
    )

    return sha, datetime.utcfromtimestamp(int(date))


def get_extreme_dates(milestones):
    earliest_ms, latest_ms = None, None
    for ms in milestones:
        if not earliest_ms or ms.due < earliest_ms:
            earliest_ms = ms.due
        if not latest_ms or ms.due > latest_ms:
            latest_ms = ms.due
    return earliest_ms, latest_ms


def generate_dmtn(milestones, wbs):
    doc = ReSTDocument(options={"tocdepth": 1})

    with doc.admonition("note", "**This technote is not yet published.**") as note:
        with note.paragraph() as p:
            p.write_line(
                "This note summarizes all milestones currently being "
                "tracked by the Data Management subsystem."
            )

    wbs_list = set(ms.wbs[:6] for ms in milestones if ms.wbs.startswith(wbs))

    with doc.section("Provenance") as my_section:
        with my_section.paragraph() as p:
            sha, timestamp = get_version_info()
            p.write_line(
                f"This document was generated based on the contents of "
                f"the `lsst-dm/milestones <https://github.com/lsst-dm/milestones>`_ "
                f"repository, version "
                f"`{sha[:8]} <https://github.com/lsst-dm/milestones/commit/{sha}>`_, "
                f"dated {timestamp.strftime('%Y-%m-%d')}."
            )

    with doc.section("Currently overdue milestones") as my_section:
        overdue_milestones = [
            ms
            for ms in milestones
            if ms.due < datetime.now() and ms.wbs.startswith(wbs) and not ms.completed
        ]

        if overdue_milestones:
            with my_section.bullet_list() as my_list:
                for ms in sorted(overdue_milestones, key=lambda ms: ms.wbs + ms.code):
                    with my_list.bullet() as b:
                        with b.paragraph() as p:
                            p.write_line(
                                f"`{ms.code}`_: {ms.name} "
                                f"[Due {ms.due.strftime('%Y-%m-%d')}]"
                            )
        else:
            with my_section.paragraph() as p:
                p.write_line("None.")

    with doc.section("Milestones by due date") as my_section:
        earliest_ms, latest_ms = get_extreme_dates(
            ms for ms in milestones if ms.wbs.startswith(wbs)
        )
        first_month = datetime(earliest_ms.year, earliest_ms.month, 1)
        last_month = (
            datetime(latest_ms.year, latest_ms.month + 1, 1)
            if latest_ms.month < 12
            else datetime(latest_ms.year + 1, 1, 1)
        )

        for year in range(latest_ms.year, earliest_ms.year - 1, -1):
            for month in range(12, 0, -1):
                start_date = datetime(year, month, 1)
                end_date = (
                    datetime(year, month + 1, 1)
                    if month < 12
                    else datetime(year + 1, 1, 1)
                )
                if end_date <= first_month or start_date >= last_month:
                    continue
                with my_section.section(f"Due in {start_date.strftime('%B %Y')}") as s:
                    output = [
                        ms
                        for ms in milestones
                        if ms.due >= start_date
                        and ms.due < end_date
                        and ms.wbs.startswith(wbs)
                    ]
                    with s.bullet_list() as my_list:
                        if output:
                            for ms in output:
                                with my_list.bullet() as b:
                                    with b.paragraph() as p:
                                        p.write_line(f"`{ms.code}`_: {ms.name}")
                        else:
                            with my_list.bullet() as b:
                                with b.paragraph() as p:
                                    p.write_line("No milestones due.")

    with doc.section("Milestones by WBS") as my_section:
        for wbs in sorted(wbs_list):
            with my_section.section(f"{wbs}: {WBS_DEFINITIONS[wbs]}") as section:
                for ms in sorted(milestones, key=lambda ms: ms.due):
                    if not ms.wbs.startswith(wbs):
                        continue
                    with section.section(
                        f"{ms.code}: {ms.name}", ms.code
                    ) as subsection:
                        with subsection.bullet_list() as my_list:
                            with my_list.bullet() as my_bullet:
                                with my_bullet.paragraph() as p:
                                    p.write_line(
                                        f"**Due:** {ms.due.strftime('%Y-%m-%d')}"
                                    )
                            if ms.completed:
                                with my_list.bullet() as my_bullet:
                                    with my_bullet.paragraph() as p:
                                        p.write_line(
                                            f"**Completed:** {ms.completed.strftime('%Y-%m-%d')}"
                                        )
                        if ms.description:
                            with subsection.paragraph() as p:
                                for line in ms.description.strip().split(". "):
                                    p.write_line(line.strip(" .") + ".")
                        else:
                            with subsection.admonition(
                                "warning", "No description available"
                            ):
                                pass

    return doc.get_result()


if __name__ == "__main__":
    milestones = load_milestones(get_latest_pmcs_path(), get_local_data_path())
    write_output("index.rst", generate_dmtn(milestones, "02C"), comment_prefix="..")
