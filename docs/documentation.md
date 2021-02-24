# Update documentation

To rebuild the documentation, install several packages:
```
pip install -r docs/requirements.txt
```
And then run:
```
sphinx-build -b html docs docs/build/html
```
This can take a long time because it executes many of the notebooks in the documentation source;
if you'd prefer to build the docs without exeuting the notebooks, you can run:
```
sphinx-build -b html -D jupyter_execute_notebooks=off docs docs/build/html
```
You can then see the generated documentation in `docs/build/html/index.html`.

## Update notebooks

We use [jupytext](https://jupytext.readthedocs.io/) to maintain two synced copies of the notebooks
in `docs/notebooks`: one in `ipynb` format, and one in `md` format. The advantage of the former
is that it can be opened and executed directly in Colab; the advantage of the latter is that
it makes it much easier to track diffs within version control.

### Editing ipynb

For making large changes that substantially modify code and outputs, it is easiest to
edit the notebooks in Jupyter or in Colab. To edit notebooks in the Colab interface,
open <http://colab.research.google.com> and `Upload` from your local repo.
Update it as needed, `Run all cells` then `Download ipynb`.
You may want to test that it executes properly, using `sphinx-build` as explained above.

### Editing md

For making smaller changes to the text content of the notebooks, it is easiest to edit the
`.md` versions using a text editor.

### Syncing notebooks

After editing either the ipynb or md versions of the notebooks, you can sync the two versions
using [jupytext](https://jupytext.readthedocs.io/) by running:

```
$ jupytext --sync docs/notebooks/*
```

Alternatively, you can run this command via the [pre-commit](https://pre-commit.com/)
framework by executing the folloing in the main JAX directory:

```
$ pre-commit run --all
```

See the pre-commit framework documentation for information on how to set your local git
environment to execute this automatically.