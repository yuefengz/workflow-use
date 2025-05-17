import React, { useState } from 'react';
import { WorkflowMetadata } from '../types/Workflow.types';
import { SidebarProps } from '../types/Sidebar.types';
import '../styles/Sidebar.css';

export function Sidebar({ workflows, onSelect, selected, workflowMetadata, onUpdateMetadata, allWorkflowsMetadata = {} }: SidebarProps) {
  const [isEditing, setIsEditing] = useState(false);
  const [editedMetadata, setEditedMetadata] = useState<WorkflowMetadata | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  
  // Initialize edited metadata when entering edit mode
  const handleEditClick = () => {
    setEditedMetadata(workflowMetadata ? { ...workflowMetadata } : null);
    setIsEditing(true);
  };
  
  // Handle input changes
  const handleInputChange = (field: keyof WorkflowMetadata, value: any) => {
    if (editedMetadata) {
      setEditedMetadata({
        ...editedMetadata,
        [field]: value
      });
    }
  };
  
  // Handle form submission
  const handleSubmit = async () => {
    if (!editedMetadata) return;
    
    setIsSubmitting(true);
    try {
      await onUpdateMetadata(editedMetadata);
      setIsEditing(false);
    } catch (error) {
      console.error('Error saving metadata:', error);
    } finally {
      setIsSubmitting(false);
    }
  };
  
  // Cancel editing
  const handleCancel = () => {
    setIsEditing(false);
    setEditedMetadata(null);
  };
  
  // Render workflow details
  const renderWorkflowDetails = () => {
    if (!workflowMetadata || !selected) return null;
    
    if (isEditing) {
      return (
        <div>
          <div className="metadata-input-container">
            <label className="metadata-label">Name</label>
            <input 
              type="text" 
              value={editedMetadata?.name || ''}
              onChange={(e) => handleInputChange('name', e.target.value)}
              className="metadata-input"
            />
          </div>
          
          <div className="metadata-input-container">
            <label className="metadata-label">Version</label>
            <input 
              type="text" 
              value={editedMetadata?.version || ''}
              onChange={(e) => handleInputChange('version', e.target.value)}
              className="metadata-input"
            />
          </div>
          
          <div className="metadata-input-container">
            <label className="metadata-label">Description</label>
            <textarea 
              value={editedMetadata?.description || ''}
              onChange={(e) => handleInputChange('description', e.target.value)}
              className="metadata-textarea"
            />
          </div>
          
          <div className="button-container">
            <button 
              onClick={handleCancel}
              className="cancel-button"
            >
              Cancel
            </button>
            <button 
              onClick={handleSubmit}
              disabled={isSubmitting}
              className={`save-button ${isSubmitting ? 'save-button--submitting' : ''}`}
            >
              {isSubmitting ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      );
    }
    
    return (
      <div>
        <div className="workflow-metadata-section">
          <div className="metadata-label">Description</div>
          <div className="metadata-description">{workflowMetadata.description}</div>
        </div>
        
        {workflowMetadata.input_schema && workflowMetadata.input_schema.length > 0 && (
          <div>
            <div className="metadata-label">Input Parameters</div>
            <ul className="parameter-list">
              {workflowMetadata.input_schema.map((input, index) => (
                <li key={index} className="parameter-item">
                  <span className="parameter-name">{input.name}</span>
                  <span className="parameter-type"> ({input.type})</span>
                  {input.required && <span className="parameter-required"> *required</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  };
  
  const getWorkflowDisplayName = (workflowId: string) => {
    if (selected === workflowId && workflowMetadata) {
      return (
        <>
          {workflowMetadata.name}
          {workflowMetadata.version && 
            <span className="version-label">v{workflowMetadata.version}</span>
          }
        </>
      );
    }
    
    if (allWorkflowsMetadata && allWorkflowsMetadata[workflowId]) {
      return (
        <>
          {allWorkflowsMetadata[workflowId].name}
          {allWorkflowsMetadata[workflowId].version && 
            <span className="version-label">v{allWorkflowsMetadata[workflowId].version}</span>
          }
        </>
      );
    }
    
    // If no metadata is available yet, show a placeholder with loading indicator
    return (
      <span className="workflow-name">
        <span style={{ opacity: 0.7 }}>Loading workflow...</span>
        <span style={{ display: 'none' }}>{workflowId}</span>
      </span>
    );
  };
  
  return (
    <div className="sidebar">
      <div className="sidebar-logo-container">
        <img 
          src="/browseruse.png" 
          alt="Browser Use Logo" 
          className="sidebar-logo"
        />
      </div>
      <h3 className="sidebar-title">Workflows</h3>
      <ul className="sidebar-list">
        {workflows.map((wf) => (
          <React.Fragment key={wf}>
            <li>
              <button
                className={`workflow-button ${wf === selected ? 'workflow-button--active' : ''}`}
                onClick={() => onSelect(wf)}
              >
                {getWorkflowDisplayName(wf)}
              </button>
            </li>

            {workflowMetadata && selected === wf && (
              <li className="workflow-details-container">
                <div className="workflow-details-header">
                  <h4 className="sidebar-details-title">Details</h4>
                  {!isEditing && (
                    <button
                      onClick={handleEditClick}
                      className="edit-button"
                    >
                      Edit
                    </button>
                  )}
                </div>
                {renderWorkflowDetails()}
              </li>
            )}
          </React.Fragment>
        ))}
      </ul>
    </div>
  );
};

export default Sidebar;