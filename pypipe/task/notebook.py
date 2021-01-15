from pypipe.core.task import Task
#from .config import parse_config

from pathlib import Path
import inspect
import importlib
import subprocess
import re

import warnings
try:
    from jubox import JupyterNotebook, CodeCell
    from jubox import run_notebook
except ImportError as exc:
    warnings.warn(f"Jubox functionalities not found: '{exc}'", ImportWarning)

class JupyterTask(Task):
    """Task that executes a Jupyter Notebook
    """

    parameter_tag = "parameter"

    def __init__(self, *args, on_preprocess=None, param_names=None, clear_outputs=True, **kwargs):
        self.on_preprocess = on_preprocess
        self.param_names = [] if param_names is None else param_names
        super().__init__(*args, **kwargs)
        self.clear_outputs = clear_outputs

    def filter_params(self, params):
        return params

    def execute_action(self, **parameters):
        nb = self.notebook
        self.process_preprocess(nb, parameters)


        nb = run_notebook(
            notebook=nb,
            # Note, we do not pass the methods 
            # (process_finish, process_success etc.)
            # to prevent double call
            on_finally=self.on_finish,
            on_success=self.on_success,
            on_failure=self.on_failure,
            # parameters=kwargs, # Parameters are set elsewhere
            clear_outputs=self.clear_outputs,
            parameter_tag=self.parameter_tag
        )

    def process_preprocess(self, nb, parameters):
        self.set_params(nb, parameters)
        if self.on_preprocess is not None:
            self.on_preprocess(nb, **kwargs)

    def set_params(self, nb, parameters):
        # TODO:
        #   An option to set arbitrary parameters using picke
        #       1. write the parameter(s) to a pickle file
        #       2. manipulate param cell in a way that it reads
        #          these parameters
        #       3. Run the notebook
        #       4. Possibly clear the pickle files
        try:
            param_cell = nb.cells.get(tags=[self.parameter_tag])[0]
        except IndexError:
            return
        param_code = parameters.extract_as_code()
        cell = CodeCell(param_code)
        cell.insert(0, "# This is autogenerated parameter cell\n")

        param_cell.overwrite(cell)

    def process_failure(self, exception):
        # on_failure is called already
        pass
    
    def process_success(self, output):
        # on_success is called already
        pass

    def process_finish(self, status):
        # on_finish is called already
        # Deleting the notebook so next time the file is refetched
        del self.notebook

    def get_default_name(self):
        return self.action

    @property
    def notebook(self):
        if not hasattr(self, "_notebook"):
            self._notebook = JupyterNotebook(self.action)
        return self._notebook

    @notebook.deleter
    def notebook(self):
        del self._notebook

    @classmethod
    def from_file(cls, path):

        obj = cls(action=path, **parse_config(path))
        return obj
        
    @classmethod
    def from_folder(cls, path, glob=None, name_func=None, **kwargs):
        """get all tasks from folder
        
        Example:
            path structure:
                | my_notebooks/
                |____ do_report.ipynb
                |____ do_analysis.ipynb
                
            JupyterTask.from_folder("my_notebooks")
            >>> [Task(name="do_report", ...), Task(name="do_analysis", ...)]
        """
        root = Path(path)

        glob = glob or "*.ipynb"
        name_func = (
            (lambda relative_path: tuple(part.replace('.ipynb', '') for part in relative_path.parts)) 
            if name_func is None else name_func
        )

        tasks = []
        for file in root.glob(glob):

            kwargs.update(cls._get_conf_from_file(file))
            task_name = name_func(Path(*file.parts[len(root.parts):]))
            tasks.append(cls(action=file, name=task_name, **kwargs))
        return tasks

    @staticmethod
    def _get_conf_from_file(path):
        nb = JupyterNotebook(path)
        cond_cell = nb.cells.get(tags=["conditions"])[0]
        src = cond_cell.source

        conds = {
        }
        exec(src, conds)
        start_condition = conds.pop("start_condition", None)
        end_condition = conds.pop("end_condition", None)
        run_condition = conds.pop("run_condition", None)
        dependent = conds.pop("dependent", None)
        execution = conds.pop("execution", None)

        return {
            "start_cond": start_condition,
            "end_cond": end_condition,
            "run_cond": run_condition,
            "dependent": dependent,
            "execution": execution,
        }


    def _get_config(self, path):
        # TODO
        notebook = JupyterNotebook(path)
        conf_cell = notebook.cells.get(tags=["taskconf"])
        conf_string = conf_cell.source
        conf_string

    @property
    def pos_args(self):
        return []

    @property
    def kw_args(self):
        nb = self.notebook
        src_param_cell = nb.cells.get(tags=["parameter"])
        if not src_param_cell:
            return []
        src_param_cell = src_param_cell[0].source

        kw_args = []
        for line in src_param_cell.split("\n"):
            var = re.search(r"^([a-zA-Z_]+[0-9a-zA-Z_]*)(?=$| *=)", line)
            if var:
                kw_args.append(var.group())
        return kw_args

        