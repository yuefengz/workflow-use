import React from 'react';
import '../styles/no-workflow-message.css';

const NoWorkflowsMessage: React.FC = () => {
  return (
    <div className="no-workflows-container">
      <img 
        src="/browseruse.png" 
        alt="Browser Use Logo" 
        className="no-workflows-logo"
      />
      <h2 className="no-workflows-title">No Workflows Found</h2>
      <p className="no-workflows-text">
        To get started with Workflow Use, you need to first create a workflow 
        or place an existing workflow file in the <code>workflows/tmp</code> folder.
      </p>
      <p className="no-workflows-instruction">
        Once you've added a workflow file, refresh this page to visualize and interact with it. For more information, checkout out the documentation below.
      </p>
      <a 
        href="https://github.com/browser-use/workflow-use" 
        target="_blank" 
        rel="noopener noreferrer"
        className="documentation-button"
      >
        Learn More
      </a>
    </div>
  );
};

export default NoWorkflowsMessage;
