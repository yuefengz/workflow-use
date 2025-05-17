import asyncio
import json
import tempfile  # For temporary file handling
from pathlib import Path

import typer

# Assuming OPENAI_API_KEY is set in the environment
from langchain_openai import ChatOpenAI

from workflow_use.builder.service import BuilderService
from workflow_use.recorder.service import RecordingService  # Added import
from workflow_use.workflow.service import WorkflowExecutor

# Placeholder for recorder functionality
# from src.recorder.service import RecorderService

app = typer.Typer(
	name='workflow-cli',
	help='A CLI tool to create and run workflows.',
	add_completion=False,
	no_args_is_help=True,
)

# Instantiate services (assuming OPENAI_API_KEY is set in environment)
try:
	llm_instance = ChatOpenAI(model='gpt-4o')
except Exception as e:
	typer.secho(f'Error initializing LLM: {e}. Ensure OPENAI_API_KEY is set.', fg=typer.colors.RED)
	# Potentially exit or provide a way to configure API key
	llm_instance = None

builder_service = BuilderService(llm=llm_instance) if llm_instance else None
# recorder_service = RecorderService() # Placeholder
workflow_executor = WorkflowExecutor(llm_instance) if llm_instance else None
recording_service = (
	RecordingService()
)  # Assuming RecordingService does not need LLM, or handle its potential None state if it does.


def get_default_save_dir() -> Path:
	"""Returns the default save directory for workflows."""
	# Ensure ./tmp exists for temporary files as well if we use it
	tmp_dir = Path('./tmp').resolve()
	tmp_dir.mkdir(parents=True, exist_ok=True)
	return tmp_dir


# --- Helper function for building and saving workflow ---
def _build_and_save_workflow_from_recording(
	recording_path: Path,
	default_save_dir: Path,
	is_temp_recording: bool = False,  # To adjust messages if it's from a live recording
) -> Path | None:
	"""Builds a workflow from a recording file, prompts for details, and saves it."""
	if not builder_service:
		typer.secho(
			'BuilderService not initialized. Cannot build workflow.',
			fg=typer.colors.RED,
		)
		return None

	prompt_subject = 'recorded' if is_temp_recording else 'provided'
	typer.echo()  # Add space
	description: str = typer.prompt(typer.style(f'What is the purpose of this {prompt_subject} workflow?', bold=True))

	typer.echo()  # Add space
	output_dir_str: str = typer.prompt(
		typer.style('Where would you like to save the final built workflow?', bold=True)
		+ f" (e.g., ./my_workflows, press Enter for '{default_save_dir}')",
		default=str(default_save_dir),
	)
	output_dir = Path(output_dir_str).resolve()
	output_dir.mkdir(parents=True, exist_ok=True)

	typer.echo(f'The final built workflow will be saved in: {typer.style(str(output_dir), fg=typer.colors.CYAN)}')
	typer.echo()  # Add space

	typer.echo(
		f'Processing recording ({typer.style(str(recording_path.name), fg=typer.colors.MAGENTA)}) and building workflow...'
	)
	try:
		workflow_definition = asyncio.run(
			builder_service.build_workflow_from_path(
				recording_path,
				description,
			)
		)
	except FileNotFoundError:
		typer.secho(
			f'Error: Recording file not found at {recording_path}. Please ensure it exists.',
			fg=typer.colors.RED,
		)
		return None
	except Exception as e:
		typer.secho(f'Error building workflow: {e}', fg=typer.colors.RED)
		return None

	if not workflow_definition:
		typer.secho(
			f'Failed to build workflow definition from the {prompt_subject} recording.',
			fg=typer.colors.RED,
		)
		return None

	typer.secho('Workflow built successfully!', fg=typer.colors.GREEN, bold=True)
	typer.echo()  # Add space

	file_stem = recording_path.stem
	if is_temp_recording:
		file_stem = file_stem.replace('temp_recording_', '') or 'recorded'

	default_workflow_filename = f'{file_stem}.workflow.json'
	workflow_output_name: str = typer.prompt(
		typer.style('Enter a name for the generated workflow file', bold=True) + f' (e.g., my_search.workflow.json):',
		default=default_workflow_filename,
	)
	final_workflow_path = output_dir / workflow_output_name

	try:
		asyncio.run(builder_service.save_workflow_to_path(workflow_definition, final_workflow_path))
		typer.secho(
			f'Final workflow definition saved to: {typer.style(str(final_workflow_path.resolve()), fg=typer.colors.BRIGHT_GREEN, bold=True)}',
			fg=typer.colors.GREEN,  # Overall message color
		)
		return final_workflow_path
	except Exception as e:
		typer.secho(f'Error saving workflow: {e}', fg=typer.colors.RED)
		return None


@app.command(
	name='create-workflow',
	help='Records a new browser interaction and then builds a workflow definition.',
)
def create_workflow():
	"""
	Guides the user through recording browser actions, then uses the helper
	to build and save the workflow definition.
	"""
	if not recording_service:
		# Adjusted RecordingService initialization check assuming it doesn't need LLM
		# If it does, this check should be more robust (e.g. based on llm_instance)
		typer.secho(
			'RecordingService not available. Cannot create workflow.',
			fg=typer.colors.RED,
		)
		raise typer.Exit(code=1)

	default_tmp_dir = get_default_save_dir()  # Ensures ./tmp exists for temporary files

	typer.echo(typer.style('Starting interactive browser recording session...', bold=True))
	typer.echo('Please follow instructions in the browser. Close the browser or follow prompts to stop recording.')
	typer.echo()  # Add space

	temp_recording_path = None
	try:
		captured_recording_model = asyncio.run(recording_service.capture_workflow())

		if not captured_recording_model:
			typer.secho(
				'Recording session ended, but no workflow data was captured.',
				fg=typer.colors.YELLOW,
			)
			raise typer.Exit(code=1)

		typer.secho('Recording captured successfully!', fg=typer.colors.GREEN, bold=True)
		typer.echo()  # Add space

		with tempfile.NamedTemporaryFile(
			mode='w',
			suffix='.json',
			prefix='temp_recording_',
			delete=False,
			dir=default_tmp_dir,
			encoding='utf-8',
		) as tmp_file:
			try:
				tmp_file.write(captured_recording_model.model_dump_json(indent=2))
			except AttributeError:
				json.dump(captured_recording_model, tmp_file, indent=2)
			temp_recording_path = Path(tmp_file.name)

		# Use the helper function to build and save
		saved_path = _build_and_save_workflow_from_recording(temp_recording_path, default_tmp_dir, is_temp_recording=True)
		if not saved_path:
			typer.secho(
				'Failed to complete workflow creation after recording.',
				fg=typer.colors.RED,
			)
			raise typer.Exit(code=1)

	except Exception as e:
		typer.secho(f'An error occurred during workflow creation: {e}', fg=typer.colors.RED)
		raise typer.Exit(code=1)


@app.command(
	name='build-from-recording',
	help='Builds a workflow definition from an existing recording JSON file.',
)
def build_from_recording_command(
	recording_path: Path = typer.Argument(
		...,
		exists=True,
		file_okay=True,
		dir_okay=False,
		readable=True,
		resolve_path=True,
		help='Path to the existing recording JSON file.',
	),
):
	"""
	Takes a path to a recording JSON file, prompts for workflow details,
	builds the workflow using BuilderService, and saves it.
	"""
	default_save_dir = get_default_save_dir()
	typer.echo(
		typer.style(
			f'Building workflow from provided recording: {typer.style(str(recording_path.resolve()), fg=typer.colors.MAGENTA)}',
			bold=True,
		)
	)
	typer.echo()  # Add space

	saved_path = _build_and_save_workflow_from_recording(recording_path, default_save_dir, is_temp_recording=False)
	if not saved_path:
		typer.secho(f'Failed to build workflow from {recording_path.name}.', fg=typer.colors.RED)
		raise typer.Exit(code=1)

@app.command(name='run-as-tool', help='Runs an existing workflow as a tool with an LLM-driven prompt.')
def run_as_tool_command(
    workflow_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help='Path to the .workflow.json file.',
        show_default=False,
    ),
    prompt: str = typer.Option(
        ...,
        '--prompt',
        '-p',
        help='Prompt for the LLM to reason about and execute the workflow.',
        prompt=True,  # Prompts interactively if not provided
    ),
):
    """
    Loads a workflow and runs it as a tool, using the provided prompt to let the LLM
    determine the necessary inputs and execute the workflow.
    """
    if not workflow_executor:
        typer.secho(
            'WorkflowExecutor not initialized. Please check your OpenAI API key.',
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    typer.echo(
        typer.style(f'Loading workflow from: {typer.style(str(workflow_path.resolve()), fg=typer.colors.MAGENTA)}', bold=True)
    )
    typer.echo()  # Add space

    try:
        workflow_definition_obj = workflow_executor.load_workflow_from_path(workflow_path)
    except Exception as e:
        typer.secho(f'Error loading workflow: {e}', fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.secho('Workflow loaded successfully.', fg=typer.colors.GREEN, bold=True)
    typer.echo()  # Add space
    typer.echo(typer.style(f'Running workflow as tool with prompt: "{prompt}"', bold=True))

    try:
        result = asyncio.run(workflow_definition_obj.run_as_tool(prompt))
        typer.secho('\nWorkflow execution completed!', fg=typer.colors.GREEN, bold=True)
        typer.echo(typer.style('Result:', bold=True))
        typer.echo(json.dumps(result, indent=2))
    except Exception as e:
        typer.secho(f'Error running workflow as tool: {e}', fg=typer.colors.RED)
        raise typer.Exit(code=1)

@app.command(name='run-workflow', help='Runs an existing workflow from a JSON file.')
def run_workflow_command(
	workflow_path: Path = typer.Argument(
		...,
		exists=True,
		file_okay=True,
		dir_okay=False,
		readable=True,
		help='Path to the .workflow.json file.',
		show_default=False,
	),
):
	"""
	Loads and executes a workflow, prompting the user for required inputs.
	"""
	if not workflow_executor:
		typer.secho(
			'WorkflowExecutor not initialized. Please check your OpenAI API key.',
			fg=typer.colors.RED,
		)
		raise typer.Exit(code=1)

	typer.echo(
		typer.style(f'Loading workflow from: {typer.style(str(workflow_path.resolve()), fg=typer.colors.MAGENTA)}', bold=True)
	)
	typer.echo()  # Add space

	try:
		workflow_definition_obj = workflow_executor.load_workflow_from_path(workflow_path)
	except Exception as e:
		typer.secho(f'Error loading workflow: {e}', fg=typer.colors.RED)
		raise typer.Exit(code=1)

	typer.secho('Workflow loaded successfully.', fg=typer.colors.GREEN, bold=True)

	inputs = {}
	# input_schema_dict is now a List[WorkflowInputSchemaDefinition]
	input_definitions = workflow_definition_obj.inputs_def

	if input_definitions:  # Check if the list is not empty
		typer.echo()  # Add space
		typer.echo(typer.style('Provide values for the following workflow inputs:', bold=True))
		typer.echo()  # Add space

		for input_def in input_definitions:
			var_name_styled = typer.style(input_def.name, fg=typer.colors.CYAN, bold=True)
			prompt_question = typer.style(f'Enter value for {var_name_styled}', bold=True)

			var_type = input_def.type.lower()  # type is a direct attribute
			is_required = input_def.required

			type_info_str = f'type: {var_type}'
			if is_required:
				status_str = typer.style('required', fg=typer.colors.RED)
			else:
				status_str = typer.style('optional', fg=typer.colors.YELLOW)

			full_prompt_text = f'{prompt_question} ({status_str}, {type_info_str})'

			input_val = None
			if var_type == 'bool':
				input_val = typer.confirm(full_prompt_text)
			elif var_type == 'number':
				input_val = typer.prompt(full_prompt_text, type=float)
			elif var_type == 'string':
				input_val = typer.prompt(full_prompt_text, type=str)
			else:
				typer.secho(
					f"Warning: Unknown type '{var_type}' for variable '{input_def.name}'. Treating as string.",
					fg=typer.colors.YELLOW,
				)
				input_val = typer.prompt(full_prompt_text, type=str)

			inputs[input_def.name] = input_val
			typer.echo()  # Add space after each prompt
	else:
		typer.echo('No input schema found in the workflow, or no properties defined. Proceeding without inputs.')

	typer.echo()  # Add space
	typer.echo(typer.style('Running workflow...', bold=True))

	try:
		result = asyncio.run(workflow_executor.run_workflow(workflow_definition_obj, inputs, close_browser_at_end=False))

		typer.secho('\nWorkflow execution completed!', fg=typer.colors.GREEN, bold=True)
		typer.echo(typer.style('Result:', bold=True))
		# User updated this part
		typer.echo(f'{typer.style(str(len(result)), bold=True)} steps')

	except Exception as e:
		typer.secho(f'Error running workflow: {e}', fg=typer.colors.RED)
		raise typer.Exit(code=1)


if __name__ == '__main__':
	app()
