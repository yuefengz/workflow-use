import { Edge } from '@xyflow/react';
import { Handle, Position, type NodeProps } from '@xyflow/react';

import { Workflow } from './types';
import { type PositionLoggerNode, type AppNode } from './types';

export interface WorkflowStep {
  description: string;
  type: string;
  [key: string]: any;
}

export interface WorkflowMetadata {
  name: string;
  description: string;
  version: string;
  input_schema: any[];
  workflow_analysis?: string;
}

export function jsonToFlow(workflow: string): { 
  nodes: AppNode[]; 
  edges: Edge[];
  metadata: WorkflowMetadata;
} {
  // workflow is a string
  const parsedWorkflow = JSON.parse(workflow) as Workflow;
  const nodes: AppNode[] = parsedWorkflow.steps.map((step: WorkflowStep, idx: number) => ({
    id: String(idx),
    data: { 
      label: `${step.description}`, 
      stepData: step,
      workflowName: parsedWorkflow.name // Add workflow name to each node for reference
    },
    position: { x: 0, y: idx * 100 }
  }));

  const edges: Edge[] = parsedWorkflow.steps.slice(1).map((_, idx) => ({
    id: `e${idx}-${idx + 1}`,
    source: String(idx),
    target: String(idx + 1),
    animated: true,
  }));

  // Extract metadata
  const metadata: WorkflowMetadata = {
    name: parsedWorkflow.name,
    description: parsedWorkflow.description,
    version: parsedWorkflow.version,
    input_schema: parsedWorkflow.input_schema,
    workflow_analysis: parsedWorkflow.workflow_analysis
  };

  return { nodes, edges, metadata };
}

// function PositionLoggerNode({
//   positionAbsoluteX,
//   positionAbsoluteY,
//   data,
// }: NodeProps<PositionLoggerNode>) {
//   const x = `${Math.round(positionAbsoluteX)}px`;
//   const y = `${Math.round(positionAbsoluteY)}px`;

//   return (
//     // We add this class to use the same styles as React Flow's default nodes.
//     <div className="react-flow__node-default">
//       {data.label && <div>{data.label}</div>}

//       <div>
//         {x} {y}
//       </div>

//       <Handle type="source" position={Position.Bottom} />
//     </div>
//   );
// }

// export const nodeTypes = {
//   'position-logger': PositionLoggerNode,
//   // Add any of your custom nodes here!
// } satisfies NodeTypes;
