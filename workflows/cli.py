import asyncio
import json
import tempfile  # For temporary file handling
from pathlib import Path

import typer

# Assuming OPENAI_API_KEY is set in the environment
from langchain_openai import ChatOpenAI

from src.builder.service import BuilderService
from src.recorder.service import RecordingService  # Added import
from src.workflow.service import WorkflowExecutor

# Placeholder for recorder functionality
# from src.recorder.service import RecorderService

app = typer.Typer(
    name="workflow-cli",
    help="A CLI tool to create and run workflows.",
    add_completion=False,
    no_args_is_help=True,
)

# Instantiate services (assuming OPENAI_API_KEY is set in environment)
try:
    llm_instance = ChatOpenAI(model="gpt-4o")
except Exception as e:
    print(f"Error initializing LLM: {e}. Ensure OPENAI_API_KEY is set.")
    # Potentially exit or provide a way to configure API key
    llm_instance = None

builder_service = BuilderService(llm=llm_instance) if llm_instance else None
# recorder_service = RecorderService() # Placeholder
workflow_executor = WorkflowExecutor(llm_instance) if llm_instance else None
recording_service = RecordingService()  # Assuming RecordingService does not need LLM, or handle its potential None state if it does.


def get_default_save_dir() -> Path:
    """Returns the default save directory for workflows."""
    # Ensure ./tmp exists for temporary files as well if we use it
    tmp_dir = Path("./tmp").resolve()
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
            "BuilderService not initialized. Cannot build workflow.",
            fg=typer.colors.RED,
        )
        return None

    prompt_subject = "recorded" if is_temp_recording else "provided"
    description: str = typer.prompt(
        f"What is the purpose of this {prompt_subject} workflow?"
    )

    output_dir_str: str = typer.prompt(
        f"Where would you like to save the final built workflow? (e.g., ./my_workflows, press Enter for '{default_save_dir}')",
        default=str(default_save_dir),
    )
    output_dir = Path(output_dir_str).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    typer.echo(f"The final built workflow will be saved in: {output_dir}")

    typer.echo(
        f"Building workflow from the {prompt_subject} recording ('{recording_path.name}') and description..."
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
            f"Error: Recording file not found at {recording_path}. Please ensure it exists.",
            fg=typer.colors.RED,
        )
        return None
    except Exception as e:
        typer.secho(f"Error building workflow: {e}", fg=typer.colors.RED)
        return None

    if not workflow_definition:
        typer.secho(
            f"Failed to build workflow definition from the {prompt_subject} recording.",
            fg=typer.colors.RED,
        )
        return None

    typer.secho("Workflow built successfully!", fg=typer.colors.GREEN)

    file_stem = recording_path.stem
    if is_temp_recording:
        file_stem = file_stem.replace("temp_recording_", "") or "recorded"

    default_workflow_filename = f"{file_stem}.workflow.json"
    workflow_output_name: str = typer.prompt(
        "Enter a name for the generated workflow file (e.g., my_search.workflow.json):",
        default=default_workflow_filename,
    )
    final_workflow_path = output_dir / workflow_output_name

    try:
        asyncio.run(
            builder_service.save_workflow_to_path(
                workflow_definition, final_workflow_path
            )
        )
        typer.secho(
            f"Final workflow definition saved to: {final_workflow_path.resolve()}",
            fg=typer.colors.GREEN,
        )
        return final_workflow_path
    except Exception as e:
        typer.secho(f"Error saving workflow: {e}", fg=typer.colors.RED)
        return None


@app.command(
    name="create-workflow",
    help="Records a new browser interaction and then builds a workflow definition.",
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
            "RecordingService not available. Cannot create workflow.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    default_tmp_dir = get_default_save_dir()  # Ensures ./tmp exists for temporary files

    typer.echo("Starting interactive browser recording session...")
    typer.echo(
        "Please follow instructions in the browser. Close the browser or follow prompts to stop recording."
    )

    temp_recording_path = None
    try:
        captured_recording_model = asyncio.run(recording_service.capture_workflow())

        if not captured_recording_model:
            typer.secho(
                "Recording session ended, but no workflow data was captured.",
                fg=typer.colors.YELLOW,
            )
            raise typer.Exit(code=1)

        typer.secho("Recording captured successfully!", fg=typer.colors.GREEN)

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            prefix="temp_recording_",
            delete=False,
            dir=default_tmp_dir,
            encoding="utf-8",
        ) as tmp_file:
            try:
                tmp_file.write(captured_recording_model.model_dump_json(indent=2))
            except AttributeError:
                json.dump(captured_recording_model, tmp_file, indent=2)
            temp_recording_path = Path(tmp_file.name)

        typer.echo(f"Temporary recording saved to: {temp_recording_path}")

        # Use the helper function to build and save
        saved_path = _build_and_save_workflow_from_recording(
            temp_recording_path, default_tmp_dir, is_temp_recording=True
        )
        if not saved_path:
            typer.secho(
                "Failed to complete workflow creation after recording.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

    except Exception as e:
        typer.secho(
            f"An error occurred during workflow creation: {e}", fg=typer.colors.RED
        )
        raise typer.Exit(code=1)


@app.command(
    name="build-from-recording",
    help="Builds a workflow definition from an existing recording JSON file.",
)
def build_from_recording_command(
    recording_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        resolve_path=True,
        help="Path to the existing recording JSON file.",
    ),
):
    """
    Takes a path to a recording JSON file, prompts for workflow details,
    builds the workflow using BuilderService, and saves it.
    """
    default_save_dir = get_default_save_dir()
    typer.echo(f"Building workflow from provided recording: {recording_path.resolve()}")

    saved_path = _build_and_save_workflow_from_recording(
        recording_path, default_save_dir, is_temp_recording=False
    )
    if not saved_path:
        typer.secho(
            f"Failed to build workflow from {recording_path.name}.", fg=typer.colors.RED
        )
        raise typer.Exit(code=1)
    else:
        typer.secho("Workflow built and saved successfully.", fg=typer.colors.GREEN)


@app.command(name="run-workflow", help="Runs an existing workflow from a JSON file.")
def run_workflow_command(
    workflow_path: Path = typer.Argument(
        ...,
        exists=True,
        file_okay=True,
        dir_okay=False,
        readable=True,
        help="Path to the .workflow.json file.",
        show_default=False,
    ),
):
    """
    Loads and executes a workflow, prompting the user for required inputs.
    """
    if not workflow_executor:
        typer.secho(
            "WorkflowExecutor not initialized. Please check your OpenAI API key.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    typer.echo(f"Loading workflow from: {workflow_path.resolve()}")

    try:
        workflow_definition_obj = workflow_executor.load_workflow_from_path(
            workflow_path
        )
    except Exception as e:
        typer.secho(f"Error loading workflow: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.secho("Workflow loaded successfully.", fg=typer.colors.GREEN)

    inputs = {}
    # input_schema_dict is now a List[WorkflowInputSchemaDefinition]
    input_definitions = workflow_definition_obj.inputs_def

    if input_definitions:  # Check if the list is not empty
        typer.echo("\nProvide values for the following workflow inputs:")

        for input_def in input_definitions:
            var_name = input_def.name
            # Assuming description might be part of future enhancements or a default.
            # For now, we'll construct a prompt_text without a specific description field
            # from input_def, unless it's added to WorkflowInputSchemaDefinition.
            # The original code used var_details.get("description", ...), we'll adapt.
            prompt_text = f"Enter value for '{var_name}'"
            var_type = input_def.type.lower()  # type is a direct attribute

            is_required = (
                input_def.required
            )  # required is a direct attribute (Optional[bool])
            type_display = f" (type: {var_type})"
            if is_required:  # True if required, False or None if optional
                prompt_text += f" (required{type_display})"
            else:
                prompt_text += f" (optional{type_display})"

            input_val = None
            # The original code used var_details.get("default", ...)
            # WorkflowInputSchemaDefinition doesn't have a 'default' field.
            # We will proceed without default values for now, or Typer's default handling will apply.
            if var_type == "bool":
                # For bool, typer.confirm's default is False if not specified.
                input_val = typer.confirm(prompt_text)  # Default handling by typer
            elif var_type == "number":
                input_val = typer.prompt(
                    prompt_text, type=float
                )  # Default handling by typer
            elif var_type == "string":
                input_val = typer.prompt(
                    prompt_text, type=str
                )  # Default handling by typer
            else:
                typer.secho(
                    f"Warning: Unknown type '{var_type}' for variable '{var_name}'. Treating as string.",
                    fg=typer.colors.YELLOW,
                )
                input_val = typer.prompt(prompt_text, type=str)

            inputs[var_name] = input_val
    else:
        typer.echo(
            "No input schema found in the workflow, or no properties defined. Proceeding without inputs."
        )

    typer.echo("\nRunning workflow...")
    typer.echo(f"With inputs: {inputs}")

    try:
        result = asyncio.run(
            workflow_executor.run_workflow(
                workflow_definition_obj, inputs, close_browser_at_end=False
            )
        )

        typer.secho("\nWorkflow execution completed!", fg=typer.colors.GREEN)
        typer.echo("Result:")
        # User updated this part
        print(len(result), "steps")

    except Exception as e:
        typer.secho(f"Error running workflow: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
