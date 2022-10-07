import os
from pathlib import Path

from nbclient import NotebookClient
from nbformat import NO_CONVERT
from nbformat import read as read_nb
from nbformat import write as write_nb


def _list_nbs_in_md(nb_folder, md_filename="index.md"):
    notebooks = []
    names = []

    index_path = nb_folder / md_filename
    if index_path.exists():
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


def pre_process_folder(nb_folder):
    # Test whether prefix of a notebook is a capital letter or a digit and if so,
    # strip them for pretty & persistent URLs.

    # We need the prefixes on notebooks to allow users to navigate downloaded
    # notebooks that should display in order in a file browser.

    notebook_paths = [path for path in nb_folder.glob("*") if path.suffix == ".ipynb"]

    for path in notebook_paths:
        prefix = path.stem[0]
        if prefix.isdigit() or prefix.isupper() and "-" in path.stem:
            new_stem = "-".join(path.stem.split("-")[1:])
            # path.with_stem() is >3.9
            new_path = path.with_name(f"{new_stem}{path.suffix}")
            path.rename(new_path)
            print(f"renaming {path} -> {new_path}")


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


def execute_notebooks(nb_file_folder: Path, write: bool = True):
    """Execute all notebooks in the folder.

    If `write` is `True`, will also add consecutive execution count numbers to
    make integrity check pass.

    Ignores .ipynb_checkpoints.

    Args:
        nb_file_folder: Path to folder with notebooks or a notebook to execute.
        write: If `True`, write the execution results to the notebooks.
    """
    env = dict(os.environ)

    if nb_file_folder.is_file():
        if nb_file_folder.suffix != ".ipynb":
            print(f"The file {nb_file_folder} is not a notebook, ignoring.")
            return

        nb_folder = nb_file_folder.parent

        notebooks = [nb_file_folder]

    else:
        nb_folder = nb_file_folder

        pre_process_folder(nb_folder)

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
                    print(f"Ignoring {name}.md due to special characters.")
                    continue

        for nb in nb_folder.glob("./*.ipynb"):
            if nb not in notebooks:
                notebooks.append(nb)

    os.chdir(nb_folder)

    for nb in notebooks:
        if ".ipynb_checkpoints/" in str(nb):
            continue
        nb_name = str(nb.relative_to(nb_folder))
        print(f"{nb_name}")

        nb_content = read_nb(nb, as_version=NO_CONVERT)

        if write:
            add_execution_count(nb_content)
            write_nb(nb_content, nb)

        client = NotebookClient(nb_content)

        env["NBPRJ_TEST_NBPATH"] = str(nb)

        client.execute(env=env)

        if write:
            write_nb(nb_content, nb)
