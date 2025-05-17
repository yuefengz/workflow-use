import React, { useState } from 'react';
import LogViewer from './LogViewer';
import { PlayButtonProps, InputField } from '../types/playButton.types';
import '../styles/PlayButton.css';

export const PlayButton: React.FC<PlayButtonProps> = ({ workflowName, workflowMetadata }) => {
  const [showModal, setShowModal] = useState<boolean>(false);
  const [showLogViewer, setShowLogViewer] = useState<boolean>(false);
  const [isRunning, setIsRunning] = useState<boolean>(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [inputFields, setInputFields] = useState<InputField[]>([]);
  const [taskId, setTaskId] = useState<string | null>(null);
  const [logPosition, setLogPosition] = useState<number>(0);
  const [workflowStatus, setWorkflowStatus] = useState<string>('idle');

  const openModal = () => {
    if (!workflowName) return;
    
    setShowModal(true);
    setResult(null);
    setError(null);

    if (workflowMetadata && workflowMetadata.input_schema) {
      const fields = workflowMetadata.input_schema.map((input: any) => ({
        name: input.name,
        type: input.type,
        required: input.required,
        value: input.type === 'boolean' ? false : ''
      }));
      setInputFields(fields);
    } else {
      setInputFields([]);
    }
  };

  const closeModal = () => {
    setShowModal(false);
    
    if (!isRunning) {
      resetState();
    }
  };
  
  const closeLogViewer = () => {
    setShowLogViewer(false);
    resetState();
  };

  const resetState = () => {
    setIsRunning(false);
    setResult(null);
    setError(null);
    setInputFields([]);
    setTaskId(null);
    setLogPosition(0);
    setWorkflowStatus('idle');
  };

  const handleInputChange = (index: number, value: any) => {
    const updatedFields = [...inputFields];
    updatedFields[index].value = value;
    setInputFields(updatedFields);
  };

  const executeWorkflow = async () => {
    if (!workflowName) return;
    
    const missingInputs = inputFields.filter(field => field.required && !field.value);
    if (missingInputs.length > 0) {
      setError(`Missing required inputs: ${missingInputs.map(f => f.name).join(', ')}`);
      return;
    }
    
    setIsRunning(true);
    setError(null);
    setTaskId(null);
    setLogPosition(0);
    setResult(null);
    setWorkflowStatus('idle');
    
    try {
      const inputs: Record<string, any> = {};
      inputFields.forEach(field => {
        inputs[field.name] = field.value;
      });
      
      const response = await fetch('http://localhost:8000/api/workflows/execute', {
          method: 'POST',
          headers: {
            'Content-Type': 'application/json',
          },
          body: JSON.stringify({
          name: workflowName,
          inputs
        }),
      });

      const data = await response.json();
      setTaskId(data.task_id);
      setLogPosition(data.log_position);
      setIsRunning(true);
      setShowLogViewer(true);
      setShowModal(false);
    } catch (err) {
      console.error('Failed to execute workflow:', err);
      setError('An error occurred while executing the workflow');
    }
  };
  
  const handleStatusChange = (status: string) => {
    setWorkflowStatus(status);
    
    if (status === 'completed' || status === 'failed' || status === 'cancelled') {
      setIsRunning(false);
    }
  };
  
  const handleCancelWorkflow = () => {
    setWorkflowStatus('cancelling');
  };
  
  const handleWorkflowComplete = (resultData: any) => {
    setResult({
      success: true,
      steps_completed: resultData.length,
      result: resultData
    });
  };
  
  const handleWorkflowError = (errorMessage: string) => {
    setError(errorMessage);
  };

  if (!workflowName) return null;

  return (
    <div className="play-button-container">
      <button 
        className="play-button" 
        onClick={openModal}
        title="Execute workflow"
      >
        <span className="play-icon">▶</span>
      </button>
      
      {/* Parameters Input Modal */}
      {showModal && (
        <div className="play-modal-overlay">
          <div className="play-modal">
            <div className="play-modal-header">
              <h3>Execute Workflow: {workflowMetadata?.name || workflowName}</h3>
              <button className="close-button" onClick={closeModal}>×</button>
            </div>
            
            <div className="play-modal-content">
              {error && <div className="error-message">{error}</div>}
              
              {/* Input Fields Section */}
              <>
                {inputFields.length > 0 ? (
                  <div className="input-fields">
                    <h4>Input Parameters</h4>
                    {inputFields.map((field, index) => (
                      <div key={field.name} className="input-field">
                        <label>
                          {field.name}
                          {field.required && <span className="required">*</span>}
                          <span className="type-info">({field.type})</span>
                        </label>
                        {field.type === 'boolean' ? (
                          <input
                            type="checkbox"
                            checked={field.value}
                            onChange={(e) => handleInputChange(index, e.target.checked)}
                          />
                        ) : field.type === 'number' ? (
                          <input
                            type="number"
                            value={field.value}
                            onChange={(e) => handleInputChange(index, e.target.value)}
                            className="input-control"
                          />
                        ) : (
                          <input
                            type="text"
                            value={field.value}
                            onChange={(e) => handleInputChange(index, e.target.value)}
                            className="input-control"
                          />
                        )}
                      </div>
                    ))}
                  </div>
                ) : (
                  <p>No input parameters required for this workflow.</p>
                )}
                
                <div className="modal-actions">
                  <button 
                    className="cancel-button" 
                    onClick={closeModal}
                  >
                    Cancel
                  </button>
                  <button 
                    className="execute-button" 
                    onClick={executeWorkflow}
                    disabled={isRunning}
                  >
                    Execute Workflow
                  </button>
                </div>
              </>
            </div>
          </div>
        </div>
      )}
      
      {/* Separate Log Viewer */}
      {showLogViewer && taskId && (
        <div className="log-viewer-overlay">
          <div className="log-viewer-modal">
            <div className="log-viewer-header">
              <div>Workflow Execution {workflowStatus !== 'running' ? `(${workflowStatus.charAt(0).toUpperCase() + workflowStatus.slice(1)})` : ''}</div>
            </div>
            
            <div className="log-viewer-content">
              <LogViewer 
                taskId={taskId} 
                initialPosition={logPosition}
                onStatusChange={handleStatusChange}
                onComplete={handleWorkflowComplete}
                onError={handleWorkflowError}
                onCancel={handleCancelWorkflow}
                onClose={closeLogViewer}
              />
            </div>
          </div>
        </div>
      )}
      
      {/* Results Modal (only shown if we want a separate results view) */}
      {false && result && (
        <div className="play-modal-overlay">
          <div className="play-modal">
            <div className="play-modal-header">
              <h3>Execution Results</h3>
              <button className="close-button" onClick={closeModal}>×</button>
            </div>
            
            <div className="play-modal-content">
              <div className="result-container">
                <div className="result-header">
                  <h4>Execution Complete</h4>
                  <div className="steps-completed">
                    Steps completed: <strong>{result.steps_completed}</strong>
                  </div>
                </div>
                
                <div className="result-output">
                  <h5>Output:</h5>
                  <pre>{JSON.stringify(result.output, null, 2)}</pre>
                </div>
                
                <div className="modal-actions">
                  <button 
                    className="close-button" 
                    onClick={closeModal}
                  >
                    Close
                  </button>
                </div>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
