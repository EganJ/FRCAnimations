"""
A build script which can be used to compile animations and build the website.
Fuzzy matching is used to enable quickly specifying targets in the website folder.
"""
import inspect
import os
import subprocess
import argparse
import sys
import pathlib
import importlib
import re

from thefuzz import process, fuzz

# prevent manim from printing
sys.stdout = open(os.devnull, "w")
import manim as mn

sys.stdout = sys.__stdout__


source_path = pathlib.Path("animations")

exclude_folders = ["__pycache__", "media", "_style"]

# Split around A-Z, _, /, and \
split_regex = "A-Z_/\\\\"


def get_all_file_paths(base: pathlib.Path) -> list[pathlib.Path]:
    """Searches source_path for all potential files. Returns a mapping of file names to their paths."""
    return [file_path for file_path in base.glob("**/*.py")]


def get_all_paths() -> list[pathlib.Path]:
    """Searches source_path for all possible paths, including sub-paths, and returns them.
    This function is used to collect paths for matching with the -p option.
    The paths include paths to all files.
    """
    return [
        pathlib.Path(*path.parts[1:])
        for path in source_path.glob("**")
        if path.name not in exclude_folders
    ]


def get_all_scenes(file_paths: list[pathlib.Path]) -> dict[str, pathlib.Path]:
    """Searches source_path for all possible scenes.
    Returns a mapping of scenes to their files.
    Duplicate scenes and files are not explicitly handled.
    """
    return dict(
        [
            (scene_name, file_path)
            for file_path in file_paths
            for scene_name in get_scene_names(file_path)
        ]
    )


def get_scene_names(file_path: pathlib.Path) -> list[str]:
    module_path = str(file_path).replace("/", ".").removesuffix(".py")
    module = importlib.import_module(module_path)

    return [
        name
        for name, cls in inspect.getmembers(module)
        if inspect.isclass(cls)
        and issubclass(cls, mn.Scene)
        and cls.__module__ == module_path
    ]


def get_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Builds animations.",
    )
    parser.add_argument(
        "--production",
        action="store_true",
        help="whether to build production versions of animations",
    )

    description = """
    Inputs to the builder. All inputs are parsed using a fuzzy matcher which enables (often aggressive) abbreviations.
    The fuzzer works by comparing tokens in the input with target tokens. 
    Token splits are determined using capital letters, slashes, and underscores.
    So, to match a scene like "CoincidentLine", "coinLi" is probably sufficient, but "coinli" and "COINLI" will likely
    fail due to to many (or to few) tokens.
    """

    group = parser.add_argument_group("inputs", description)

    group.add_argument(
        "-f",
        "--file",
        nargs="*",
        default=None,
        help="python files to build",
    )
    group.add_argument(
        "-p",
        "--path",
        nargs="*",
        default=None,
        help='paths relative to "/{}" which are recursively searched for files'.format(
            source_path
        ),
    )
    group.add_argument(
        "-s",
        "--scene",
        nargs="*",
        help="a list of scenes to render",
    )
    return parser


def fuzzy_search(targets: list[str], values: list[str]) -> list[str]:
    parsed_targets = dict([(target, split_tokens(target)) for target in targets])

    matches = []
    for value in values:
        parsed_value = split_tokens(value)
        _, score, target_name = process.extractOne(  # type: ignore
            parsed_value, parsed_targets, scorer=fuzz.token_sort_ratio  # type: ignore
        )

        if score < 95:
            print("Found {} for input {} (score: {})".format(target_name, value, score))
        matches.append(target_name)
    return matches


def split_tokens(input: str) -> str:
    parsed = re.search("[^{}]*".format(split_regex), input)
    matches: list[str] = []
    if parsed is not None:
        matches.append(parsed.group(0))

    end = re.findall("[{}][^{}]*".format(split_regex, split_regex), input)
    matches.extend(end)
    return " ".join(matches)


def main():
    args = get_arg_parser().parse_args()

    quality = "h" if args.production else "l"

    target_paths = []
    if args.path is not None:
        all_paths = get_all_paths()
        all_path_strs = [str(path) for path in all_paths]
        results = fuzzy_search(all_path_strs, args.path)
        file_path_lists = [
            get_all_file_paths(source_path / pathlib.Path(path)) for path in results
        ]
        target_paths = [item for sublist in file_path_lists for item in sublist]

    else:
        target_paths = get_all_file_paths(source_path)

    if args.file is not None:
        # we use a dict so we can split names into sequences
        target_names = [path.name for path in target_paths]
        results = fuzzy_search(target_names, args.file)
        target_paths = [path for path in target_paths if path.name in results]

    scenes = get_all_scenes(target_paths)
    if args.scene is not None:
        results = fuzzy_search(list(scenes.keys()), args.scene)
        scenes = dict([(k, v) for k, v in scenes.items() if k in results])

    for scene_name, file_path in scenes.items():
        manim_command = (
            "manim render -v ERROR -q{quality} {file_path} {scene_names}".format(
                quality=quality,
                file_path=file_path,
                scene_names=scene_name,  # " ".join(scene_names),
            )
        )

        print("Rendering {} - {}".format(file_path, scene_name))
        subprocess.run(manim_command, shell=True)


if __name__ == "__main__":
    main()
