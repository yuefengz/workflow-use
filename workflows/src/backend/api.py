from fastapi import FastAPI, HTTPException, Body
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import asyncio
import sys
from langchain_openai import ChatOpenAI
from pathlib import Path
from typing import Dict, Any, Optional, List

# Import the workflow executor
sys.path.append(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))
from src.workflow.service import WorkflowExecutor

app = FastAPI()

llm_instance = None
try:
	llm_instance = ChatOpenAI(model='gpt-4.1-mini')
except Exception as e:
    print(f'Error initializing LLM: {e}. Ensure OPENAI_API_KEY is set.')

# Initialize workflow executor
workflow_executor = WorkflowExecutor(llm_instance)
TMP_DIR = Path('./tmp')

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Your React app's URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/api/workflows")
def list_workflows():
    return [
        f.stem
        for f in TMP_DIR.iterdir()
        if f.is_file() and f.suffix != ".json"
    ]

@app.get("/api/workflows/{name}")
def get_workflow(name: str):
    wf_file = TMP_DIR / f"{name}"
    return wf_file.read_text()

@app.post("/api/workflows/update")
def update_workflow(workflow_data: dict = Body(...)):
    try:
        # Extract the workflow file name and updated data
        workflow_filename = workflow_data.get("filename")  # Changed from 'name' to 'filename'
        node_id = workflow_data.get("nodeId")
        updated_step_data = workflow_data.get("stepData")
        
        if not workflow_filename or not node_id or not updated_step_data:
            return {"success": False, "error": "Missing required fields"}
        
        # Read the existing workflow file using the filename directly
        wf_file = TMP_DIR / workflow_filename  # Use the filename directly
        if not wf_file.exists():
            return {"success": False, "error": f"Workflow file '{workflow_filename}' not found"}
        
        # Parse the workflow content
        workflow_content = json.loads(wf_file.read_text())
        steps = workflow_content.get("steps", [])
        
        # Find and update the specific node's step data
        updated = False
        for idx, step in enumerate(steps):
            print(f"Checking node {idx}")
            print(f"Node ID: {node_id}")
            if int(node_id) == idx:
                print(f"Updating step data for node {node_id}")
                steps[idx] = updated_step_data
                updated = True
                break
        
        if not updated:
            print(f"Node {node_id} not found in workflow")
            return {"success": False, "error": "Node not found in workflow"}
        
        # Write the updated workflow back to the file
        wf_file.write_text(json.dumps(workflow_content, indent=2))
        print(f"Workflow updated successfully")
        
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/workflows/update-metadata")
def update_workflow_metadata(data: dict = Body(...)):
    try:
        # Extract the workflow name and updated metadata
        workflow_name = data.get("name")
        updated_metadata = data.get("metadata")
        
        if not workflow_name or not updated_metadata:
            return {"success": False, "error": "Missing required fields"}
        
        # Read the existing workflow file
        wf_file = TMP_DIR / f"{workflow_name}"
        if not wf_file.exists():
            return {"success": False, "error": "Workflow not found"}
        
        # Parse the workflow content
        workflow_content = json.loads(wf_file.read_text())
        
        # Update the metadata fields
        workflow_content["name"] = updated_metadata.get("name", workflow_content.get("name", ""))
        workflow_content["description"] = updated_metadata.get("description", workflow_content.get("description", ""))
        workflow_content["version"] = updated_metadata.get("version", workflow_content.get("version", ""))
        
        # Only update input_schema if it's provided
        if "input_schema" in updated_metadata:
            workflow_content["input_schema"] = updated_metadata["input_schema"]
        
        # Write the updated workflow back to the file
        wf_file.write_text(json.dumps(workflow_content, indent=2))
        
        return {"success": True}
    except Exception as e:
        return {"success": False, "error": str(e)}

@app.post("/api/workflows/execute")
async def execute_workflow(data: dict = Body(...)):
    # Extract the workflow name and inputs
    workflow_name = data.get("name")
    inputs = data.get("inputs", {})
    
    if not workflow_name:
        raise HTTPException(status_code=400, detail="Missing workflow name")
    
    # Construct the path to the workflow file
    workflow_path = Path(os.path.join(TMP_DIR, workflow_name))
    
    if not workflow_path.exists():
        raise HTTPException(status_code=404, detail=f"Workflow {workflow_name} not found")
    
    try:
        # Load the workflow definition
        workflow_definition_obj = workflow_executor.load_workflow_from_path(workflow_path)
        
        # Validate inputs against the workflow's input schema
        input_definitions = workflow_definition_obj.inputs_def
        missing_required_inputs = []
        
        for input_def in input_definitions:
            if input_def.required and input_def.name not in inputs:
                missing_required_inputs.append(input_def.name)
        
        if missing_required_inputs:
            raise HTTPException(
                status_code=400, 
                detail=f"Missing required inputs: {', '.join(missing_required_inputs)}"
            )
        
        # Execute the workflow
        result = await workflow_executor.run_workflow(
            workflow_definition_obj, 
            inputs, 
            close_browser_at_end=False
        )
        
        # Format the result for the response
        formatted_result = []
        for i, step_result in enumerate(result):
            formatted_result.append({
                "step_id": i,
                "description": step_result.get('description', f'Step {i}'),
                "status": "completed",
                "timestamp": step_result.get('timestamp', 0),
                "output": step_result.get('output')
            })
        
        return {
            "success": True,
            "steps_completed": len(result),
            "result": formatted_result,
            "message": f"Workflow '{workflow_name}' executed successfully with {len(inputs)} input parameters"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error executing workflow: {str(e)}")