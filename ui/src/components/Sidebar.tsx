import React, { useState } from 'react';
import { WorkflowMetadata } from '../jsonToFlow';

interface SidebarProps {
  workflows: string[];
  onSelect: (wf: string) => void;
  selected: string | null;
  workflowMetadata: WorkflowMetadata | null;
  onUpdateMetadata: (metadata: WorkflowMetadata) => Promise<void>;
  allWorkflowsMetadata?: Record<string, WorkflowMetadata>;
}

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
        <div style={{ marginBottom: 16 }}>
          <div style={{ marginBottom: 8 }}>
            <label style={{ display: 'block', fontSize: '12px', color: '#aaa', marginBottom: 4 }}>Name</label>
            <input 
              type="text" 
              value={editedMetadata?.name || ''}
              onChange={(e) => handleInputChange('name', e.target.value)}
              style={{
                width: '100%',
                background: '#333',
                border: '1px solid #555',
                color: '#fff',
                padding: '6px',
                borderRadius: '4px',
                boxSizing: 'border-box'
              }}
            />
          </div>
          
          <div style={{ marginBottom: 8 }}>
            <label style={{ display: 'block', fontSize: '12px', color: '#aaa', marginBottom: 4 }}>Version</label>
            <input 
              type="text" 
              value={editedMetadata?.version || ''}
              onChange={(e) => handleInputChange('version', e.target.value)}
              style={{
                width: '100%',
                background: '#333',
                border: '1px solid #555',
                color: '#fff',
                padding: '6px',
                borderRadius: '4px',
                boxSizing: 'border-box'
              }}
            />
          </div>
          
          <div style={{ marginBottom: 8 }}>
            <label style={{ display: 'block', fontSize: '12px', color: '#aaa', marginBottom: 4 }}>Description</label>
            <textarea 
              value={editedMetadata?.description || ''}
              onChange={(e) => handleInputChange('description', e.target.value)}
              style={{
                width: '100%',
                background: '#333',
                border: '1px solid #555',
                color: '#fff',
                padding: '6px',
                borderRadius: '4px',
                minHeight: '60px',
                resize: 'vertical',
                boxSizing: 'border-box'
              }}
            />
          </div>
          
          <div style={{ display: 'flex', gap: 8, justifyContent: 'flex-end' }}>
            <button 
              onClick={handleCancel}
              style={{
                background: '#555',
                border: 'none',
                color: '#fff',
                padding: '6px 12px',
                borderRadius: '4px',
                cursor: 'pointer'
              }}
            >
              Cancel
            </button>
            <button 
              onClick={handleSubmit}
              disabled={isSubmitting}
              style={{
                background: '#2a7ac5',
                border: 'none',
                color: '#fff',
                padding: '6px 12px',
                borderRadius: '4px',
                cursor: 'pointer',
                opacity: isSubmitting ? 0.7 : 1
              }}
            >
              {isSubmitting ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      );
    }
    
    return (
      <div>
        <div style={{ marginBottom: 8 }}>
          <div style={{ fontSize: '12px', color: '#aaa' }}>Description</div>
          <div style={{ fontSize: '13px' }}>{workflowMetadata.description}</div>
        </div>
        
        {workflowMetadata.input_schema && workflowMetadata.input_schema.length > 0 && (
          <div>
            <div style={{ fontSize: '12px', color: '#aaa', marginBottom: 4 }}>Input Parameters</div>
            <ul style={{ margin: 0, padding: 0, paddingLeft: 16, fontSize: '13px' }}>
              {workflowMetadata.input_schema.map((input, index) => (
                <li key={index} style={{ marginBottom: 4 }}>
                  <span style={{ color: '#7ac5ff' }}>{input.name}</span>
                  <span style={{ color: '#aaa', fontSize: '11px' }}> ({input.type})</span>
                  {input.required && <span style={{ color: '#ff7a7a', fontSize: '11px' }}> *required</span>}
                </li>
              ))}
            </ul>
          </div>
        )}
      </div>
    );
  };
  
  // Function to get workflow display name
  const getWorkflowDisplayName = (workflowId: string) => {
    // For the selected workflow, use its metadata name
    if (selected === workflowId && workflowMetadata) {
      return (
        <>
          {workflowMetadata.name}
          {workflowMetadata.version && 
            <span style={{ fontSize: '11px', color: '#888', marginLeft: '5px' }}>v{workflowMetadata.version}</span>
          }
        </>
      );
    }
    
    // For non-selected workflows, use the cached metadata if available
    if (allWorkflowsMetadata && allWorkflowsMetadata[workflowId]) {
      return (
        <>
          {allWorkflowsMetadata[workflowId].name}
          {allWorkflowsMetadata[workflowId].version && 
            <span style={{ fontSize: '11px', color: '#888', marginLeft: '5px' }}>v{allWorkflowsMetadata[workflowId].version}</span>
          }
        </>
      );
    }
    
    // If no metadata is available, show the filename
    return <span style={{ color: '#ccc' }}>{workflowId}</span>;
  };
  
  return (
    <div style={{ 
      width: 250, 
      borderRight: '1px solid #444', 
      padding: 12, 
      background: '#2a2a2a',
      color: '#fff',
      display: 'flex',
      flexDirection: 'column',
      overflow: 'auto',
      boxSizing: 'border-box'
    }}>
      <div style={{ 
        display: 'flex', 
        justifyContent: 'center', 
        marginBottom: 16,
        alignItems: 'center'
      }}>
        <img 
          src="/browseruse.png" 
          alt="Browser Use Logo" 
          style={{ 
            maxWidth: '80%', 
            height: 'auto',
            maxHeight: 60
          }} 
        />
      </div>
      <h3 style={{ marginTop: 0, fontSize: '16px', color: '#ddd' }}>Workflows</h3>
      <ul style={{ listStyle: 'none', padding: 0, margin: 0 }}>
        {workflows.map((wf) => (
          <React.Fragment key={wf}>
            <li>
              <button
                style={{
                  background: 'transparent',
                  border: 'none',
                  width: '100%',
                  textAlign: 'left',
                  padding: '5px 0',
                  cursor: 'pointer',
                  fontWeight: wf === selected ? 600 : 400,
                  color: wf === selected ? '#7ac5ff' : '#ccc',
                }}
                onClick={() => onSelect(wf)}
              >
                {getWorkflowDisplayName(wf)}
              </button>
            </li>

            {workflowMetadata && selected === wf && (
              <li
                style={{
                  padding: '8px 0 12px 16px',
                  borderLeft: '1px solid #444',
                  margin: '4px 0 8px 4px',
                }}
              >
                <div
                  style={{
                    display: 'flex',
                    justifyContent: 'space-between',
                    alignItems: 'center',
                    marginBottom: 8,
                  }}
                >
                  <h4 style={{ margin: 0, fontSize: '14px', color: '#ddd' }}>Details</h4>
                  {!isEditing && (
                    <button
                      onClick={handleEditClick}
                      style={{
                        background: '#444',
                        border: 'none',
                        color: '#fff',
                        padding: '4px 8px',
                        borderRadius: '4px',
                        cursor: 'pointer',
                        fontSize: '12px',
                      }}
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