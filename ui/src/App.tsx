import { ReactFlowProvider } from '@xyflow/react';
import '@xyflow/react/dist/style.css';
import WorkflowLayout from './components/WorkflowLayout';

export default function App() {
  return (
    <ReactFlowProvider>
      <WorkflowLayout />
    </ReactFlowProvider>
  );
}
