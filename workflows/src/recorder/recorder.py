import asyncio
import json
import pathlib
from typing import Optional

import uvicorn
from fastapi import FastAPI, HTTPException
from playwright.async_api import async_playwright, BrowserContext

# Import the Pydantic models from views.py
from src.recorder.views import (
    HttpRecordingStartedEvent,
    HttpRecordingStoppedEvent,  # Ensure this is imported as it's used
    HttpWorkflowUpdateEvent,
    RecorderEvent,
)

# --- Global State ---
event_queue: asyncio.Queue[RecorderEvent] = asyncio.Queue()
last_workflow_update_event: Optional[HttpWorkflowUpdateEvent] = None
playwright_context_global: Optional[BrowserContext] = None
app = FastAPI(title="Browser Event Recorder Server")

# Playwright and Path Configuration
SCRIPT_DIR = pathlib.Path(__file__).resolve().parent
# Corrected EXT_DIR path based on user feedback
EXT_DIR = SCRIPT_DIR.parent.parent.parent / "extension" / ".output" / "chrome-mv3"
# Corrected USER_DATA_DIR name based on user feedback
USER_DATA_DIR = SCRIPT_DIR / "user_data_dir"

# Flag and lock for ensuring final workflow is printed only once
final_workflow_printed_lock = asyncio.Lock()
final_workflow_printed_flag = False


# --- Helper to Print Final Workflow & Optionally Close Browser ---
async def print_final_workflow_if_any(trigger_reason: str):
    global \
        last_workflow_update_event, \
        final_workflow_printed_flag, \
        playwright_context_global

    printed_this_call = False
    async with final_workflow_printed_lock:
        if not final_workflow_printed_flag and last_workflow_update_event:
            print(f"\n--- FINAL WORKFLOW CAPTURED (Trigger: {trigger_reason}) ---")
            try:
                # Assuming WorkflowDefinitionSchema has model_dump_json
                print(last_workflow_update_event.payload.model_dump_json(indent=2))
            except AttributeError:
                print(
                    "Error: last_workflow_update_event.payload does not have model_dump_json. Raw data:"
                )
                print(last_workflow_update_event.payload)
            print("---------------------------------------------------\n")
            final_workflow_printed_flag = True
            printed_this_call = True  # Mark that this specific call did the printing

    # If printing was done by *this call* due to RecordingStoppedEvent, close the browser.
    if printed_this_call and trigger_reason == "RecordingStoppedEvent":
        if playwright_context_global:
            print(
                "Recording stopped and workflow printed, attempting to close browser..."
            )
            try:
                await playwright_context_global.close()
                print(
                    "Browser close command issued successfully via RecordingStoppedEvent."
                )
            except Exception as e_close_browser:
                print(
                    f"Error attempting to close browser via context after recording stop: {e_close_browser}"
                )
        else:
            print(
                "Recording stopped, workflow printed, but no active Playwright browser context to close."
            )


# --- FastAPI Endpoint ---
@app.post("/event", status_code=202)
async def receive_event(event_data: RecorderEvent):
    """
    Receives a typed event from the browser extension, validates it,
    and puts it into an asynchronous queue for processing.
    """
    global last_workflow_update_event
    try:
        if isinstance(event_data, HttpWorkflowUpdateEvent):
            last_workflow_update_event = (
                event_data  # Persist the latest workflow update
            )
        await event_queue.put(event_data)
        return {"status": "accepted", "message": "Event queued for processing"}
    except Exception as e:
        print(f"Error queuing event: {e}")
        raise HTTPException(status_code=500, detail=f"Error queuing event: {str(e)}")


# --- Event Queue Processing ---
async def process_event_queue():
    """
    Continuously processes typed events from the asyncio queue.
    """
    print("Event processing task started. Waiting for events...")
    while True:
        try:
            event: RecorderEvent = await event_queue.get()
            print("\n---------- RECORDER EVENT RECEIVED ----------")
            print(f"Type:      {event.type}")
            print(f"Timestamp: {event.timestamp}")

            if isinstance(event, HttpWorkflowUpdateEvent):
                # Payload is WorkflowDefinitionSchema (handled by type hint)
                print(
                    f'Payload:   Workflow Name: "{event.payload.name}", Steps: {len(event.payload.steps)}'
                )
                # Update the global state (already done in receive_event, but good for clarity if logic moves)
                # global last_workflow_update_event
                # last_workflow_update_event = event
            elif isinstance(event, HttpRecordingStartedEvent):
                print(f"Payload:   {event.payload.message}")
            elif isinstance(event, HttpRecordingStoppedEvent):
                print(f"Payload:   {event.payload.message}")
                # Trigger printing final workflow on recording stopped
                await print_final_workflow_if_any("RecordingStoppedEvent")
            else:
                # Should not happen if RecorderEvent union is exhaustive
                print(f"Payload:   {json.dumps(event.payload.model_dump(), indent=2)}")
            print("-------------------------------------------")
            event_queue.task_done()
        except asyncio.CancelledError:
            print("Event processing task cancelled.")
            break
        except Exception as e:
            print(f"Error in event processing task: {e}")
            # Add a small delay or log more before continuing if needed


# --- Playwright Browser Launch ---
async def launch_playwright_with_extension():
    """
    Launches a Playwright browser with the specified extension and handles its closure.
    """
    global playwright_context_global
    print(f"Attempting to load extension from: {EXT_DIR}")
    if not EXT_DIR.exists() or not EXT_DIR.is_dir():
        print(f"ERROR: Extension directory not found or not a directory: {EXT_DIR}")
        print("Please ensure the extension is built and the path is correct.")
        return

    USER_DATA_DIR.mkdir(parents=True, exist_ok=True)
    print(f"Using Playwright user data directory: {USER_DATA_DIR}")

    async with async_playwright() as p:
        launched_context: Optional[BrowserContext] = None
        try:
            launched_context = await p.chromium.launch_persistent_context(
                str(USER_DATA_DIR.resolve()),  # Ensure path is string
                headless=False,
                args=[
                    f"--disable-extensions-except={str(EXT_DIR.resolve())}",
                    f"--load-extension={str(EXT_DIR.resolve())}",
                ],
            )
            playwright_context_global = launched_context  # Assign to global
            print(
                "Playwright browser launched. Close browser or stop recording to see final workflow."
            )

            await launched_context.wait_for_event("close", timeout=0)
            print(
                "Playwright context 'close' event detected (e.g., browser manually closed or by script)."
            )

        except asyncio.CancelledError:
            print("Playwright task was cancelled.")
            if (
                playwright_context_global
            ):  # Check global, as launched_context might not be set if cancelled early
                print(
                    "Playwright task cancelled, attempting to close browser context..."
                )
                try:
                    await playwright_context_global.close()
                    print("Browser context closed due to Playwright task cancellation.")
                except Exception as e_cancel_close:
                    print(
                        f"Error closing browser context during Playwright task cancellation: {e_cancel_close}"
                    )
            raise
        except Exception as e:
            print(f"Error during Playwright browser launch or operation: {e}")
            if playwright_context_global:
                print(f"Error occurred: {e}. Attempting to close browser context...")
                try:
                    await playwright_context_global.close()
                    print("Browser context closed due to error in Playwright task.")
                except Exception as e_err_close:
                    print(
                        f"Further error closing browser context after initial error: {e_err_close}"
                    )
        finally:
            print(
                "Playwright task finalization (finally block). Triggering final workflow print if needed."
            )
            playwright_context_global = None  # Clear the global reference
            await print_final_workflow_if_any("PlaywrightTaskEnded")


# --- FastAPI App Lifecycle ---
processor_task: Optional[asyncio.Task] = None


@app.on_event("startup")
async def startup_event():
    global processor_task
    processor_task = asyncio.create_task(process_event_queue())
    print("FastAPI server started, event processor task is running.")


@app.on_event("shutdown")
async def shutdown_event():
    if processor_task:
        processor_task.cancel()
        try:
            await processor_task
        except asyncio.CancelledError:
            print("Event processor task successfully cancelled during shutdown.")
        except Exception as e:
            print(f"Exception during processor_task shutdown: {e}")
    # Ensure final workflow is printed on graceful server shutdown too, if not already done
    await print_final_workflow_if_any("ServerShutdown")
    print("FastAPI server shutting down.")


# --- Main Application Setup ---
async def run_fastapi_server():
    config = uvicorn.Config(app, host="127.0.0.1", port=7331, log_level="info")
    server = uvicorn.Server(config)
    # server.should_exit is a flag uvicorn uses for graceful shutdown
    # We'll handle shutdown via main's try/finally and task cancellation
    await server.serve()


async def main():
    print("Starting main application...")
    # These tasks will run concurrently
    server_task = asyncio.create_task(run_fastapi_server())
    playwright_task = asyncio.create_task(launch_playwright_with_extension())

    try:
        # Gather will wait for all tasks to complete.
        # If one errors, it might cancel others depending on return_exceptions.
        # Here, we want them to run until browser closes or server is stopped (Ctrl+C).
        await asyncio.gather(server_task, playwright_task)
    except KeyboardInterrupt:
        print("\nKeyboard interrupt received. Shutting down all tasks...")
    except Exception as e:
        print(f"An unexpected error occurred in main: {e}")
    finally:
        print("Main application attempting to clean up...")

        # Attempt to print workflow before cancelling tasks if browser closed but server running
        await print_final_workflow_if_any("MainCleanup")

        if playwright_task and not playwright_task.done():
            playwright_task.cancel()
        if server_task and not server_task.done():
            # Uvicorn server needs signal to shutdown if not already exiting
            # server.should_exit = True # This might be specific to how server is run
            server_task.cancel()  # Standard task cancellation

        # Wait for tasks to acknowledge cancellation (or complete)
        await asyncio.gather(server_task, playwright_task, return_exceptions=True)
        print("All tasks hopefully shut down. Exiting.")


if __name__ == "__main__":
    asyncio.run(main())
