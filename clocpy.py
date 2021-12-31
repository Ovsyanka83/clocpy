from pathlib import Path
from typing import Callable, Dict, Generator, Iterator, List, Optional, Sequence, Tuple, Type, Union
from dataclasses import dataclass
import os
from typing_extensions import TypeAlias
import click
import itertools
from rich.table import Table
from rich.console import Console


COMMENT_START: TypeAlias = str
COMMENT_END: TypeAlias = str
LANGUAGE_FACTORY: TypeAlias = Callable[
    [str, Union[str, Tuple[str, ...]], Sequence[str], Sequence[Tuple[COMMENT_START, COMMENT_END]]], "Language"
]


@dataclass
class Language:
    name: str
    file_suffix: Union[str, Tuple[str, ...]]
    comment_line_prefixes: Union[str, Tuple[str, ...]]
    multiline_comment_sequences: Tuple[Tuple[COMMENT_START, COMMENT_END], ...]

    @classmethod
    def get_factory(cls, default_comment_line_prefixes, default_multiline_comment_sequences):
        def language_factory(
            name: str,
            file_suffix: Union[str, Tuple[str, ...]],
            comment_line_prefixes: Union[str, Tuple[str, ...]] = (),
            multiline_comment_sequences: Tuple[Tuple[COMMENT_START, COMMENT_END], ...] = (),
        ):
            return Language(
                name,
                file_suffix,
                tuple(default_comment_line_prefixes) + tuple(comment_line_prefixes),
                tuple(default_multiline_comment_sequences) + tuple(multiline_comment_sequences),
            )

        return language_factory

    def __hash__(self):
        return hash((self.name, self.file_suffix))


@dataclass
class AnalysisInfo:
    files: int = 0
    blank: int = 0
    comment: int = 0
    code: int = 0


CLIKE = Language.get_factory("//", ("/*", "*/"))


SUPPORTED_LANGUAGES = (
    CLIKE("C", ".c"),
    CLIKE("C++", (".c++", ".cpp")),
    CLIKE("Javascript", ".js"),
    CLIKE("C#", (".cs", ".csx")),
    CLIKE("Java", ".java"),
    CLIKE("Golang", ".go"),
    Language("Python", (".py", ".pyw"), "#", (('"""', '"""'),)),
)


def figure_out_file_type(file: Path, supported_languages: Sequence[Language]) -> Optional[Language]:
    for lang in supported_languages:
        if file.suffix.endswith(lang.file_suffix):
            return lang


@click.command()
@click.argument("root_path", type=Path, default=Path("."))
def clocpy(root_path: Path):
    if root_path.is_dir():
        files = iter_all_files(root_path)
    elif root_path.is_file():
        files = (root_path,)
    else:
        raise ValueError(f'"{root_path}" is not a file or a directory')

    language_analysis_info: Dict[Language, AnalysisInfo] = {}

    for file in files:
        ftype = figure_out_file_type(file, SUPPORTED_LANGUAGES)
        if ftype is None:
            continue
        elif ftype not in language_analysis_info:
            analysis = AnalysisInfo()
            language_analysis_info[ftype] = analysis
        else:
            analysis = language_analysis_info[ftype]
        analysis.files += 1

        contents = [line.strip() for line in file.read_text().splitlines()]
        for line in contents:
            if not line:
                analysis.blank += 1
            elif line.startswith(ftype.comment_line_prefixes):
                analysis.comment += 1
            else:
                analysis.code += 1
    individual_table = Table(title="Clocpy analysis results")
    individual_table.add_column("Language")
    for field in AnalysisInfo.__dataclass_fields__.keys():
        column = " ".join(field.split("_")).title()
        individual_table.add_column(column)
    total_files = 0
    total_blanks = 0
    total_comments = 0
    total_code = 0
    sorted_analysis_info = sorted(language_analysis_info.items(), key=lambda o: o[1].code, reverse=True)
    for index, (ftype, analysis) in enumerate(sorted_analysis_info):
        individual_table.add_row(
            ftype.name,
            *(str(t) for t in [analysis.files, analysis.blank, analysis.comment, analysis.code]),
            end_section=(index == len(language_analysis_info) - 1),
        )
        total_files += analysis.files
        total_blanks += analysis.blank
        total_comments += analysis.comment
        total_code += analysis.code

    individual_table.add_row("SUM", *(str(t) for t in [total_files, total_blanks, total_comments, total_code]))
    Console().print(individual_table)


def pathwalk(
    top: Union[str, Path],
    topdown: bool = True,
    onerror: Optional[Callable[[OSError], None]] = None,
    followlinks: bool = False,
) -> Generator[Tuple[Path, List[Path], List[Path]], None, None]:
    for root, dirs, files in os.walk(top, topdown, onerror, followlinks):
        yield Path(root), [Path(root, d) for d in dirs], [Path(root, f) for f in files]


def iter_all_files(root_dir: Union[Path, str]) -> Iterator[Path]:
    return itertools.chain.from_iterable(
        (file for file in files)
        for _, _, files in pathwalk(
            root_dir,
            followlinks=True,
        )
    )


if __name__ == "__main__":
    clocpy()
