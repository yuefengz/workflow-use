from typing import Any, Dict, List, Literal, Optional, Union

from pydantic import BaseModel, Field, RootModel


# --- Input Schema Definition ---
# (Remains the same)
class InputSchemaPropertyDetail(BaseModel):
    type: Literal["string", "number", "bool"]


InputSchemaProperties = Dict[
    str, Union[Literal["string", "number", "bool"], InputSchemaPropertyDetail]
]


class WorkflowInputSchemaDefinition(BaseModel):
    type: Literal["object"] = Field(default="object")
    properties: InputSchemaProperties = Field(default_factory=dict)
    required: List[str] = Field(default_factory=list)


# --- Base Step Model ---
# Common fields for all step types
class BaseWorkflowStep(BaseModel):
    description: Optional[str] = Field(
        None, description="Optional description/comment about the step's purpose."
    )
    output: Optional[str] = Field(
        None, description="Context key to store step output under."
    )
    # Informational fields often included from recordings
    timestamp: Optional[int] = Field(
        None, description="Timestamp from recording (informational)."
    )
    tabId: Optional[int] = Field(
        None, description="Browser tab ID from recording (informational)."
    )
    # Allow other fields captured from raw events but not explicitly modeled
    model_config = {"extra": "allow"}


# --- Agent Step ---
class AgentWorkflowStep(BaseWorkflowStep):
    type: Literal["agent"]
    task: str = Field(
        ..., description="The objective or task description for the agent."
    )
    max_steps: Optional[int] = Field(
        None,
        description="Maximum number of iterations for the agent (default handled in code).",
    )
    # Agent steps might also have 'params' for other configs, handled by extra='allow'


# --- Deterministic Action Steps (based on controllers and examples) ---


# Actions from src/workflows/controller/service.py & Examples
class NavigationStep(BaseWorkflowStep):
    """Navigates using the 'navigation' action (likely maps to go_to_url)."""

    type: Literal["navigation"]  # As seen in examples
    url: str = Field(
        ..., description="Target URL to navigate to. Can use {context_var}."
    )


class ClickStep(BaseWorkflowStep):
    """Clicks an element using 'click' (maps to workflow controller's click)."""

    type: Literal["click"]  # As seen in examples
    cssSelector: str = Field(..., description="CSS selector for the target element.")
    xpath: Optional[str] = Field(
        None, description="XPath selector (often informational)."
    )
    elementTag: Optional[str] = Field(None, description="HTML tag (informational).")
    elementText: Optional[str] = Field(
        None, description="Element text (informational)."
    )


class InputStep(BaseWorkflowStep):
    """Inputs text using 'input' (maps to workflow controller's input)."""

    type: Literal["input"]  # As seen in examples
    cssSelector: str = Field(
        ..., description="CSS selector for the target input element."
    )
    value: str = Field(..., description="Value to input. Can use {context_var}.")
    xpath: Optional[str] = Field(None, description="XPath selector (informational).")
    elementTag: Optional[str] = Field(None, description="HTML tag (informational).")


class SelectChangeStep(BaseWorkflowStep):
    """Selects a dropdown option using 'select_change' (maps to workflow controller's select_change)."""

    type: Literal[
        "select_change"
    ]  # Assumed type for workflow controller's select_change
    cssSelector: str = Field(
        ..., description="CSS selector for the target select element."
    )
    selectedText: str = Field(
        ..., description="Visible text of the option to select. Can use {context_var}."
    )
    xpath: Optional[str] = Field(None, description="XPath selector (informational).")
    elementTag: Optional[str] = Field(None, description="HTML tag (informational).")


class KeyPressStep(BaseWorkflowStep):
    """Presses a key using 'key_press' (maps to workflow controller's key_press)."""

    type: Literal["key_press"]  # As seen in examples
    cssSelector: str = Field(..., description="CSS selector for the target element.")
    key: str = Field(..., description="The key to press (e.g., 'Tab', 'Enter').")
    xpath: Optional[str] = Field(None, description="XPath selector (informational).")
    elementTag: Optional[str] = Field(None, description="HTML tag (informational).")


class ScrollStep(BaseWorkflowStep):
    """Scrolls the page using 'scroll' (maps to workflow controller's scroll)."""

    type: Literal["scroll"]  # Assumed type for workflow controller's scroll
    scrollX: int = Field(..., description="Horizontal scroll pixels.")
    scrollY: int = Field(..., description="Vertical scroll pixels.")


# --- Base Controller Actions (browser_use/controller/service.py) ---
# These might be used directly or mapped to the types above by the builder LLM.
# We define them here for completeness, assuming direct usage is possible.


# class GoToUrlStep(BaseWorkflowStep):
#     type: Literal["go_to_url"]
#     url: str = Field(
#         ..., description="Target URL to navigate to. Can use {context_var}."
#     )


# class SearchGoogleStep(BaseWorkflowStep):
#     type: Literal["search_google"]
#     query: str = Field(..., description="Search query. Can use {context_var}.")


# class GoBackStep(BaseWorkflowStep):
#     type: Literal["go_back"]


# class WaitStep(BaseWorkflowStep):
#     type: Literal["wait"]
#     seconds: Optional[int] = Field(default=3, description="Seconds to wait.")


# class ClickElementByIndexStep(BaseWorkflowStep):
#     type: Literal["click_element_by_index"]
#     index: int = Field(
#         ..., description="Index of the element from the browser context map."
#     )


# class InputTextStep(BaseWorkflowStep):
#     type: Literal["input_text"]
#     index: int = Field(..., description="Index of the target input element.")
#     text: str = Field(..., description="Text to input. Can use {context_var}.")


# class SavePdfStep(BaseWorkflowStep):
#     type: Literal["save_pdf"]


# class SwitchTabStep(BaseWorkflowStep):
#     type: Literal["switch_tab"]
#     page_id: int = Field(..., description="ID of the target tab/page.")


# class OpenTabStep(BaseWorkflowStep):
#     type: Literal["open_tab"]
#     url: Optional[str] = Field(
#         None, description="URL for the new tab. Can use {context_var}."
#     )  # Parameter name based on controller


# class CloseTabStep(BaseWorkflowStep):
#     type: Literal["close_tab"]
#     page_id: int = Field(..., description="ID of the tab/page to close.")


class ExtractContentStep(BaseWorkflowStep):
    type: Literal["extract_content"]
    goal: str = Field(..., description="Goal for the content extraction LLM.")
    should_strip_link_urls: Optional[bool] = Field(default=False)


# class ScrollDownStep(BaseWorkflowStep):
#     type: Literal["scroll_down"]
#     amount: Optional[int] = Field(
#         None, description="Pixel amount to scroll down (defaults to viewport height)."
#     )


# class ScrollUpStep(BaseWorkflowStep):
#     type: Literal["scroll_up"]
#     amount: Optional[int] = Field(
#         None, description="Pixel amount to scroll up (defaults to viewport height)."
#     )


# class SendKeysStep(BaseWorkflowStep):
#     type: Literal["send_keys"]
#     keys: str = Field(
#         ...,
#         description="String of keys/shortcuts to press (e.g., 'Enter', 'Control+C').",
#     )


# class ScrollToTextStep(BaseWorkflowStep):
#     type: Literal["scroll_to_text"]
#     text: str = Field(..., description="Text content to scroll into view.")


# class GetDropdownOptionsStep(BaseWorkflowStep):
#     type: Literal["get_dropdown_options"]
#     index: int = Field(..., description="Index of the select element.")


# class SelectDropdownOptionStep(BaseWorkflowStep):
#     type: Literal["select_dropdown_option"]
#     index: int = Field(..., description="Index of the select element.")
#     text: str = Field(..., description="Visible text of the option to select.")


# # Position model needed for DragDrop
# class Position(BaseModel):
#     x: int
#     y: int


# class DragDropStep(BaseWorkflowStep):
#     type: Literal["drag_drop"]
#     element_source: Optional[str] = Field(
#         None, description="Selector for the source element."
#     )
#     element_target: Optional[str] = Field(
#         None, description="Selector for the target element."
#     )
#     element_source_offset: Optional[Position] = Field(
#         None, description="Offset within the source element."
#     )
#     element_target_offset: Optional[Position] = Field(
#         None, description="Offset within the target element."
#     )
#     coord_source_x: Optional[int] = Field(
#         None, description="Absolute source X coordinate."
#     )
#     coord_source_y: Optional[int] = Field(
#         None, description="Absolute source Y coordinate."
#     )
#     coord_target_x: Optional[int] = Field(
#         None, description="Absolute target X coordinate."
#     )
#     coord_target_y: Optional[int] = Field(
#         None, description="Absolute target Y coordinate."
#     )
#     steps: Optional[int] = Field(
#         None, description="Number of steps for smooth drag motion."
#     )
#     delay_ms: Optional[int] = Field(
#         None, description="Delay between drag steps in milliseconds."
#     )


# class DoneStep(BaseWorkflowStep):
#     """Represents the final step, indicating completion."""

#     type: Literal["done"]
#     # Parameters seen in example/base controller
#     text: Optional[str] = Field(None, description="Optional completion message.")
#     success: Optional[bool] = Field(
#         None, description="Success flag (defaults handled in code)."
#     )
#     properties: Optional[Dict[str, Any]] = Field(
#         None, description="Generic properties."
#     )
#     # data: Optional[Any] = Field(None, description="Structured output data (if output_model used).")


# --- Union of all possible step types ---
# This Union defines what constitutes a valid step in the "steps" list.
WorkflowStep = Union[
    AgentWorkflowStep,
    NavigationStep,
    ClickStep,
    InputStep,
    SelectChangeStep,
    KeyPressStep,
    ScrollStep,
    # GoToUrlStep,
    # SearchGoogleStep,
    # GoBackStep,
    # WaitStep,
    # ClickElementByIndexStep,
    # InputTextStep,
    # SavePdfStep,
    # SwitchTabStep,
    # OpenTabStep,
    # CloseTabStep,
    ExtractContentStep,
    # ScrollDownStep,
    # ScrollUpStep,
    # SendKeysStep,
    # ScrollToTextStep,
    # GetDropdownOptionsStep,
    # SelectDropdownOptionStep,
    # DragDropStep,
    # DoneStep,
]


# --- Top-Level Workflow Definition File ---
# Uses the Union WorkflowStep type


class WorkflowDefinitionSchema(BaseModel):
    """Pydantic model representing the structure of the workflow JSON file."""

    name: str = Field(..., description="The name of the workflow.")
    description: str = Field(
        ..., description="A human-readable description of the workflow."
    )
    version: str = Field(
        ..., description="The version identifier for this workflow definition."
    )
    input_schema: Optional[WorkflowInputSchemaDefinition] = Field(
        default=None,
        description="Optional schema defining the inputs required to run the workflow.",
    )
    steps: List[WorkflowStep] = Field(
        ...,
        min_length=1,
        description="An ordered list of steps (actions or agent tasks) to be executed.",
    )
