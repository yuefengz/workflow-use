from typing import List

from browser_use.agent.views import ActionResult, AgentHistoryList
from pydantic import BaseModel


class WorkflowRunOutput(BaseModel):
	"""Output of a workflow run"""

	step_results: List[ActionResult | AgentHistoryList]
