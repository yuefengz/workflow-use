import { Workflow } from "./workflow-types"; // Assuming Workflow is in this path

export interface BaseMessage {
  source: "BU_BUS"; // To identify messages from our bus
  timestamp: number;
}

export interface WorkflowUpdateMessage extends BaseMessage {
  type: "WORKFLOW_UPDATE";
  payload: Workflow;
}

export interface RecordingStartedMessage extends BaseMessage {
  type: "RECORDING_STARTED";
  payload: {
    message: string;
  };
}

export interface RecordingStoppedMessage extends BaseMessage {
  type: "RECORDING_STOPPED";
  payload: {
    message: string;
  };
}

export interface TerminateCommandMessage extends BaseMessage {
  type: "TERMINATE_COMMAND";
  payload: {
    reason?: string; // Optional reason for termination
  };
}

export type MessageBusMessage =
  | WorkflowUpdateMessage
  | RecordingStartedMessage
  | RecordingStoppedMessage
  | TerminateCommandMessage;

// Helper function to create a loggable string
export function formatBusMessage(message: MessageBusMessage): string {
  return `BU_BUS_MESSAGE: ${JSON.stringify(message)}`;
}
