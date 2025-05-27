from __future__ import annotations

import asyncio
import json
import json as _json
import logging
from pathlib import Path
from typing import Any, Dict, List

from browser_use.agent.service import Agent
from browser_use.agent.views import ActionResult, AgentHistoryList
from browser_use.browser.browser import Browser
from browser_use.browser.context import BrowserContext
from browser_use.controller.service import Controller
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, create_model

from workflow_use.controller.service import WorkflowController
from workflow_use.schema.views import (
	AgenticWorkflowStep,
	ClickStep,
	DeterministicWorkflowStep,
	InputStep,
	KeyPressStep,
	NavigationStep,
	ScrollStep,
	SelectChangeStep,
	WorkflowDefinitionSchema,
	WorkflowInputSchemaDefinition,
	WorkflowStep,
)
from workflow_use.workflow.prompts import WORKFLOW_FALLBACK_PROMPT_TEMPLATE, AGENTIC_STEP_PROMPT_TEMPLATE

logger = logging.getLogger(__name__)


class Workflow:
	"""Simple orchestrator that executes a list of workflow *steps* defined in a WorkflowDefinitionSchema."""

	def __init__(
		self,
		workflow_schema: WorkflowDefinitionSchema,
		*,
		controller: WorkflowController | None = None,
		browser: Browser | None = None,
		llm: BaseChatModel | None = None,
		fallback_to_agent: bool = True,
		fallback_controller: Controller | None = None,
	) -> None:
		"""Initialize a new Workflow instance from a schema object.

		Args:
			workflow_schema: The parsed workflow definition schema.
			controller: Optional WorkflowController instance to handle action execution
			browser: Optional Browser instance to use for browser automation
			llm: Optional language model for fallback agent functionality
			fallback_to_agent: Whether to fall back to agent-based execution on step failure

		Raises:
			ValueError: If the workflow schema is invalid (though Pydantic handles most).
		"""
		self.schema = workflow_schema  # Store the schema object

		self.name = self.schema.name
		self.description = self.schema.description
		self.version = self.schema.version
		self.steps = self.schema.steps

		self.controller = controller or WorkflowController()
		self.fallback_controller = fallback_controller or Controller()
		self.browser = browser or Browser()
		self.llm = llm
		self.fallback_to_agent = fallback_to_agent

		self.browser_context = BrowserContext(browser=self.browser, config=self.browser.config.new_context_config)

		self.context: dict[str, Any] = {}

		self.inputs_def: List[WorkflowInputSchemaDefinition] = self.schema.input_schema
		self._input_model: type[BaseModel] = self._build_input_model()
		self.failure_details: dict[int, str] = {}  # step_index -> failure_details

	# --- Loaders ---
	@classmethod
	def load_from_file(
		cls,
		file_path: str | Path,
		*,
		controller: WorkflowController | None = None,
		browser: Browser | None = None,
		llm: BaseChatModel | None = None,
	) -> Workflow:
		"""Load a workflow from a file."""
		with open(file_path, 'r') as f:
			data = _json.load(f)
		workflow_schema = WorkflowDefinitionSchema(**data)
		return Workflow(workflow_schema=workflow_schema, controller=controller, browser=browser, llm=llm)

	# --- Runners ---
	async def _run_deterministic_step(self, step: DeterministicWorkflowStep) -> ActionResult:
		"""Execute a deterministic (controller) action based on step dictionary."""
		# Assumes WorkflowStep for deterministic type has 'action' and 'params' keys
		action_name: str = step.type  # Expect 'action' key for deterministic steps
		params: Dict[str, Any] = step.model_dump()  # Use params if present

		ActionModel = self.controller.registry.create_action_model(include_actions=[action_name])
		# Pass the params dictionary directly
		action_model = ActionModel(**{action_name: params})

		try:
			return await self.controller.act(action_model, self.browser_context)
		except Exception as e:
			raise RuntimeError(f"Deterministic action '{action_name}' failed: {str(e)}")

	async def _run_agent_step(self, step: AgenticWorkflowStep) -> AgentHistoryList | dict[str, Any]:
		"""Spin-up an Agent based on step dictionary."""
		if self.llm is None:
			raise ValueError("An 'llm' instance must be supplied for agent-based steps")

		task: str = step.task
		max_steps: int = step.max_steps or 5

		agent = Agent(
			task=task,
			llm=self.llm,
			browser=self.browser,
			browser_context=self.browser_context,
			controller=self.fallback_controller,
			use_vision=True,  # Consider making this configurable via WorkflowStep schema
		)
		return await agent.run(max_steps=max_steps)

	def _get_workflow_overview(self, highlight_index: int | None = None) -> str:
		"""Get a string representation of the workflow."""
		workflow_overview_lines: list[str] = []
		for idx, step in enumerate(self.steps):
			desc = step.description or ""
			step_type_info = step.type
			details = step.model_dump()
			if highlight_index is not None and idx == highlight_index:
				workflow_overview_lines.append(
					f"  ** {idx + 1}. ({step_type_info}) {desc} ** - {details}"
				)
			else:
				workflow_overview_lines.append(
					f"  {idx + 1}. ({step_type_info}) {desc} - {details}"
				)
		return "\n".join(workflow_overview_lines)

	async def _fallback_to_agent(
		self,
		step_resolved: WorkflowStep,
		step_index: int,
		error: Exception | str | None = None,
	) -> AgentHistoryList | dict[str, Any]:
		"""Handle step failure by delegating to an agent."""
		if self.llm is None:
			raise ValueError("Cannot fall back to agent: An 'llm' instance must be supplied")
		print('Workflow steps:', step_resolved)
		# Extract details from the failed step dictionary
		failed_action_name = step_resolved.type
		failed_params = step_resolved.model_dump()
		step_description = step_resolved.description or "No description provided"
		error_msg = str(error) if error else "Unknown error"
		total_steps = len(self.steps)
		fail_details = (
			f"step={step_index + 1}/{total_steps}, action='{failed_action_name}', "
			f"description='{step_description}', params={str(failed_params)}, error='{error_msg}'"
		)
		self.failure_details[step_index] = fail_details
		
		# Determine the failed_value based on step type and attributes
		failed_value = None
		description_suffix = f"The purpose of this step is: {step_description}. " if step_description and step_description !="No description provided" else ""
		
		if isinstance(step_resolved, NavigationStep):
			failed_value = f"Navigate to URL: {step_resolved.url}. {description_suffix}"
		elif isinstance(step_resolved, ClickStep):
			# element_info = step_resolved.elementText or step_resolved.cssSelector
			# failed_value = f"{description_prefix}Click element: {element_info}"
			failed_value = f"Find and click element with description: {step_resolved.description}"
		elif isinstance(step_resolved, InputStep):
			failed_value = f"Input text: '{step_resolved.value}' into element. {description_suffix}"
		elif isinstance(step_resolved, SelectChangeStep):
			failed_value = f"Select option: '{step_resolved.selectedText}' in dropdown. {description_suffix}"
		elif isinstance(step_resolved, KeyPressStep):
			failed_value = f"Press key: '{step_resolved.key}'. {description_suffix}"
		elif isinstance(step_resolved, ScrollStep):
			failed_value = f"Scroll to position: (x={step_resolved.scrollX}, y={step_resolved.scrollY}). {description_suffix}"
		else:
			failed_value = f"No specific target value available for action '{failed_action_name}'. {description_suffix}"
		
		# Build workflow overview using the stored dictionaries
		workflow_overview = self._get_workflow_overview(highlight_index=step_index)
		print(workflow_overview)

		# Build the fallback task with the failed_value
		fallback_task = WORKFLOW_FALLBACK_PROMPT_TEMPLATE.format(
			step_index=step_index + 1,
			total_steps=len(self.steps),
			workflow_details=workflow_overview,
			action_type=failed_action_name,
			fail_details=fail_details,
			failed_value=failed_value,
			step_description=step_description
		)
		logger.info(f'Agent fallback task: {fallback_task}')

		# Prepare agent step config based on the failed step, adding task
		agent_step_config = AgenticWorkflowStep(
			type='agent',
			task=fallback_task,
			max_steps=5,
			output=None,
			description='Fallback agent to handle step failure',
		)

		return await self._run_agent_step(agent_step_config)

	def _validate_inputs(self, inputs: dict[str, Any]) -> None:
		"""Validate provided inputs against the workflow's input schema definition."""
		# If no inputs are defined in the schema, no validation needed
		if not self.inputs_def:
			return

		try:
			# Let Pydantic perform the heavy lifting – this covers both presence and
			# type validation based on the JSON schema model.
			self._input_model(**inputs)
		except Exception as e:
			raise ValueError(f'Invalid workflow inputs: {e}') from e

	def _resolve_placeholders(self, data: Any) -> Any:
		"""Recursively replace placeholders in *data* using current context variables.

		String placeholders are written using Python format syntax, e.g. "{index}".
		"""
		if isinstance(data, str):
			try:
				# Only attempt to format if placeholder syntax is likely present
				if '{' in data and '}' in data:
					formatted_data = data.format(**self.context)
					return formatted_data
				return data  # No placeholders, return as is
			except KeyError:
				# A key in the placeholder was not found in the context.
				# Return the original string as per previous behavior.
				return data

		# TODO: This next things are not really supported atm, we'll need to to do it in the future.
		elif isinstance(data, list):
			new_list = []
			changed = False
			for item in data:
				resolved_item = self._resolve_placeholders(item)
				if resolved_item is not item:
					changed = True
				new_list.append(resolved_item)
			return new_list if changed else data
		elif isinstance(data, dict):
			new_dict = {}
			changed = False
			for key, value in data.items():
				resolved_value = self._resolve_placeholders(value)
				if resolved_value is not value:
					changed = True
				new_dict[key] = resolved_value
			return new_dict if changed else data
		elif isinstance(data, BaseModel):  # Handle Pydantic models
			update_dict = {}
			model_changed = False
			for field_name in data.model_fields:  # Iterate using model_fields keys
				original_value = getattr(data, field_name)
				resolved_value = self._resolve_placeholders(original_value)
				if resolved_value is not original_value:
					model_changed = True
				update_dict[field_name] = resolved_value

			if model_changed:
				return data.model_copy(update=update_dict)
			else:
				return data  # Return original instance if no field's value changed
		else:
			# For any other types (int, float, bool, None, etc.), return as is
			return data

	def _store_output(self, step_cfg: WorkflowStep, result: Any) -> None:
		"""Store output into context based on 'output' key in step dictionary."""
		# Assumes WorkflowStep schema includes an optional 'output' field (string)
		output_key = step_cfg.output
		if not output_key:
			return

		# Helper to extract raw content we want to store

		value: Any = None

		if isinstance(result, ActionResult):
			# Prefer JSON in extracted_content if available
			content = result.extracted_content
			if content is None:
				value = {
					'success': result.success,
					'is_done': result.is_done,
				}
			else:
				try:
					value = json.loads(content)
				except Exception:
					value = content
		elif isinstance(result, AgentHistoryList):
			# Try to pull last ActionResult with extracted_content
			try:
				last_item = result.history[-1]
				last_action_result = next(
					(r for r in reversed(last_item.result) if r.extracted_content is not None),
					None,
				)
				if last_action_result and last_action_result.extracted_content:
					try:
						value = json.loads(last_action_result.extracted_content)
					except Exception:
						value = last_action_result.extracted_content
			except Exception:
				value = None
		else:
			value = str(result)

		self.context[output_key] = value

	async def _execute_step(self, step_index: int, step_resolved: WorkflowStep) -> Any:
		"""Execute the resolved step dictionary, handling type branching and fallback."""
		# Use 'type' field from the WorkflowStep dictionary
		result: Any | None = None

		if isinstance(step_resolved, DeterministicWorkflowStep):
			from browser_use.agent.views import ActionResult  # Local import ok

			try:
				# Use action key from step dictionary
				action_name = step_resolved.type or '[No action specified]'
				logger.info(f'Attempting deterministic action: {action_name}')
				result = await self._run_deterministic_step(step_resolved)
				if isinstance(result, ActionResult) and result.error:
					logger.warning(f'Deterministic action reported error: {result.error}')
					raise ValueError(f'Deterministic action {action_name} failed: {result.error}')
			except Exception as e:
				action_name = step_resolved.type or '[Unknown Action]'
				logger.warning(
					f'Deterministic step {step_index + 1} ({action_name}) failed: {e}. Attempting fallback with agent.'
				)
				if self.llm is None:
					raise ValueError('Cannot fall back to agent: LLM instance required.')
				if self.fallback_to_agent:
					result = await self._fallback_to_agent(step_resolved, step_index, e)
				else:
					raise ValueError(f'Deterministic step {step_index + 1} ({action_name}) failed: {e}')
		elif isinstance(step_resolved, AgenticWorkflowStep):
			# Use task key from step dictionary
			task_description = step_resolved.task
			logger.info(f'Running agent task: {task_description}')
			task_prompt = AGENTIC_STEP_PROMPT_TEMPLATE.format(
				task=task_description,
				workflow_details=self._get_workflow_overview(highlight_index=step_index),
				step_index=step_index + 1,
				total_steps=len(self.steps))
			step_resolved.task = task_prompt
			result = await self._run_agent_step(step_resolved)

		return result

	async def run_step(self, step_index: int, inputs: dict[str, Any] | None = None) -> Any:
		"""Run a *single* workflow step asynchronously and return its result.

		Parameters
		----------
		step_index:
				Zero-based index of the step to execute.
		inputs:
				Optional workflow-level inputs.  If provided on the first call they
				are validated and injected into :pyattr:`context`.  Subsequent
				calls can omit *inputs* as :pyattr:`context` is already populated.
		"""
		if not (0 <= step_index < len(self.steps)):
			raise IndexError(f'step_index {step_index} is out of range for workflow with {len(self.steps)} steps')

		# Initialise/augment context once with the provided inputs
		if inputs is not None or not self.context:
			runtime_inputs = inputs or {}
			self._validate_inputs(runtime_inputs)
			# If context is empty we assume this is the first invocation – start fresh;
			# otherwise merge new inputs on top (explicitly overriding duplicates)
			if not self.context:
				self.context = runtime_inputs.copy()
			else:
				self.context.update(runtime_inputs)

		async with self.browser_context:
			raw_step_cfg = self.steps[step_index]
			step_resolved = self._resolve_placeholders(raw_step_cfg)
			result = await self._execute_step(step_index, step_resolved)
			# Persist outputs (if declared) for future steps
			self._store_output(step_resolved, result)
			await asyncio.sleep(5)  # Keep browser open for 5 seconds
		# Each invocation opens a new browser context – we close the browser to
		# release resources right away.  This keeps the single-step API
		# self-contained.
		# await self.browser.close() # <-- Commented out for testing
		return result

	async def run(self, inputs: dict[str, Any] | None = None, close_browser_at_end: bool = True) -> List[Any]:
		"""Execute the workflow asynchronously using step dictionaries.

		@dev This is the main entry point for the workflow.
		"""
		runtime_inputs = inputs or {}
		# 1. Validate inputs against definition
		self._validate_inputs(runtime_inputs)
		# 2. Initialize context with validated inputs
		self.context = runtime_inputs.copy()  # Start with a fresh context

		results: List[Any] = []

		await self.browser_context.__aenter__()
		try:
			for step_index, step_dict in enumerate(self.steps):  # self.steps now holds dictionaries
				await asyncio.sleep(0.1)

				# Use description from the step dictionary
				step_description = step_dict.description or 'No description provided'
				logger.info(f'--- Running Step {step_index + 1}/{len(self.steps)} -- {step_description} ---')
				# Resolve placeholders using the current context (works on the dictionary)
				step_resolved = self._resolve_placeholders(step_dict)

				# Execute step using the unified _execute_step method
				result = await self._execute_step(step_index, step_resolved)

				results.append(result)
				# Persist outputs using the resolved step dictionary
				self._store_output(step_resolved, result)
				logger.info(f'--- Finished Step {step_index + 1} ---\n')
		finally:
			if close_browser_at_end:
				# Ensure __aexit__ is called with appropriate args for exception handling if needed
				# For simplicity, assuming no exception to pass: exc_type, exc_val, exc_tb = None, None, None
				# wait 3 seconds before closing the browser
				await asyncio.sleep(3)
				await self.browser_context.__aexit__(None, None, None)

		# Clean-up browser after finishing workflow
		if close_browser_at_end:
			await self.browser.close()

		return results

	# ------------------------------------------------------------------
	# LangChain tool wrapper
	# ------------------------------------------------------------------

	def _build_input_model(self) -> type[BaseModel]:
		"""Return a *pydantic* model matching the workflow's ``input_schema`` section."""
		if not self.inputs_def:
			# No declared inputs -> generate an empty model
			# Use schema name for uniqueness, fallback if needed
			model_name = f'{(self.schema.name or "Workflow").replace(" ", "_")}_NoInputs'
			return create_model(model_name)

		type_mapping = {
			'string': str,
			'number': float,
			'bool': bool,  # Added boolean type
		}
		fields: Dict[str, tuple[type, Any]] = {}
		for input_def in self.inputs_def:
			name = input_def.name
			type_str = input_def.type
			py_type = type_mapping.get(type_str)
			if py_type is None:
				raise ValueError(f'Unsupported input type: {type_str!r} for field {name!r}')
			# Pydantic's create_model uses ... (Ellipsis) to mark required fields
			default = ... if input_def.required else None
			fields[name] = (py_type, default)

		from typing import cast as _cast

		# The raw ``create_model`` helper from Pydantic deliberately uses *dynamic*
		# signatures, which the static type checker cannot easily verify.  We cast
		# the **fields** mapping to **Any** to silence these warnings.
		return create_model(  # type: ignore[arg-type]
			f'{(self.schema.name or "Workflow").replace(" ", "_")}_Inputs',
			**_cast(Dict[str, Any], fields),
		)

	def as_tool(self, *, name: str | None = None, description: str | None = None):  # noqa: D401
		"""Expose the entire workflow as a LangChain *StructuredTool* instance.

		The generated tool validates its arguments against the workflow's input
		schema (if present) and then returns the JSON-serialised output of
		:py:meth:`run`.
		"""

		InputModel = self._build_input_model()
		# Use schema name as default, sanitize for tool name requirements
		default_name = ''.join(c if c.isalnum() else '_' for c in self.name)
		tool_name = name or default_name[:50]
		doc = description or self.description  # Use schema description

		# `self` is closed over via the inner function so we can keep state.
		async def _invoke(**kwargs):  # type: ignore[override]
			logger.info(f'Running workflow as tool with inputs: {kwargs}')
			augmented_inputs = kwargs.copy() if kwargs else {}
			for input_def in self.inputs_def:
				if not input_def.required and input_def.name not in augmented_inputs:
					augmented_inputs[input_def.name] = ''
			result = await self.run(inputs=augmented_inputs)
			# Serialise non-string output so models that expect a string tool
			# response still work.
			try:
				return _json.dumps(result, default=str)
			except Exception:
				return str(result)

		return StructuredTool.from_function(
			coroutine=_invoke,
			name=tool_name,
			description=doc,
			args_schema=InputModel,
		)

	async def run_as_tool(self, prompt: str) -> str:
		"""
		Run the workflow with a prompt and automatically parse the required variables.

		@dev Uses AgentExecutor to properly handle the tool invocation loop.
		"""

		# For now I kept it simple but one could think of using a react agent here.
		if self.llm is None:
			raise ValueError("Cannot run as tool: An 'llm' instance must be supplied for tool-based steps")

		prompt_template = ChatPromptTemplate.from_messages(
			[
				('system', 'You are a helpful assistant'),
				('human', '{input}'),
				# Placeholders fill up a **list** of messages
				('placeholder', '{agent_scratchpad}'),
			]
		)

		# Create the workflow tool
		workflow_tool = self.as_tool()
		agent = create_tool_calling_agent(self.llm, [workflow_tool], prompt_template)
		agent_executor = AgentExecutor(agent=agent, tools=[workflow_tool])
		result = await agent_executor.ainvoke({'input': prompt})
		return result['output']
