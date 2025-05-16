import {
  ReactFlow,
  Background,
  Controls,
  MiniMap,
  addEdge,
  useNodesState,
  useEdgesState,
  type OnConnect,
  useReactFlow,
  ReactFlowProvider,
} from '@xyflow/react';
import type { Node } from '@xyflow/react';

// Import NodeData type from NodeConfigMenu
import { NodeData } from './components/NodeConfigMenu';

import { useCallback, useEffect, useState, useLayoutEffect, MouseEvent } from 'react';
import { jsonToFlow, WorkflowMetadata } from './jsonToFlow';
import { Sidebar } from './components/Sidebar';
import { NodeConfigMenu } from './components/NodeConfigMenu';
import { PlayButton } from './components/PlayButton';
import './components/NodeConfigMenu.css';
import './components/PlayButton.css';
import { nodeTypes } from './components/nodes';
import { edgeTypes } from './components/edges';

import '@xyflow/react/dist/style.css';



function FlowWithLayout() {
  const [workflows, setWorkflows] = useState<string[]>([]);
  const [selected, setSelected] = useState<string | null>(null);
  const [nodes, setNodes, onNodesChange] = useNodesState([]);
  const [edges, setEdges, onEdgesChange] = useEdgesState([]);
  const [selectedNode, setSelectedNode] = useState<Node<NodeData> | null>(null);
  const [workflowMetadata, setWorkflowMetadata] = useState<WorkflowMetadata | null>(null);
  const [allWorkflowsMetadata, setAllWorkflowsMetadata] = useState<Record<string, WorkflowMetadata>>({});
  const [isLoading, setIsLoading] = useState(true);
  const { fitView } = useReactFlow();

  const onConnect: OnConnect = useCallback(
    (connection) => setEdges((edges) => addEdge(connection, edges)),
    [setEdges]
  );

  // Handle node click to show configuration
  const onNodeClick = useCallback((_: MouseEvent, node: Node<NodeData>) => {
    setSelectedNode(node);
  }, []);

  // Close the node configuration menu
  const closeNodeMenu = useCallback(() => {
    setSelectedNode(null);
  }, []);
  
  // Fit view when nodes change
  useLayoutEffect(() => {
    if (nodes.length > 0) {
      window.requestAnimationFrame(() => {
        fitView({ padding: 0.2 });
      });
    }
  }, [nodes.length, fitView]);

  useEffect(() => {
    async function fetchWorkflows() {
      setIsLoading(true);
      try {
        const resp = await fetch('http://localhost:8000/api/workflows');
        if (!resp.ok) {
          throw new Error(`Failed to fetch workflows: ${resp.status} ${resp.statusText}`);
        }
        
        const files = await resp.json();
        setWorkflows(files);
        
        // Auto-select the first workflow if available
        if (files && files.length > 0) {
          setSelected(files[0]);
          
          // Fetch metadata for all workflows - but don't await all of them
          // This prevents one slow request from blocking everything
          files.forEach(async (workflowName: string) => {
            try {
              const response = await fetch(`http://localhost:8000/api/workflows/${workflowName}`);
              if (response.ok) {
                const workflowData = await response.json();
                const flowData = jsonToFlow(workflowData);
                
                // Store metadata in the allWorkflowsMetadata state
                setAllWorkflowsMetadata(prev => ({
                  ...prev,
                  [workflowName]: flowData.metadata
                }));
              }
            } catch (error) {
              console.error(`Error fetching metadata for ${workflowName}:`, error);
            }
          });
        }
      } catch (error) {
        console.error('Error fetching workflows:', error);
      } finally {
        // Always set loading to false, even if there are errors
        setIsLoading(false);
      }
    }
    fetchWorkflows();
  }, []);

  // Store node positions for each workflow
  const [savedNodePositions, setSavedNodePositions] = useState<Record<string, Record<string, { x: number, y: number }>>>({});
  
  // Handle node drag stop to save positions
  const onNodeDragStop = useCallback(
    (_: React.MouseEvent, node: Node) => {
      if (selected) {
        // Update the saved positions for just this node
        setSavedNodePositions(prev => {
          const workflowPositions = prev[selected] || {};
          return {
            ...prev,
            [selected]: {
              ...workflowPositions,
              [node.id]: { x: node.position.x, y: node.position.y }
            }
          };
        });
      }
    },
    [selected]
  );
  
  // Load and convert selected workflow
  useEffect(() => {
    if (!selected) return;
    
    async function fetchAndConvert() {
      const resp = await fetch(`http://localhost:8000/api/workflows/${selected}`);
      if (!resp.ok) return;
      
      const wf = await resp.json();
      const flowData = jsonToFlow(wf);
      
      // Apply saved positions if available
      if (selected && savedNodePositions[selected]) {
        const nodesWithSavedPositions = flowData.nodes.map((node: any) => {
          const savedPosition = savedNodePositions[selected][node.id];
          if (savedPosition) {
            return {
              ...node,
              position: savedPosition
            };
          }
          return node;
        });
        
        setNodes(nodesWithSavedPositions as any);
      } else {
        setNodes(flowData.nodes as any);
      }
      
      setEdges(flowData.edges as any);
      setWorkflowMetadata(flowData.metadata);
    }
    
    fetchAndConvert();
  }, [selected]);
  
  // Handle workflow metadata updates
  const updateWorkflowMetadata = async (updatedMetadata: WorkflowMetadata) => {
    if (!selected) return;
    
    try {
      // Send updated metadata to the backend
      const response = await fetch('http://localhost:8000/api/workflows/update-metadata', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          name: selected,
          metadata: updatedMetadata
        }),
      });
      
      if (response.ok) {
        // Update local state
        setWorkflowMetadata(updatedMetadata);
      } else {
        console.error('Failed to update workflow metadata');
      }
    } catch (error) {
      console.error('Error updating workflow metadata:', error);
    }
  };

  if (isLoading) {
    return (
      <div style={{ 
        display: 'flex', 
        flexDirection: 'column',
        justifyContent: 'center', 
        alignItems: 'center', 
        height: '100vh', 
        background: '#2a2a2a',
        color: '#fff'
      }}>
        <img 
          src="/browseruse.png" 
          alt="Loading..." 
          style={{ 
            width: 120,
            height: 'auto',
            animation: 'spin 2s linear infinite',
            marginBottom: 20
          }} 
        />
        <div style={{ fontSize: 18 }}>Loading workflows...</div>
        <style>{`
          @keyframes spin {
            0% { transform: rotate(0deg); }
            100% { transform: rotate(360deg); }
          }
        `}</style>
      </div>
    );
  }
  
  return (
    <div style={{ display: 'flex', height: '100vh', fontFamily: 'Inter, sans-serif' }}>
      <Sidebar 
        workflows={workflows} 
        onSelect={setSelected} 
        selected={selected} 
        workflowMetadata={workflowMetadata}
        onUpdateMetadata={updateWorkflowMetadata}
        allWorkflowsMetadata={allWorkflowsMetadata}
      />
      <div style={{ flex: 1, background: '#fafbfc', position: 'relative' }}>
        {nodes.length > 0 ? (
          <>
            <ReactFlow 
              nodes={nodes} 
              edges={edges} 
              colorMode="dark"
              nodeTypes={nodeTypes}
              edgeTypes={edgeTypes}
              onNodesChange={onNodesChange}
              onEdgesChange={onEdgesChange}
              onConnect={onConnect}
              onNodeClick={onNodeClick}
              onNodeDragStop={onNodeDragStop}
              fitView
            >
              <Background />
              <MiniMap />
              <Controls />
            </ReactFlow>
            <PlayButton workflowName={selected} workflowMetadata={workflowMetadata} />
          </>
        ) : (
          <div style={{ margin: 32, color: '#888' }}>Select a workflow to visualize</div>
        )}
        {selectedNode && <NodeConfigMenu node={selectedNode} onClose={closeNodeMenu} workflowFilename={selected} />}
      </div>
    </div>
  );
}

// Wrap with ReactFlowProvider to ensure useReactFlow works
export default function App() {
  return (
    <ReactFlowProvider>
      <FlowWithLayout />
    </ReactFlowProvider>
  );
}
