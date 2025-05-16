import React, { useState } from 'react';
import './PlayButton.css';

interface PlayButtonProps {
  workflowName: string | null;
  workflowMetadata: any;
}

interface InputField {
  name: string;
  type: string;
  required: boolean;
  value: any;
}

export const PlayButton: React.FC<PlayButtonProps> = ({ workflowName, workflowMetadata }) => {
  const [isModalOpen, setIsModalOpen] = useState(false);
  const [isRunning, setIsRunning] = useState(false);
  const [result, setResult] = useState<any>(null);
  const [error, setError] = useState<string | null>(null);
  const [inputFields, setInputFields] = useState<InputField[]>([]);

  const openModal = () => {
    if (!workflowName) return;
    
    // Reset state
    setIsModalOpen(true);
    setResult(null);
    setError(null);
    
    // Initialize input fields from workflow metadata
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
    setIsModalOpen(false);
  };

  const handleInputChange = (index: number, value: any) => {
    const updatedFields = [...inputFields];
    updatedFields[index].value = value;
    setInputFields(updatedFields);
  };

  const executeWorkflow = async () => {
    if (!workflowName) return;
    
    // Validate required inputs
    const missingInputs = inputFields.filter(field => field.required && !field.value);
    if (missingInputs.length > 0) {
      setError(`Missing required inputs: ${missingInputs.map(f => f.name).join(', ')}`);
      return;
    }
    
    setIsRunning(true);
    setError(null);
    
    try {
      // Convert input fields to the format expected by the API
      const inputs: Record<string, any> = {};
      inputFields.forEach(field => {
        inputs[field.name] = field.value;
      });
      
      // Call the execute workflow API
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
      
      if (response.ok) {
        setResult(data);
      } else {
        setError(data.detail || 'Failed to execute workflow');
      }
    } catch (err) {
      setError(`Error: ${err instanceof Error ? err.message : String(err)}`);
    } finally {
      setIsRunning(false);
    }
  };

  if (!workflowName) return null;

  return (
    <>
      <button 
        className="play-button" 
        onClick={openModal}
        title="Execute workflow"
      >
        <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 24 24" fill="currentColor" width="24" height="24">
          <path d="M8 5v14l11-7z" />
        </svg>
      </button>
      
      {isModalOpen && (
        <div className="play-modal-overlay">
          <div className="play-modal">
            <div className="play-modal-header">
              <h3>Execute Workflow: {workflowMetadata?.name || workflowName}</h3>
              <button className="close-button" onClick={closeModal}>×</button>
            </div>
            
            <div className="play-modal-content">
              {error && <div className="error-message">{error}</div>}
              
              {!result ? (
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
                      {isRunning ? 'Executing...' : 'Execute Workflow'}
                    </button>
                  </div>
                </>
              ) : (
                <div className="result-container">
                  <div className="result-header">
                    <h4>Execution Complete</h4>
                    <div className="steps-completed">
                      Steps completed: <strong>{result.steps_completed}</strong>
                    </div>
                  </div>
                  
                  <div className="result-data">
                    <pre>{JSON.stringify(result.result, null, 2)}</pre>
                  </div>
                </div>
              )}
            </div>
          </div>
        </div>
      )}
    </>
  );
};
