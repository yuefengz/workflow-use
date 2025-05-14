import React from "react";
import { useWorkflow } from "../context/workflow-provider";
import { Button } from "@/components/ui/button";
import { EventViewer } from "./event-viewer";

export const StoppedView: React.FC = () => {
  const { discardAndStartNew, workflow } = useWorkflow();

  const downloadJson = () => {
    if (!workflow) return;

    // Sanitize workflow name for filename
    const safeName = workflow.name
      ? workflow.name.replace(/[^a-z0-9\.\-\_]/gi, "_").toLowerCase()
      : "workflow";

    const blob = new Blob([JSON.stringify(workflow, null, 2)], {
      type: "application/json",
    });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    // Generate filename e.g., my_workflow_name_2023-10-27_10-30-00.json
    const timestamp = new Date()
      .toISOString()
      .replace(/[:.]/g, "-")
      .slice(0, 19);
    // Use sanitized name instead of domain
    a.download = `${safeName}_${timestamp}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
  };

  return (
    <div className="flex flex-col h-full">
      <div className="flex items-center justify-between p-4 border-b border-border">
        <h2 className="text-lg font-semibold">Recording Finished</h2>
        <div className="space-x-2">
          <Button variant="outline" size="sm" onClick={discardAndStartNew}>
            Discard & Start New
          </Button>
          <Button
            size="sm"
            onClick={downloadJson}
            disabled={
              !workflow || !workflow.steps || workflow.steps.length === 0
            }
          >
            Download JSON
          </Button>
        </div>
      </div>
      <div className="flex-grow overflow-hidden p-4">
        <EventViewer />
      </div>
    </div>
  );
};
