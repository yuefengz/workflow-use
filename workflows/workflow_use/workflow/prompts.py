WORKFLOW_FALLBACK_PROMPT_TEMPLATE = """Your task is to complete the step {step_index} of the workflow:

{workflow_details}

* There are {total_steps} steps in the workflow. You are currently on step {step_index}. You can safely assume that the steps before this one were completed successfully.
* This deterministic action '{action_type}' was attempted but failed with the following context:
{fail_details}

* The intended target or expected value for this step was:
{failed_value}

* Please analyze the situation and achieve the objective of step {step_index} using the available browser actions. 
* Once the objective of step {step_index} is reached, call the `Done` action to complete the step. 
* If key information is "<Not Given>", call the `Done` action to complete the step immediately.
* Do not proceed to the next step; focus ONLY on completing step {step_index}. DON'T DO ANYTHING ELSE.
"""

# * Do not retry the same action that failed. Instead, choose a different suitable action(s) to accomplish the same goal. For example, if a click failed, consider navigating to a URL, inputting text, or selecting an option. 

AGENTIC_STEP_PROMPT_TEMPLATE = """Your task is: {task}

## More context and instructions:
* Your task is to complete the step {step_index} of the workflow:

{workflow_details}

* There are {total_steps} steps in the workflow. You are currently on step {step_index}. You can safely assume that the steps before this one were completed successfully.
* Remember your task is to complete the step {step_index} of the workflow ONLY.
* Once the objective of step {step_index} is reached, call the `Done` action to complete the step. 
* If key information is "<Not Given>", call the `Done` action to complete the step immediately.
* Do not proceed to the next step; focus ONLY on completing step {step_index}. DON'T DO ANYTHING ELSE.
"""


STRUCTURED_OUTPUT_PROMPT = """
You are a data extraction expert. Your task is to extract structured information from the provided content.

The content may contain various pieces of information from different sources. You need to analyze this content and extract the relevant information according to the output schema provided below.

Only extract information that is explicitly present in the content. Be precise and follow the schema exactly.
"""
