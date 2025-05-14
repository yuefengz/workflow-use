import asyncio
import json
from typing import Optional  # Added Union

import uvicorn
from fastapi import FastAPI, HTTPException

# Removed Field from pydantic import BaseModel
# Import the new Pydantic models from views.py
from src.recorder.views import (
    HttpRecordingStartedEvent,
    HttpRecordingStoppedEvent,
    HttpWorkflowUpdateEvent,
    RecorderEvent,
)

# In-memory queue to hold incoming typed events
event_queue: asyncio.Queue[RecorderEvent] = asyncio.Queue()  # Typed queue

# FastAPI application
app = FastAPI(title="Browser Event Recorder Server")

# The generic EventPayload class is no longer needed as we use RecorderEvent
# class EventPayload(BaseModel):
#     type: str
#     timestamp: int
#     payload: Dict[str, Any]


@app.post("/event", status_code=202)
async def receive_event(
    event_data: RecorderEvent,  # Use the union of specific Pydantic models
):
    """
    Receives a typed event from the browser extension, validates it against the specific model,
    and puts it into an asynchronous queue for processing.
    """
    try:
        # event_data is already parsed and validated by FastAPI into the correct Pydantic model type
        await event_queue.put(event_data)  # Put the Pydantic model directly
        return {"status": "accepted", "message": "Event queued for processing"}
    except Exception as e:
        print(f"Error queuing event: {e}")
        raise HTTPException(status_code=500, detail=f"Error queuing event: {str(e)}")


async def process_event_queue():
    """
    Continuously processes typed events from the asyncio queue.
    """
    print("Event processing task started. Waiting for events...")
    while True:
        try:
            event: RecorderEvent = await event_queue.get()  # Event is now typed
            print("\n---------- RECORDER EVENT RECEIVED ----------")
            print(f"Type:      {event.type}")  # Access attributes directly
            print(f"Timestamp: {event.timestamp}")

            if isinstance(event, HttpWorkflowUpdateEvent):
                # event.payload is WorkflowPayloadStructure
                print(
                    f'Payload:   Workflow Name: "{event.payload.name}", Steps: {len(event.payload.steps)}'
                )
                # Optionally, print more details about the workflow steps if needed
                # for i, step in enumerate(event.payload.steps):
                #     print(f"    Step {i+1}: Type: {step.type}, URL: {step.url}")
            elif isinstance(
                event, (HttpRecordingStartedEvent, HttpRecordingStoppedEvent)
            ):
                # event.payload is RecordingStatusPayload
                print(f"Payload:   {event.payload.message}")
            else:
                # Should not happen if RecorderEvent union is exhaustive and FastAPI validates correctly
                # For safety, convert unrecognized payload to JSON string
                print(f"Payload:   {json.dumps(event.payload.model_dump(), indent=2)}")
            print("-------------------------------------------")
            event_queue.task_done()
        except asyncio.CancelledError:
            print("Event processing task cancelled.")
            break
        except Exception as e:
            print(f"Error in event processing task: {e}")


processor_task: Optional[asyncio.Task] = None


@app.on_event("startup")
async def startup_event():
    """
    FastAPI startup event handler. Starts the event queue processing task.
    """
    global processor_task
    processor_task = asyncio.create_task(process_event_queue())
    print("FastAPI server started, event processor task is running.")


@app.on_event("shutdown")
async def shutdown_event():
    """
    FastAPI shutdown event handler. Gracefully stops the event queue processing task.
    """
    if processor_task:
        processor_task.cancel()
        try:
            await processor_task
        except asyncio.CancelledError:
            print("Event processor task successfully cancelled during shutdown.")
        except Exception as e:
            print(f"Exception during processor_task shutdown: {e}")
    print("FastAPI server shutting down.")


if __name__ == "__main__":
    print("Starting recorder server on http://127.0.0.1:7331")
    uvicorn.run(
        "recorder:app", host="127.0.0.1", port=7331, log_level="info", reload=True
    )  # Use string for app to enable reload
