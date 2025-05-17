import React, { useState } from 'react';
import { WorkflowMetadata } from '../types/workflow-layout.types';
import { SidebarProps } from '../types/sidebar.types';

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
          <div className="mb-2">
            <label className="block text-xs text-[#aaa] mb-1">Name</label>
            <input 
              type="text" 
              value={editedMetadata?.name || ''}
              onChange={(e) => handleInputChange('name', e.target.value)}
              className="w-full bg-[#333] border border-[#555] text-white p-1.5 rounded box-border text-xs"
            />
          </div>
          
          <div className="mb-2">
            <label className="block text-xs text-[#aaa] mb-1">Version</label>
            <input 
              type="text" 
              value={editedMetadata?.version || ''}
              onChange={(e) => handleInputChange('version', e.target.value)}
              className="w-full bg-[#333] border border-[#555] text-white p-1.5 rounded box-border text-xs"
            />
          </div>
          
          <div className="mb-2">
            <label className="block text-xs text-[#aaa] mb-1">Description</label>
            <textarea 
              value={editedMetadata?.description || ''}
              onChange={(e) => handleInputChange('description', e.target.value)}
              className="w-full bg-[#333] border border-[#555] text-white p-1.5 rounded min-h-[60px] resize-y box-border text-xs"
            />
          </div>
          
          <div className="flex gap-2 justify-end">
            <button 
              onClick={handleCancel}
              className="bg-[#444] border-none text-white py-1.5 px-3 rounded cursor-pointer text-xs"
            >
              Cancel
            </button>
            <button 
              onClick={handleSubmit}
              disabled={isSubmitting}
              className={`bg-blue-400 hover:bg-blue-500 border-none text-xs text-white py-1.5 px-3 rounded cursor-pointer ${isSubmitting ? 'opacity-70' : ''}`}
            >
              {isSubmitting ? 'Saving...' : 'Save'}
            </button>
          </div>
        </div>
      );
    }
    
    return (
      <div>
        <div className="mb-2">
          <div className="text-xs text-[#aaa] mb-1">Description</div>
          <div className="text-xs">{workflowMetadata.description}</div>
        </div>
        
        {workflowMetadata.input_schema && workflowMetadata.input_schema.length > 0 && (
          <div>
            <div className="text-xs text-[#aaa] mb-1">Input Parameters</div>
            <ul className="m-0 p-0 pl-4 text-xs">
              {workflowMetadata.input_schema.map((input, index) => (
                <li key={index} className="mb-1">
                  <span className="text-[#7ac5ff]">{input.name}</span>
                  <span className="text-[#aaa] text-xs"> ({input.type})</span>
                  {input.required && <span className="text-[#ff7a7a] text-xs"> *</span>}
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
          <span className="text-md">{workflowMetadata.name}</span>
          {workflowMetadata.version && 
            <span className="text-xs text-[#888] ml-1.5">v{workflowMetadata.version}</span>
          }
        </>
      );
    }
    
    if (allWorkflowsMetadata && allWorkflowsMetadata[workflowId]) {
      return (
        <>
          <span className="text-md">{allWorkflowsMetadata[workflowId].name}</span>
          {allWorkflowsMetadata[workflowId].version && 
            <span className="text-xs text-[#888] ml-1.5">v{allWorkflowsMetadata[workflowId].version}</span>
          }
        </>
      );
    }
    
    // If no metadata is available yet, show a placeholder with loading indicator
    return (
      <span className="text-[#ccc]">
        <span className="opacity-70">Loading workflow...</span>
        <span className="hidden">{workflowId}</span>
      </span>
    );
  };
  
  return (
    <div className="w-[250px] border-r border-[#444] p-3 bg-[#2a2a2a] text-white flex flex-col overflow-auto box-border">
      <div className="flex justify-center mb-4 items-center">
        <img 
          src="/browseruse.png" 
          alt="Browser Use Logo" 
          className="max-w-[80%] h-auto max-h-[60px]"
        />
      </div>
      <h3 className="mt-0 text-lg text-[#ddd]">Workflows</h3>
      <ul className="list-none p-0 m-0">
        {workflows.map((wf) => (
          <React.Fragment key={wf}>
            <li>
              <button
                className={`bg-transparent border-none w-full text-left py-1.5 px-0 cursor-pointer ${wf === selected ? 'font-semibold text-[#7ac5ff]' : 'text-[#ccc]'}`}
                onClick={() => onSelect(wf)}
              >
                {getWorkflowDisplayName(wf)}
              </button>
            </li>

            {workflowMetadata && selected === wf && (
              <li className="py-2 pl-4 pr-0 border-l border-[#444] my-1 ml-1">
                <div className="flex justify-between items-center mb-2">
                  <h4 className="m-0 text-sm text-[#ddd]">Details</h4>
                  {!isEditing && (
                    <button
                      onClick={handleEditClick}
                      className="bg-[#444] border-none text-white py-1 px-2 rounded cursor-pointer text-xs"
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