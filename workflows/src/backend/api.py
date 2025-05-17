from fastapi import FastAPI, HTTPException, Body, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
import os
import json
import asyncio
import sys
import uuid
import time
from langchain_openai import ChatOpenAI
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple, NamedTuple

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
LOG_DIR = TMP_DIR / 'logs'

# Ensure log directory exists
LOG_DIR.mkdir(exist_ok=True, parents=True)

# Dictionary to track active tasks with status information
ACTIVE_TASKS = {}

# Dictionary to keep asyncio tasks and cancellation events
WORKFLOW_TASKS: Dict[str, asyncio.Task] = {}
CANCEL_EVENTS: Dict[str, asyncio.Event] = {}

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

def get_log_file_position() -> int:
    """Get the current position in the log file"""
    log_file = LOG_DIR / f"backend.log"
    if not log_file.exists():
        # Create the file if it doesn't exist
        log_file.write_text("")
        return 0
    
    return log_file.stat().st_size

def read_logs_from_position(position: int) -> Tuple[List[str], int]:
    """Read logs from the specified position using efficient file seeking"""
    log_file = LOG_DIR / f"backend.log"
    
    if not log_file.exists():
        return [], 0
    
    current_size = log_file.stat().st_size
    
    # If position is beyond file size, return empty result
    if position >= current_size:
        return [], position
    
    # Use file seeking to efficiently read only new content
    with open(log_file, 'r') as f:
        f.seek(position)
        # Read all logs but filter out lines that start with INFO:
        all_logs = f.readlines()
        new_logs = [line for line in all_logs if not line.strip().startswith('INFO:')]
    
    return new_logs, current_size

async def run_workflow_in_background(task_id: str, workflow_name: str, inputs: Dict, cancel_event: asyncio.Event):
    """Run a workflow in the background and log its progress with cancellation support"""
    log_file = LOG_DIR / f"backend.log"
    
    try:
        # Update task status
        ACTIVE_TASKS[task_id] = {"status": "running", "workflow": workflow_name}
        
        # Write to log file
        with open(log_file, 'a') as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Starting workflow '{workflow_name}'\n")
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Input parameters: {json.dumps(inputs)}\n")
        
        # Check if cancellation requested before starting
        if cancel_event.is_set():
            with open(log_file, 'a') as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Workflow cancelled before execution\n")
            ACTIVE_TASKS[task_id] = {
                "status": "cancelled", 
                "workflow": workflow_name
            }
            return
        
        # Construct the path to the workflow file
        workflow_path = Path(os.path.join(TMP_DIR, workflow_name))
        
        # Load the workflow definition
        workflow_definition_obj = workflow_executor.load_workflow_from_path(workflow_path)
        
        # Execute the workflow
        with open(log_file, 'a') as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Executing workflow...\n")
        
        # Check for cancellation again before execution
        if cancel_event.is_set():
            with open(log_file, 'a') as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Workflow cancelled before execution\n")
            ACTIVE_TASKS[task_id] = {
                "status": "cancelled", 
                "workflow": workflow_name
            }
            return
        
        result = await workflow_executor.run_workflow(
            workflow_definition_obj, 
            inputs, 
            close_browser_at_end=True,
            cancel_event=cancel_event
        )
        
        # Check if cancelled during execution
        if cancel_event.is_set():
            with open(log_file, 'a') as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Workflow execution was cancelled\n")
            ACTIVE_TASKS[task_id] = {
                "status": "cancelled", 
                "workflow": workflow_name
            }
            return
        
        # Format and log the result
        formatted_result = []
        for i, step_result in enumerate(result):
            step_info = {
                "step_id": i,
                "description": step_result.get('description', f'Step {i}'),
                "status": "completed",
                "timestamp": step_result.get('timestamp', 0)
            }
            formatted_result.append(step_info)
            
            # Log step completion
            with open(log_file, 'a') as f:
                f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Completed step {i}: {step_info['description']}\n")
        
        # Update task status to completed
        ACTIVE_TASKS[task_id] = {
            "status": "completed", 
            "workflow": workflow_name,
            "result": formatted_result
        }
        
        # Final log entry
        with open(log_file, 'a') as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Workflow completed successfully with {len(result)} steps\n")
    
    except asyncio.CancelledError:
        # Handle hard cancellation
        with open(log_file, 'a') as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Workflow execution was forcefully cancelled\n")
        
        ACTIVE_TASKS[task_id] = {
            "status": "cancelled", 
            "workflow": workflow_name
        }
        raise
        
    except Exception as e:
        # Log the error
        with open(log_file, 'a') as f:
            f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Error executing workflow: {str(e)}\n")
        
        # Update task status to failed
        ACTIVE_TASKS[task_id] = {
            "status": "failed", 
            "workflow": workflow_name,
            "error": str(e)
        }

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
        # Load the workflow definition to validate inputs
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
        
        # Generate a unique task ID
        task_id = str(uuid.uuid4())
        
        # Create a cancellation event for this task
        cancel_event = asyncio.Event()
        CANCEL_EVENTS[task_id] = cancel_event

        log_position = get_log_file_position()
        
        # Start execution in background
        task = asyncio.create_task(
            run_workflow_in_background(task_id, workflow_name, inputs, cancel_event)
        )
        WORKFLOW_TASKS[task_id] = task
        
        # Set up task cleanup after completion
        task.add_done_callback(
            lambda _: WORKFLOW_TASKS.pop(task_id, None) and CANCEL_EVENTS.pop(task_id, None)
        )
        
        return {
            "success": True,
            "task_id": task_id,
            "workflow": workflow_name,
            "log_position": log_position,
            "message": f"Workflow '{workflow_name}' execution started with task ID: {task_id}"
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error starting workflow: {str(e)}")

@app.get("/api/workflows/logs/{task_id}")
async def get_logs(task_id: str, position: int = 0):
    """Get logs for a specific task from the given position"""
    # Check if the task exists or existed before
    task_info = ACTIVE_TASKS.get(task_id)
    
    # Read new logs since the given position
    new_logs, new_position = read_logs_from_position(position)
    
    return {
        "logs": new_logs,
        "position": new_position,
        "log_position": new_position,  # Add this for compatibility with frontend
        "status": task_info["status"] if task_info else "unknown",
        "result": task_info.get("result", None) if task_info else None,
        "error": task_info.get("error", None) if task_info else None
    }

@app.get("/api/workflows/tasks/{task_id}/status")
async def get_task_status(task_id: str):
    """Get the status of a specific task"""
    task_info = ACTIVE_TASKS.get(task_id)
    
    if not task_info:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    return {
        "task_id": task_id,
        "status": task_info["status"],
        "workflow": task_info["workflow"],
        "result": task_info.get("result", None),
        "error": task_info.get("error", None)
    }

@app.post("/api/workflows/tasks/{task_id}/cancel")
async def cancel_workflow(task_id: str):
    """Cancel a running workflow task"""
    # Check if task exists
    task_info = ACTIVE_TASKS.get(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail=f"Task {task_id} not found")
    
    # Check if task is actually running
    if task_info["status"] != "running":
        return {"success": False, "message": f"Task is already {task_info['status']}"}
    
    # Check if we still have a handle to the task and cancellation event
    task = WORKFLOW_TASKS.get(task_id)
    cancel_event = CANCEL_EVENTS.get(task_id)
    
    if not task:
        # If we don't have a task object but task is marked as running,
        # just update the status
        ACTIVE_TASKS[task_id] = {
            **task_info,
            "status": "cancelled"
        }
    else:
        print(f"Cancelling task {task_id}")
        # First try cooperative cancellation
        if cancel_event:
            cancel_event.set()
        
        # Also attempt hard cancellation as backup
        if not task.done():
            task.cancel()
    
    # Log the cancellation
    log_file = LOG_DIR / f"backend.log"
    with open(log_file, 'a') as f:
        f.write(f"[{time.strftime('%Y-%m-%d %H:%M:%S')}] Workflow execution for task {task_id} cancelled by user\n")
    
    # Update the task status (even if cancellation is still in progress)
    ACTIVE_TASKS[task_id] = {
        **task_info,
        "status": "cancelling"  # Use 'cancelling' status to indicate cancellation in progress
    }
    
    return {"success": True, "message": "Workflow cancellation requested"}