import json as _json
from inspect import Parameter, Signature
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
		with the FastMCP instance by dynamically setting function signatures.
		"""
		workflow_files = list(Path(self.workflow_dir).glob('*.workflow.json'))
		print(f"[FastMCP Service] Found workflow files in '{self.workflow_dir}': {len(workflow_files)}")

		for wf_file_path in workflow_files:
			try:
				print(f'[FastMCP Service] Loading workflow from: {wf_file_path}')
				schema = WorkflowDefinitionSchema.load_from_json(str(wf_file_path))

				# Instantiate the workflow
				workflow = Workflow(workflow_schema=schema, llm=llm_instance, browser=None, controller=None)

				params_for_signature = []
				annotations_for_runner = {}

				if hasattr(workflow._input_model, 'model_fields'):
					for field_name, model_field in workflow._input_model.model_fields.items():
						param_annotation = model_field.annotation if model_field.annotation is not None else Any

						param_default = Parameter.empty
						if not model_field.is_required():
							param_default = model_field.default if model_field.default is not None else None

						params_for_signature.append(
							Parameter(
								name=field_name,
								kind=Parameter.POSITIONAL_OR_KEYWORD,
								default=param_default,
								annotation=param_annotation,
							)
						)
						annotations_for_runner[field_name] = param_annotation

				dynamic_signature = Signature(params_for_signature)

				# Sanitize workflow name for the function name
				safe_workflow_name_for_func = ''.join(c if c.isalnum() else '_' for c in schema.name)
				dynamic_func_name = f'tool_runner_{safe_workflow_name_for_func}_{schema.version.replace(".", "_")}'

				# Define the actual function that will be called by FastMCP
				# It uses a closure to capture the specific 'workflow' instance
				def create_runner(wf_instance: Workflow):
					async def actual_workflow_runner(**kwargs):
						# kwargs will be populated by FastMCP based on the dynamic_signature
						raw_result = await wf_instance.run(inputs=kwargs)
						try:
							return _json.dumps(raw_result, default=str)
						except Exception:
							return str(raw_result)

					return actual_workflow_runner

				runner_func_impl = create_runner(workflow)

				# Set the dunder attributes that FastMCP will inspect
				runner_func_impl.__name__ = dynamic_func_name
				runner_func_impl.__doc__ = schema.description
				runner_func_impl.__signature__ = dynamic_signature
				runner_func_impl.__annotations__ = annotations_for_runner

				# Tool name and description for FastMCP registration
				unique_tool_name = f'{schema.name.replace(" ", "_")}_{schema.version}'
				tool_description = schema.description

				tool_decorator = mcp_app.tool(name=unique_tool_name, description=tool_description)
				tool_decorator(runner_func_impl)

				param_names_for_log = list(dynamic_signature.parameters.keys())
				print(
					f"[FastMCP Service] Registered tool (via signature): '{unique_tool_name}' for '{schema.name}'. Params: {param_names_for_log}"
				)

			except Exception as e:
				print(f'[FastMCP Service] Failed to load or register workflow from {wf_file_path}: {e}')
				import traceback

				traceback.print_exc()
