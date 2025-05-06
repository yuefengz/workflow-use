from __future__ import annotations

import asyncio
import json
import json as _json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from browser_use.agent.service import Agent
from browser_use.agent.views import ActionResult, AgentHistoryList
from browser_use.browser.browser import Browser
from browser_use.browser.context import BrowserContext
from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.language_models.chat_models import BaseChatModel
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.tools import StructuredTool
from pydantic import BaseModel, create_model

from src.schema.views import (
    WorkflowDefinitionSchema,
    WorkflowStep,
    WorkflowInputSchemaDefinition,
)

from src.workflow.prompts import WORKFLOW_FALLBACK_PROMPT_TEMPLATE
from src.controller.service import WorkflowController

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

        self.controller = controller or WorkflowController()
        self.browser = browser or Browser()
        self.llm = llm
        self.fallback_to_agent = fallback_to_agent

        self.browser_context = BrowserContext(
            browser=self.browser, config=self.browser.config.new_context_config
        )

        self.context: dict[str, Any] = {}

        self.steps: List[Dict[str, Any]] = self._load_steps_from_schema()
        self.inputs_def: Dict[str, Any] = (
            self.schema.input_schema.model_dump() if self.schema.input_schema else {}
        )
        self._input_model: type[BaseModel] = self._build_input_model()

    # ---------------------------------------------------------------------
    # Unified config loader (JSON workflow or raw event log) -> Now from Schema
    # ---------------------------------------------------------------------

    def _load_steps_from_schema(self) -> List[Dict[str, Any]]:
        """Convert WorkflowStep models from the schema into dictionaries for internal use."""

        steps_dict_list: List[Dict[str, Any]] = []
        for step_model in self.schema.steps:  # step_model is WorkflowStep
            # Convert the WorkflowStep Pydantic model to a dictionary
            # Use exclude_none=True to avoid adding keys with None values if not needed
            step_dict = step_model.model_dump(exclude_none=True)

            # Ensure essential keys potentially used downstream exist, even if None/empty,
            # if they aren't guaranteed by the model dump and schema
            step_dict.setdefault(
                "type", "deterministic"
            )  # Default type if not specified
            step_dict.setdefault("description", f"Step {len(steps_dict_list) + 1}")
            step_dict.setdefault("params", {})

            # Scrub screenshot if present (assuming it's not needed for execution)
            if "screenshot" in step_dict:
                step_dict["screenshot"] = ""

            steps_dict_list.append(step_dict)
        return steps_dict_list

    async def _run_deterministic_step(self, step: Dict[str, Any]) -> ActionResult:
        """Execute a deterministic (controller) action based on step dictionary."""
        # Assumes WorkflowStep for deterministic type has 'action' and 'params' keys
        action_name: str = step["action"]  # Expect 'action' key for deterministic steps
        params: Dict[str, Any] = step.get("params", {})  # Use params if present

        ActionModel = self.controller.registry.create_action_model(
            include_actions=[action_name]
        )
        # Pass the params dictionary directly
        action_model = ActionModel(**{action_name: params})

        try:
            return await self.controller.act(action_model, self.browser_context)
        except Exception as e:
            raise RuntimeError(f"Deterministic action '{action_name}' failed: {str(e)}")

    async def _run_agent_step(
        self, step: Dict[str, Any]
    ) -> AgentHistoryList | dict[str, Any]:
        """Spin-up an Agent based on step dictionary."""
        if self.llm is None:
            raise ValueError("An 'llm' instance must be supplied for agent-based steps")

        # Assumes WorkflowStep for agent type has 'task' and optional 'max_steps'
        task: str = step["task"]  # Expect 'task' key for agent steps
        max_steps: int = step.get("max_steps", 5)  # Use max_steps if present

        agent = Agent(
            task=task,
            llm=self.llm,
            browser=self.browser,
            browser_context=self.browser_context,
            controller=self.controller,
            use_vision=True,  # Consider making this configurable via WorkflowStep schema
        )
        return await agent.run(max_steps=max_steps)

    async def _fallback_to_agent(
        self,
        step_resolved: Dict[str, Any],
        step_index: int,
        error: Exception | str | None = None,
    ) -> AgentHistoryList | dict[str, Any]:
        """Handle step failure by delegating to an agent."""
        if self.llm is None:
            raise ValueError(
                "Cannot fall back to agent: An 'llm' instance must be supplied"
            )

        # Extract details from the failed step dictionary
        failed_action_name = step_resolved.get("action", "unknown_action")
        failed_params = step_resolved.get("params", {})
        step_description = step_resolved.get("description", "No description provided")
        error_msg = str(error) if error else "Unknown error"
        total_steps = len(self.steps)
        fail_details = (
            f"step={step_index + 1}/{total_steps}, action='{failed_action_name}', description='{step_description}', "
            f"params={str(failed_params)}, error='{error_msg}'"
        )

        # Build workflow overview using the stored dictionaries
        workflow_overview_lines: list[str] = []
        for i, st_dict in enumerate(self.steps):
            # Use description, fallback to task/action/type
            desc = (
                st_dict.get("description")
                or st_dict.get("task")
                or st_dict.get("action")
                or st_dict.get("type", "Unknown Type")
            )
            step_type_info = st_dict.get("type", "deterministic")
            details = st_dict.get("action") or st_dict.get("task")
            workflow_overview_lines.append(
                f"  {i + 1}. ({step_type_info}) {desc} - {details}"
            )
        workflow_overview = "\n".join(workflow_overview_lines)

        fallback_task = WORKFLOW_FALLBACK_PROMPT_TEMPLATE.format(
            step_index=step_index + 1,
            total_steps=len(self.steps),
            workflow_details=workflow_overview,
            fail_details=fail_details,
        )
        logger.info(f"Agent fallback task: {fallback_task}")

        # Prepare agent step config based on the failed step, adding task
        agent_step_config = step_resolved.copy()
        agent_step_config["type"] = "agent"
        agent_step_config["task"] = fallback_task
        agent_step_config.setdefault("max_steps", 5)  # Add default max_steps if missing

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
            raise ValueError(f"Invalid workflow inputs: {e}") from e

    def _resolve_placeholders(self, data: Any) -> Any:
        """Recursively replace placeholders in *data* using current context variables.

        String placeholders are written using Python format syntax, e.g. "{index}".
        """

        if isinstance(data, str):
            try:
                return data.format(**self.context)
            except KeyError:
                # variable not yet available – leave as-is
                return data
        elif isinstance(data, dict):
            return {k: self._resolve_placeholders(v) for k, v in data.items()}
        elif isinstance(data, list):
            return [self._resolve_placeholders(v) for v in data]
        else:
            return data

    def _store_output(self, step_cfg: Dict[str, Any], result: Any) -> None:
        """Store output into context based on 'output' key in step dictionary."""
        # Assumes WorkflowStep schema includes an optional 'output' field (string)
        output_key = step_cfg.get("output")
        if not output_key:
            return

        # Helper to extract raw content we want to store

        value: Any = None

        if isinstance(result, ActionResult):
            # Prefer JSON in extracted_content if available
            content = result.extracted_content
            if content is None:
                value = {
                    "success": result.success,
                    "is_done": result.is_done,
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
                    (
                        r
                        for r in reversed(last_item.result)
                        if r.extracted_content is not None
                    ),
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

    async def _execute_step(
        self, step_index: int, step_resolved: Dict[str, Any]
    ) -> Any:
        """Execute the resolved step dictionary, handling type branching and fallback."""
        # Use 'type' field from the WorkflowStep dictionary
        step_type = step_resolved.get("type", "deterministic").lower()
        result: Any | None = None

        if step_type == "deterministic":
            from browser_use.agent.views import ActionResult  # Local import ok

            try:
                # Use action key from step dictionary
                action_name = step_resolved.get("action", "[No action specified]")
                logger.info(f"Attempting deterministic action: {action_name}")
                result = await self._run_deterministic_step(step_resolved)
                if isinstance(result, ActionResult) and result.error:
                    logger.warning(
                        f"Deterministic action reported error: {result.error}"
                    )
                    raise ValueError(
                        f"Deterministic action {action_name} failed: {result.error}"
                    )
            except Exception as e:
                action_name = step_resolved.get("action", "[Unknown Action]")
                logger.warning(
                    f"Deterministic step {step_index + 1} ({action_name}) failed: {e}. "
                    "Attempting fallback with agent."
                )
                if self.llm is None:
                    raise ValueError(
                        "Cannot fall back to agent: LLM instance required."
                    )
                if self.fallback_to_agent:
                    result = await self._fallback_to_agent(step_resolved, step_index, e)
                else:
                    raise ValueError(
                        f"Deterministic step {step_index + 1} ({action_name}) failed: {e}"
                    )
        elif step_type == "agent":
            # Use task key from step dictionary
            task_description = step_resolved.get("task", "[No task specified]")
            logger.info(f"Running agent task: {task_description}")
            result = await self._run_agent_step(step_resolved)
        else:
            raise ValueError(f"Unknown step type in step {step_index + 1}: {step_type}")

        return result

    async def run_step_async(
        self, step_index: int, inputs: dict[str, Any] | None = None
    ) -> Any:
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
            raise IndexError(
                f"step_index {step_index} is out of range for workflow with {len(self.steps)} steps"
            )

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
        # Each invocation opens a new browser context – we close the browser to
        # release resources right away.  This keeps the single-step API
        # self-contained.
        await self.browser.close()
        return result

    async def run_async(self, inputs: dict[str, Any] | None = None) -> List[Any]:
        """Execute the workflow asynchronously using step dictionaries."""
        runtime_inputs = inputs or {}
        # 1. Validate inputs against definition
        self._validate_inputs(runtime_inputs)
        # 2. Initialize context with validated inputs
        self.context = runtime_inputs.copy()  # Start with a fresh context

        results: List[Any] = []

        async with self.browser_context:
            for step_index, step_dict in enumerate(
                self.steps
            ):  # self.steps now holds dictionaries
                # Use description from the step dictionary
                step_description = step_dict.get(
                    "description", "No description provided"
                )
                logger.info(
                    f"--- Running Step {step_index + 1}/{len(self.steps)} -- {step_description} ---"
                )
                # Resolve placeholders using the current context (works on the dictionary)
                step_resolved = self._resolve_placeholders(step_dict)

                # Execute step using the unified _execute_step method
                result = await self._execute_step(step_index, step_resolved)

                results.append(result)
                # Persist outputs using the resolved step dictionary
                self._store_output(step_resolved, result)
                logger.info(f"--- Finished Step {step_index + 1} ---")

        # Clean-up browser after finishing workflow
        await self.browser.close()
        return results

    # Convenience synchronous wrapper ------------------------------------------------
    def run(self, inputs: dict[str, Any] | None = None) -> List[Any]:
        """Synchronously execute :py:meth:`run_async` with ``asyncio.run``.

        Args:
                inputs: Dictionary of input values required by the workflow (defined in JSON).
        """
        return asyncio.run(self.run_async(inputs=inputs))

    # Convenience wrapper to execute a single step synchronously -----------------
    def run_step(self, step_index: int, inputs: dict[str, Any] | None = None) -> Any:
        """Synchronously execute :py:meth:`run_step_async` for *step_index*."""
        return asyncio.run(self.run_step_async(step_index, inputs=inputs))

    # ------------------------------------------------------------------
    # LangChain tool wrapper
    # ------------------------------------------------------------------

    def _build_input_model(self) -> type[BaseModel]:
        """Return a *pydantic* model matching the workflow's ``input_schema`` section."""
        if not self.inputs_def or not self.inputs_def.get("properties"):
            # No declared inputs or no properties defined -> generate an empty model
            # Use schema name for uniqueness, fallback if needed
            model_name = (
                f"{(self.schema.name or 'Workflow').replace(' ', '_')}_NoInputs"
            )
            return create_model(model_name)  # type: ignore[call-arg]

        props = self.inputs_def.get("properties", {})
        required = set(self.inputs_def.get("required", []))

        type_mapping = {
            "string": str,
            "number": float,
            "bool": bool,
        }
        fields: Dict[str, tuple[type, Any]] = {}
        for name, spec in props.items():
            type_str = (
                spec if isinstance(spec, str) else spec.get("type")
            )  # spec may be string or dict
            py_type = type_mapping.get(type_str)
            if py_type is None:
                raise ValueError(
                    f"Unsupported input type: {type_str!r} for field {name!r}"
                )
            default = ... if name in required else None
            fields[name] = (py_type, default)

        from typing import cast as _cast

        # The raw ``create_model`` helper from Pydantic deliberately uses *dynamic*
        # signatures, which the static type checker cannot easily verify.  We cast
        # the **fields** mapping to **Any** to silence these warnings.
        return create_model(  # type: ignore[arg-type]
            f"{self.schema.name}_Inputs",
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
        default_name = "".join(c if c.isalnum() else "_" for c in self.name)
        tool_name = name or default_name[:50]
        doc = description or self.description  # Use schema description

        # `self` is closed over via the inner function so we can keep state.
        async def _invoke(**kwargs):  # type: ignore[override]
            logger.info(f"Running workflow as tool with inputs: {kwargs}")
            result = await self.run_async(inputs=kwargs if kwargs else None)
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

    async def run_as_tool(self, input: str) -> str:
        """Run the workflow as a tool with the given input.
        Uses AgentExecutor to properly handle the tool invocation loop.
        """
        # For now I kept it simpel but one could think of using a react agent here.
        if self.llm is None:
            raise ValueError(
                "Cannot run as tool: An 'llm' instance must be supplied for tool-based steps"
            )
        prompt = ChatPromptTemplate.from_messages(
            [
                ("system", "You are a helpful assistant"),
                ("human", "{input}"),
                # Placeholders fill up a **list** of messages
                ("placeholder", "{agent_scratchpad}"),
            ]
        )

        # Create the workflow tool
        workflow_tool = self.as_tool()
        agent = create_tool_calling_agent(self.llm, [workflow_tool], prompt)
        agent_executor = AgentExecutor(agent=agent, tools=[workflow_tool])
        result = await agent_executor.ainvoke({"input": input})
        return result["output"]


class WorkflowExecutor:
    """Handles loading workflows from files and executing them."""

    def __init__(
        self,
        llm: BaseChatModel,
        *,
        # Pass default dependencies for Workflow instances created by the executor
        controller: WorkflowController | None = None,
        browser: Browser | None = None,
        fallback_to_agent: bool = True,
    ):
        """Initialize the WorkflowExecutor.

        Args:
            controller: Default WorkflowController for created Workflows.
            browser: Default Browser instance for created Workflows.
            llm: Default language model for created Workflows.
            fallback_to_agent: Default fallback behavior for created Workflows.
        """
        self.controller = controller
        self.browser = browser
        self.llm = llm
        self.fallback_to_agent = fallback_to_agent

    def load_workflow_from_path(self, json_path: Union[str, Path]) -> Workflow:
        """Loads a workflow definition from a JSON file and initializes a Workflow instance."""
        path = Path(json_path)
        if not path.exists():
            raise FileNotFoundError(f"Workflow definition file not found: {path}")

        try:
            with path.open("r", encoding="utf-8") as f:
                data = _json.load(f)
            # Use the imported WorkflowDefinitionSchema for validation
            schema = WorkflowDefinitionSchema(**data)
        except Exception as e:
            raise ValueError(
                f"Failed to load or parse workflow definition from {path}: {e}"
            ) from e

        # Initialize Workflow with the loaded schema and executor's defaults
        return Workflow(
            workflow_schema=schema,
            controller=self.controller,
            browser=self.browser,
            llm=self.llm,
            fallback_to_agent=self.fallback_to_agent,
        )

    async def run_workflow(
        self, workflow: Workflow, inputs: dict[str, Any] | None = None
    ) -> List[Any]:
        """Executes a given Workflow instance asynchronously."""
        return await workflow.run_async(inputs=inputs)

    async def run_workflow_from_path(
        self, json_path: Union[str, Path], inputs: dict[str, Any] | None = None
    ) -> List[Any]:
        """Loads a workflow from a path and executes it asynchronously."""
        workflow = self.load_workflow_from_path(json_path)
        return await self.run_workflow(workflow, inputs=inputs)
