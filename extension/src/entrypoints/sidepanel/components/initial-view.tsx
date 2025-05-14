import React from "react";
import { useWorkflow } from "../context/workflow-provider";
import { Button } from "@/components/ui/button"; // Reverted to alias path

export const InitialView: React.FC = () => {
  const { startRecording } = useWorkflow();

  return (
    <div className="flex flex-col items-center justify-center h-full space-y-4">
      <h2 className="text-lg font-semibold">Record a Workflow</h2>

      <Button onClick={startRecording}>Start Recording</Button>
    </div>
  );
};
