import typer
from pathlib import Path

# Ensure langchain-openai is installed and OPENAI_API_KEY is set
from langchain_openai import ChatOpenAI
from src.builder.service import BuilderService
from src.schema.views import WorkflowDefinitionSchema


# Instantiate the LLM and the service directly
llm_instance = ChatOpenAI(model="gpt-4o-mini")  # Or your preferred model
builder_service = BuilderService(llm=llm_instance)


def main(
    path: Path = typer.Argument(
        ..., help="Path to the recorded browser session JSON file."
    ),
    user_goal: str = typer.Option(
        ..., "--goal", "-g", help="High-level description of the workflow's purpose."
    ),
):
    """
    Builds an executable workflow JSON definition from a recorded browser session.
    """
    print(f"Building workflow from: {path}")
    print(f"User Goal: {user_goal}")
    try:
        workflow_definition: WorkflowDefinitionSchema = (
            builder_service.build_workflow_from_path(path=path, user_goal=user_goal)
        )

        output_path = path.with_suffix(".workflow.json")
        builder_service.save_workflow_to_path(workflow_definition, output_path)
        print(f"Successfully built workflow definition and saved to: {output_path}")

    except FileNotFoundError:
        print(f"Error: Input file not found at {path}")
        raise typer.Exit(code=1)
    except ValueError as e:
        print(f"Error building workflow: {e}")
        raise typer.Exit(code=1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}")
        raise typer.Exit(code=1)


if __name__ == "__main__":
    typer.run(main)
