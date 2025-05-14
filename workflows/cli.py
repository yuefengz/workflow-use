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
recording_service = (
    RecordingService() if llm_instance else None
)  # Added RecordingService, assuming it might need LLM or can be None


def get_default_save_dir() -> Path:
    """Returns the default save directory for workflows."""
    # Ensure ./tmp exists for temporary files as well if we use it
    tmp_dir = Path("./tmp").resolve()
    tmp_dir.mkdir(parents=True, exist_ok=True)
    return tmp_dir


@app.command(
    name="create-workflow",
    help="Records a new browser interaction and then builds a workflow definition.",
)
def create_workflow(
    # recording_path argument removed
    # description and output_dir will be prompted after recording
):
    """
    Guides the user through recording browser actions, describing the workflow,
    and then builds and saves the workflow definition.
    """
    if not recording_service:
        typer.secho(
            "RecordingService not initialized. This might be due to LLM initialization issues if it depends on it.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)
    if not builder_service:
        typer.secho(
            "BuilderService not initialized. Please check your OpenAI API key.",
            fg=typer.colors.RED,
        )
        raise typer.Exit(code=1)

    default_tmp_dir = get_default_save_dir()  # Ensures ./tmp exists

    # --- 1. Record Workflow ---
    typer.echo("Starting interactive browser recording session...")
    typer.echo("Please follow the instructions in the browser window that will open.")
    typer.echo(
        "When you are finished with the recording, close the browser or follow the service's prompts to stop."
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

        # Save captured recording to a temporary file for the builder service
        # Using a named temporary file within the ./tmp directory for better visibility/debugging if needed
        # but it will be deleted.
        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".json",
            prefix="temp_recording_",
            delete=False,  # We'll delete it manually after builder service uses it
            dir=default_tmp_dir,  # Save in ./tmp
            encoding="utf-8",
        ) as tmp_file:
            # recorder.py example uses model_dump_json, assuming captured_recording_model is a Pydantic model
            try:
                tmp_file.write(captured_recording_model.model_dump_json(indent=2))
                temp_recording_path = Path(tmp_file.name)
            except AttributeError:
                # Fallback if it's not a Pydantic model but a dict
                json.dump(captured_recording_model, tmp_file, indent=2)
                temp_recording_path = Path(tmp_file.name)

        typer.echo(f"Temporary recording saved to: {temp_recording_path}")

        # --- 2. Get Description and Output Path from User ---
        description: str = typer.prompt(
            "What is the purpose of this recorded workflow?"
        )

        output_dir_str: str = typer.prompt(
            "Where would you like to save the final built workflow? (e.g., ./tmp/my_workflows, press Enter for ./tmp/)",
            default=str(default_tmp_dir),
        )
        output_dir = Path(output_dir_str).resolve()
        output_dir.mkdir(parents=True, exist_ok=True)

        typer.echo(f"The final built workflow will be saved in: {output_dir}")

        # --- 3. Build Workflow ---
        typer.echo("Building workflow from the captured recording and description...")
        workflow_definition = asyncio.run(
            builder_service.build_workflow_from_path(
                temp_recording_path,
                description,
            )
        )

        if not workflow_definition:
            typer.secho(
                "Failed to build workflow definition from the recording.",
                fg=typer.colors.RED,
            )
            raise typer.Exit(code=1)

        typer.secho("Workflow built successfully!", fg=typer.colors.GREEN)

        # --- 4. Save Workflow ---
        default_workflow_filename = f"{temp_recording_path.stem.replace('temp_recording_', '') or 'recorded'}.workflow.json"
        workflow_output_name: str = typer.prompt(
            "Enter a name for the generated workflow file (e.g., my_search.workflow.json):",
            default=default_workflow_filename,
        )
        final_workflow_path = output_dir / workflow_output_name

        asyncio.run(
            builder_service.save_workflow_to_path(
                workflow_definition, final_workflow_path
            )
        )
        typer.secho(
            f"Final workflow definition saved to: {final_workflow_path.resolve()}",
            fg=typer.colors.GREEN,
        )

    except Exception as e:
        typer.secho(
            f"An error occurred during workflow creation: {e}", fg=typer.colors.RED
        )
        # import traceback # For debugging uncomment this
        # traceback.print_exc()
        raise typer.Exit(code=1)
    finally:
        # --- 5. Cleanup ---
        if temp_recording_path and temp_recording_path.exists():
            try:
                temp_recording_path.unlink()
                typer.echo(
                    f"Cleaned up temporary recording file: {temp_recording_path}"
                )
            except OSError as e_unlink:
                typer.secho(
                    f"Error deleting temporary file {temp_recording_path}: {e_unlink}",
                    fg=typer.colors.YELLOW,
                )


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
        workflow_definition = workflow_executor.load_workflow_from_path(workflow_path)
    except Exception as e:
        typer.secho(f"Error loading workflow: {e}", fg=typer.colors.RED)
        raise typer.Exit(code=1)

    typer.secho("Workflow loaded successfully.", fg=typer.colors.GREEN)

    # --- Parse and collect input variables ---
    inputs = {}
    # Access input_schema through workflow_definition.inputs_def, which is a dict
    input_schema_dict = workflow_definition.inputs_def

    if input_schema_dict and input_schema_dict.get("properties"):
        typer.echo("\nProvide values for the following workflow inputs:")
        properties = input_schema_dict["properties"]
        required_props = input_schema_dict.get("required", [])

        for var_name, var_details in properties.items():
            prompt_text = var_details.get(
                "description", f"Enter value for '{var_name}'"
            )
            # Get type from schema, default to "string"
            # Based on src/schema/views.py: InputSchemaPropertyDetail -> type: Literal["string", "number", "bool"]
            var_type = var_details.get("type", "string").lower()

            is_required = var_name in required_props
            type_display = f" (type: {var_type})"
            if is_required:
                prompt_text += f" (required{type_display})"
            else:
                prompt_text += f" (optional{type_display})"

            input_val = None
            if var_type == "bool":
                # Use typer.confirm for boolean inputs
                default_val = var_details.get(
                    "default", False
                )  # Default for confirm is False
                if isinstance(
                    default_val, str
                ):  # Handle string default from schema if any
                    default_val = default_val.lower() in ["true", "t", "yes", "y", "1"]
                input_val = typer.confirm(prompt_text, default=default_val)
            elif var_type == "number":
                # Use typer.prompt with type=float for numbers
                default_val = var_details.get("default")
                try:
                    # Ensure default is float if provided
                    default_val_float = (
                        float(default_val) if default_val is not None else None
                    )
                    input_val = typer.prompt(
                        prompt_text, default=default_val_float, type=float
                    )
                except ValueError:
                    # If default is not a valid float, prompt without it or handle error
                    typer.secho(
                        f"Warning: Default value '{default_val}' for '{var_name}' is not a valid number. Prompting without default.",
                        fg=typer.colors.YELLOW,
                    )
                    input_val = typer.prompt(prompt_text, type=float)
            elif var_type == "string":
                # Use typer.prompt with type=str for strings
                default_val = var_details.get("default")
                input_val = typer.prompt(prompt_text, default=default_val, type=str)
            else:
                # Fallback for any other unspecified types, treat as string
                typer.secho(
                    f"Warning: Unknown type '{var_type}' for variable '{var_name}'. Treating as string.",
                    fg=typer.colors.YELLOW,
                )
                default_val = var_details.get("default")
                input_val = typer.prompt(prompt_text, default=default_val, type=str)

            inputs[var_name] = input_val

    else:
        typer.echo(
            "No input schema found in the workflow, or no properties defined. Proceeding without inputs."
        )

    # --- Run Workflow ---
    typer.echo("\nRunning workflow...")
    typer.echo(f"With inputs: {inputs}")

    try:
        # The run_workflow method in the test used asyncio.run()
        # We need to ensure the executor's run_workflow is awaitable if called like this
        # or that workflow_executor.run_workflow is synchronous.
        # From the test: result = await executor.run_workflow(workflow, {"model": "12"})
        # So it is an async function.

        # Ensure there's an event loop if running async code directly with asyncio.run
        # Typer commands are synchronous by default.
        # If WorkflowExecutor.run_workflow is an async def, we must run it in an event loop.
        result = asyncio.run(
            workflow_executor.run_workflow(workflow_definition, inputs)
        )

        typer.secho("\nWorkflow execution completed!", fg=typer.colors.GREEN)
        typer.echo("Result:")
        # Pretty print the result if it's a dictionary or list
        # if isinstance(result, (dict, list)):
        #     try:
        #         import rich  # For pretty printing

        #         rich.print(result)
        #     except ImportError:
        #         # print(json.dumps(result, indent=2))  # Fallback to standard json print
        # else:
        #     print(result)
        print(len(result), "steps")

    except Exception as e:
        typer.secho(f"Error running workflow: {e}", fg=typer.colors.RED)
        # You might want to print more detailed traceback here for debugging
        # import traceback
        # traceback.print_exc()
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
