from pathlib import Path

from nbproject_test import execute_notebooks

nb_folder = Path(__file__).parent / "notebooks"


def test_execute_folder():
    execute_notebooks(nb_folder, write=False)


def test_execute_file():
    execute_notebooks(nb_folder / "test.ipynb", write=False, print_cells=True)
