import json as _json
from pathlib import Path
from typing import Any

from fastmcp import FastMCP
from langchain_core.language_models.chat_models import BaseChatModel  # For type hinting

from workflow_use.schema.views import WorkflowDefinitionSchema
from workflow_use.workflow.service import Workflow


class WorkflowMCPService:
	def __init__(
		self,
		name: str = 'WorkflowService',
		description: str = 'Exposes workflows as MCP tools.',
		workflow_dir: str = './tmp',
	):
		self.name = name
		self.description = description
		self.workflow_dir = workflow_dir

	def get_mcp_server(self, llm_instance: BaseChatModel):
		mcp_app = FastMCP(name=self.name, description=self.description)

		self._setup_workflow_tools(mcp_app, llm_instance)

		return mcp_app

	def _setup_workflow_tools(self, mcp_app: FastMCP, llm_instance: BaseChatModel):
		"""
		Scans a directory for workflow.json files, loads them, and registers them as tools
		with the FastMCP instance using dynamically generated functions via exec.
		"""
		workflow_files = list(Path(self.workflow_dir).glob('*.workflow.json'))
		print(f"[FastMCP Service] Found workflow files in '{self.workflow_dir}': {len(workflow_files)}")

		for wf_file_path in workflow_files:
			try:
				print(f'[FastMCP Service] Loading workflow from: {wf_file_path}')
				schema = WorkflowDefinitionSchema.load_from_json(str(wf_file_path))

				workflow = Workflow(workflow_schema=schema, llm=llm_instance, browser=None, controller=None)

				param_def_strings = []  # e.g., ["first_name: str", "age: int = None"]
				param_names = []  # e.g., ["first_name", "age"]
				exec_context_types = {'Any': Any, '_json_serializer': _json, 'workflow_obj': workflow}

				if hasattr(workflow._input_model, 'model_fields'):
					for field_name, model_field in workflow._input_model.model_fields.items():
						param_names.append(field_name)

						# Get type hint string (e.g., "str", "int", "Any")
						type_hint_str = 'Any'  # Default to Any
						if model_field.annotation is not None:
							if hasattr(model_field.annotation, '__name__'):
								type_hint_str = model_field.annotation.__name__
							elif (
								hasattr(model_field.annotation, '_name') and model_field.annotation._name
							):  # For things like List, Dict
								type_hint_str = str(model_field.annotation).replace('typing.', '')  # Get a string representation
							else:
								# Fallback for more complex types, might need specific handling
								type_hint_str = str(model_field.annotation).replace('typing.', '')

						# Add type to exec context if not already basic or Any
						if model_field.annotation is not Any and model_field.annotation is not None:
							exec_context_types[type_hint_str.split('[')[0]] = model_field.annotation  # Corrected string split

						param_def_str = f'{field_name}: {type_hint_str}'

						if not model_field.is_required():
							default_val = model_field.default
							if isinstance(default_val, str):
								param_def_str += f" = '{default_val}'"  # escape quotes in default_val if necessary
							else:
								param_def_str += f' = {default_val}'
						param_def_strings.append(param_def_str)

				func_signature_params_str = ', '.join(param_def_strings)
				safe_workflow_name = ''.join(c if c.isalnum() else '_' for c in schema.name)
				dynamic_func_name = f'tool_runner_{safe_workflow_name}_{schema.version.replace(".", "_")}'

				inputs_dict_parts = [f"'{name}': {name}" for name in param_names]
				inputs_dict_str = '{' + ', '.join(inputs_dict_parts) + '}'

				func_def_str = f"""
async def {dynamic_func_name}({func_signature_params_str}):
    # This function is dynamically created by exec.
    # 'workflow_obj' and '_json_serializer' are injected from the exec_context.
    inputs_for_run = {inputs_dict_str}
    raw_result = await workflow_obj.run(inputs=inputs_for_run)
    try:
        return _json_serializer.dumps(raw_result, default=str)
    except Exception:
        return str(raw_result)
"""
				# print(f"--- Generated function for {dynamic_func_name} ---")
				# print(func_def_str)
				# print(f"--- Exec context types: {exec_context_types.keys()} ---")

				# Execute the function definition
				exec(func_def_str, exec_context_types)
				runner_func_impl = exec_context_types[dynamic_func_name]

				# Set the docstring for the tool
				runner_func_impl.__doc__ = schema.description

				unique_tool_name = f'{schema.name.replace(" ", "_")}_{schema.version}'
				tool_description = schema.description

				tool_decorator = mcp_app.tool(name=unique_tool_name, description=tool_description)
				tool_decorator(runner_func_impl)

				actual_params = (
					list(runner_func_impl.__annotations__.keys()) if hasattr(runner_func_impl, '__annotations__') else 'N/A'
				)
				print(
					f"[FastMCP Service] Registered tool (via exec): '{unique_tool_name}' for '{schema.name}'. Params: {actual_params}"
				)

			except Exception as e:
				print(f'[FastMCP Service] Failed to load or register workflow from {wf_file_path}: {e}')
				import traceback

				traceback.print_exc()
