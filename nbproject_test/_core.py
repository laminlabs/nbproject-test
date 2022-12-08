import os
from pathlib import Path
from time import perf_counter

from natsort import natsorted
from nbclient import NotebookClient
from nbformat import NO_CONVERT
from nbformat import read as read_nb
from nbformat import write as write_nb


def _list_nbs_in_md(nb_folder, md_filename="index.md"):
    notebooks = []
    names = []

    index_path = nb_folder / md_filename
    if index_path.exists():
        print(f"Reading {index_path}", flush=True)
        with open(index_path) as f:
            index = f.read()

        # parse out indexed file list
        if "```{toctree}" in index:
            content = index.split("```{toctree}")[1]
            content = content.split("\n\n")[1]
            content = content.split("```")[0]

            # if a file is a notebook, add it
            # return non-notebook names
            for name in content.split():
                nb = nb_folder / f"{name}.ipynb"
                if nb.exists():
                    notebooks.append(nb)
                else:
                    names.append(name)

    return notebooks, names


def add_execution_count(nb):
    """Add consecutive execution count.

    Notebooks that are executed during CI automatically have consecutive count.

    However, there is no interactive saving. Hence, add this count to the
    notebook files before executing them.

    Args:
        nb: Notebook content (`nbproject.dev._notebook.Notebook`).
    """
    count = 1

    for icell, cell in enumerate(nb.cells):
        if cell["cell_type"] != "code" or cell["source"] == []:
            continue

        nb.cells[icell]["execution_count"] = count
        count += 1


def _print_starting_cell(cell, cell_index):
    print(f"Starting cell {cell_index}, {cell}.", flush=True)


def execute_notebooks(
    nb_file_folder: Path, write: bool = True, print_cells: bool = False
):
    """Execute all notebooks in the folder.

    If `write` is `True`, will also add consecutive execution count numbers to
    make integrity check pass.

    Ignores .ipynb_checkpoints.

    Args:
        nb_file_folder: Path to folder with notebooks or a notebook to execute.
        write: If `True`, writes the execution results to the notebooks.
        print_cells: If `True`, prints cell indices and content
        on the start of the execution.
    """
    print(f"Executing notebooks in {nb_file_folder}", flush=True)

    t_execute_start = perf_counter()

    env = dict(os.environ)

    if nb_file_folder.is_file():
        if nb_file_folder.suffix != ".ipynb":
            print(f"{nb_file_folder} is not a notebook, ignoring", flush=True)
            return

        nb_folder = nb_file_folder.parent

        notebooks = [nb_file_folder]

    else:
        nb_folder = nb_file_folder

        # notebooks are part of documentation and indexed
        # by a sphinx myst index.md file
        # the order of execution matters!
        notebooks, names = _list_nbs_in_md(nb_folder, md_filename="index.md")
        for name in names:
            md_filename = nb_folder / f"{name}.md"
            if md_filename.exists():
                try:
                    notebooks_, _ = _list_nbs_in_md(nb_folder, md_filename=f"{name}.md")
                    notebooks += notebooks_
                except UnicodeDecodeError:
                    print(f"Ignoring {name}.md due to special characters", flush=True)
                    continue

        notebooks_unindexed = []
        for nb in nb_folder.glob("./*.ipynb"):
            if nb not in notebooks:
                notebooks_unindexed.append(nb)

        # also for unindexed notebooks the order matters!!!
        # we'll sort them with natsort so that they can be prefixed
        notebooks += natsorted(notebooks_unindexed)

    print(f"Scheduled: {[nb.stem for nb in notebooks]}", flush=True)

    os.chdir(nb_folder)

    for nb in notebooks:
        if ".ipynb_checkpoints/" in str(nb):
            continue

        t_start = perf_counter()

        nb_content = read_nb(nb, as_version=NO_CONVERT)

        if write:
            add_execution_count(nb_content)
            write_nb(nb_content, nb)

        client = NotebookClient(nb_content)

        if print_cells:
            client.on_cell_start = _print_starting_cell
        print(f"{nb.stem}", end=" ", flush=True)

        env["NBPRJ_TEST_NBPATH"] = str(nb)

        client.execute(env=env)

        if write:
            write_nb(nb_content, nb)

        t_stop = perf_counter()

        print(f"✓ ({(t_stop - t_start):.3f}s)", flush=True)

    total_time_elapsed = perf_counter() - t_execute_start
    print(
        f"Total time: {total_time_elapsed:.3f}s",
        flush=True,
    )
