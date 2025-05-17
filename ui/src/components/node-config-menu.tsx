import React, { useState, useEffect } from 'react';
import { StepData, NodeConfigMenuProps } from '../types/node-config-menu.types';
import '../styles/node-config-menu.css';

const toTitleCase = (str: string): string => {
  return str.split('_').map(word => {
    return word.charAt(0).toUpperCase() + word.slice(1);
  }).join(' ');
};

export const NodeConfigMenu: React.FC<NodeConfigMenuProps> = ({ node, onClose, workflowFilename }) => {
  const [isEditing, setIsEditing] = useState(false);
  const [editedStepData, setEditedStepData] = useState<StepData | null>(null);
  const [isSubmitting, setIsSubmitting] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [success, setSuccess] = useState(false);
  const [localStepData, setLocalStepData] = useState<StepData | null>(null);
  
  if (!node || !node.data || !node.data.stepData) return null;
  
  useEffect(() => {
    if (node && node.data && node.data.stepData) {
      setLocalStepData(node.data.stepData);
      setIsEditing(false);
      setEditedStepData(null);
      setError(null);
      setSuccess(false);
    }
  }, [node]);
  
  useEffect(() => {
    const handleEscKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') {
        onClose();
      }
    };
    
    document.addEventListener('keydown', handleEscKey);
    
    return () => {
      document.removeEventListener('keydown', handleEscKey);
    };
  }, [onClose]);
  
  const stepData: StepData = localStepData || node.data.stepData;
  
  if (isEditing && !editedStepData) {
    setEditedStepData({...stepData});
  }
  
  const [cssSelectors, setCssSelectors] = useState<string[]>([]);
  const [newSelector, setNewSelector] = useState('');
  
  if (isEditing && editedStepData?.cssSelector && cssSelectors.length === 0) {
    setCssSelectors(editedStepData.cssSelector.split(' '));
  }
  
  const handleInputChange = (field: keyof StepData, value: any) => {
    if (editedStepData) {
      setEditedStepData({
        ...editedStepData,
        [field]: value
      });
    }
  };
  
  const handleAddSelector = () => {
    if (newSelector.trim() !== '') {
      const updatedSelectors = [...cssSelectors, newSelector.trim()];
      setCssSelectors(updatedSelectors);
      setNewSelector('');
      
      // Update the editedStepData
      if (editedStepData) {
        setEditedStepData({
          ...editedStepData,
          cssSelector: updatedSelectors.join(' ')
        });
      }
    }
  };
  
  const handleRemoveSelector = (index: number) => {
    const updatedSelectors = cssSelectors.filter((_, i) => i !== index);
    setCssSelectors(updatedSelectors);
    
    if (editedStepData) {
      setEditedStepData({
        ...editedStepData,
        cssSelector: updatedSelectors.join(' ')
      });
    }
  };
  
  const handleSubmit = async () => {
    if (!editedStepData) return;
    
    if (cssSelectors.length > 0) {
      editedStepData.cssSelector = cssSelectors.join(' ');
    }
    
    setIsSubmitting(true);
    setError(null);
    setSuccess(false);
    
    try {
      const response = await fetch('http://localhost:8000/api/workflows/update', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          filename: workflowFilename,
          nodeId: node.id,
          stepData: editedStepData
        }),
      });
      
      const result = await response.json();
      
      if (result.success) {
        setSuccess(true);
        setIsEditing(false);
        setLocalStepData(editedStepData);
        if (node && node.data) {
          node.data.stepData = editedStepData;
        }
      } else {
        setError(result.error || 'Failed to update workflow');
      }
    } catch (err) {
      setError('Network error: ' + (err instanceof Error ? err.message : String(err)));
    } finally {
      setIsSubmitting(false);
    }
  };
  
  const handleCancel = () => {
    setIsEditing(false);
    setEditedStepData(null);
    setError(null);
    setCssSelectors([]);
    setNewSelector('');
  };

  return (
    <div className="node-config-menu">
      <div className="node-config-menu-header">
        <div>{stepData.description}</div>
        <button onClick={onClose} className="close-button">×</button>
      </div>
      <div className="node-config-menu-content">
        {/* Core fields */}
        <div className="node-config-menu-item">
          <strong>Step Type:</strong> {isEditing ? (
            <select 
              value={editedStepData?.type || 'navigation'}
              onChange={(e) => handleInputChange('type', e.target.value)}
              className="edit-input"
            >
              <option value="navigation">Navigation</option>
              <option value="click">Click</option>
              <option value="select_change">Select Change</option>
              <option value="input">Input</option>
            </select>
          ) : (
            toTitleCase(stepData.type)
          )}
        </div>
        {stepData.tabId !== null && !isEditing && (
          <div className="node-config-menu-item">
            <strong>Tab ID:</strong> {stepData.tabId}
          </div>
        )}
        {/* URL field */}
        {((stepData.url || isEditing) && node.id === '0') && (
          <div className="node-config-menu-item">
            <strong>URL:</strong>
            {isEditing ? (
              <div style={{ marginTop: '4px' }}>
                <input 
                  type="text" 
                  value={editedStepData?.url || ''}
                  onChange={(e) => handleInputChange('url', e.target.value)}
                  className="edit-input full-width"
                />
              </div>
            ) : (
              <a 
                href={stepData.url || ''} 
                target="_blank" 
                rel="noopener noreferrer"
                title={stepData.url || ''}
                style={{ wordBreak: 'break-all' }}
              >
                {stepData.url && stepData.url.length > 40 ? `${stepData.url.substring(0, 37)}...` : stepData.url}
              </a>
            )}
          </div>
        )}
        {(stepData.cssSelector || isEditing) && (
          <div className="node-config-menu-item">
            <strong>CSS Selectors:</strong>
            {isEditing ? (
              <div className="selector-editor">
                <div className="selector-chips">
                  {cssSelectors.map((selector, index) => (
                    <div key={index} className="selector-chip-container">
                      <span 
                        className="selector-chip" 
                        title={selector.length > 40 ? selector : undefined}
                      >
                        {selector.length > 40 ? `${selector.substring(0, 37)}...` : selector}
                      </span>
                      <button 
                        className="selector-remove" 
                        onClick={() => handleRemoveSelector(index)}
                      >
                        ×
                      </button>
                    </div>
                  ))}
                </div>
                <div className="selector-input-container">
                  <input
                    type="text"
                    value={newSelector}
                    onChange={(e) => setNewSelector(e.target.value)}
                    className="edit-input"
                    placeholder="Add selector..."
                  />
                  <button 
                    className="selector-add" 
                    onClick={handleAddSelector}
                  >
                    +
                  </button>
                </div>
              </div>
            ) : (
              <div className="selector-chips">
                {stepData.cssSelector && stepData.cssSelector.split(' ').map((selector, index) => (
                  <span 
                    key={index} 
                    className="selector-chip"
                    title={selector.length > 40 ? selector : undefined}
                  >
                    {selector.length > 40 ? `${selector.substring(0, 37)}...` : selector}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}
        {(stepData.xpath || isEditing) && (
          <div className="node-config-menu-item">
            <strong>XPath:</strong>
            {isEditing ? (
              <div style={{ marginTop: '4px' }}>
                <input
                  type="text"
                  value={editedStepData?.xpath || ''}
                  onChange={(e) => handleInputChange('xpath', e.target.value)}
                  className="edit-input full-width"
                />
              </div>
            ) : (
              <div className="selector-chips">
                <span 
                  className="selector-chip" 
                  title={stepData.xpath}
                  style={{ wordBreak: 'break-all' }}
                >
                  {stepData.xpath && stepData.xpath.length > 40 ? `${stepData.xpath.substring(0, 37)}...` : stepData.xpath}
                </span>
              </div>
            )}
          </div>
        )}
        {(stepData.elementTag || isEditing) && (
          <div className="node-config-menu-item">
            <strong>Element Tag:</strong>
            {isEditing ? (
              <div style={{ marginTop: '4px' }}>
                <input
                  type="text"
                  value={editedStepData?.elementTag || ''}
                  onChange={(e) => handleInputChange('elementTag', e.target.value)}
                  className="edit-input"
                />
              </div>
            ) : (
              <span style={{ marginLeft: '4px' }}>{"<"}{stepData.elementTag}{">"}          </span>
            )}
          </div>
        )}
        {(stepData.elementText || isEditing) && (
          <div className="node-config-menu-item">
            <strong>Element Text:</strong>
            {isEditing ? (
              <div style={{ marginTop: '4px' }}>
                <input
                  type="text"
                  value={editedStepData?.elementText || ''}
                  onChange={(e) => handleInputChange('elementText', e.target.value)}
                  className="edit-input full-width"
                />
              </div>
            ) : (
              <div style={{ wordBreak: 'break-word', marginTop: '4px' }}>{stepData.elementText}</div>
            )}
          </div>
        )}
        {(stepData.selectedText || isEditing) && (
          <div className="node-config-menu-item">
            <strong>Selected Text:</strong>
            {isEditing ? (
              <div style={{ marginTop: '4px' }}>
                <input
                  type="text"
                  value={editedStepData?.selectedText || ''}
                  onChange={(e) => handleInputChange('selectedText', e.target.value)}
                  className="edit-input full-width"
                />
              </div>
            ) : (
              <div style={{ wordBreak: 'break-word', marginTop: '4px' }}>{stepData.selectedText}</div>
            )}
          </div>
        )}
        {(stepData.value || isEditing) && (
          <div className="node-config-menu-item">
            <strong>Value:</strong>
            {isEditing ? (
              <div style={{ marginTop: '4px' }}>
                <input
                  type="text"
                  value={editedStepData?.value || ''}
                  onChange={(e) => handleInputChange('value', e.target.value)}
                  className="edit-input full-width"
                />
              </div>
            ) : (
              <div style={{ wordBreak: 'break-word', marginTop: '4px' }}>{stepData.value}</div>
            )}
          </div>
        )}
        
        {stepData.output && (
          <div className="node-config-menu-data">
            <strong>Output:</strong>
            <pre>{JSON.stringify(stepData.output, null, 2)}</pre>
          </div>
        )}
        <div className="header-buttons">
          {isEditing ? (
            <>
              <button 
                onClick={handleSubmit} 
                disabled={isSubmitting}
                className="edit-button submit-button"
              >
                {isSubmitting ? 'Saving...' : 'Save'}
              </button>
              <button 
                onClick={handleCancel}
                className="edit-button cancel-button-config"
              >
                Cancel
              </button>
            </>
          ) : (
            <button 
              onClick={() => setIsEditing(true)}
              className="edit-button"
            >
              Edit
            </button>
          )}
        </div>
        
        {/* Show success/error messages at the bottom of the modal */}
        {success && <div className="success-message">Changes saved successfully!</div>}
        {error && <div className="error-message">{error}</div>}
      </div>
    </div>
  );
};
