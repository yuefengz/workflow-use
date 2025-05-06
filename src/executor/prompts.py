WORKFLOW_FALLBACK_PROMPT_TEMPLATE = (
    "While executing step {step_index}/{total_steps} in the workflow:\n\n{workflow_details}\n\n"
    "The deterministic action failed with the following context:\n{fail_details}\n\n"
    "Please analyze the situation and achieve the objective of step {step_index} using the available browser actions. "
    "You do not have to use the same action – feel free to choose any suitable action(s) to accomplish the same goal. "
    "Once the objective of step {step_index} is reached, call the Done action to complete the step."
    "Do not attempt to use the same action again – choose a different one."
    "Do not continue with the next step, just complete step {step_index}."
)
