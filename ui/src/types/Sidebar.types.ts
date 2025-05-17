import { type WorkflowMetadata } from './Workflow.types';

export interface SidebarProps {
  workflows: string[];
  onSelect: (wf: string) => void;
  selected: string | null;
  workflowMetadata: WorkflowMetadata | null;
  onUpdateMetadata: (metadata: WorkflowMetadata) => Promise<void>;
  allWorkflowsMetadata?: Record<string, WorkflowMetadata>;
}