import subprocess
import shlex
from fastapi import FastAPI, BackgroundTasks, HTTPException
import os

app = FastAPI()

def run_automation_script():
    """
<<<<<<< HEAD
    Function to execute the auto
    mation script via subprocess.
=======
    Function to execute the automation script via subprocess.
>>>>>>> de3ca197708a6c1a2333d9212db86660c5bf375f
    This runs in an external threadpool, allowing the FastAPI event loop to remain free.
    """
    command_str = "python -m app.Automation.automation_service"
    # shlex.split safely splits the command string into a list for subprocess
    command = shlex.split(command_str) 

    try:
        # Use subprocess.Popen for a non-blocking execution
        process = subprocess.Popen(command, 
                                   stdout=subprocess.PIPE, 
                                   stderr=subprocess.PIPE,
                                   text=True, # Decode output as text
                                   cwd=os.getcwd()) # Ensure it runs from the correct directory

        # Log that the process started; output handling needs a separate mechanism if you need real-time feedback
        print(f"Started automation process PID: {process.pid}")
        # You could also add logic here to manage the process lifetime or log its completion

    except FileNotFoundError:
        print(f"Error: Command not found or module path incorrect: {command_str}")
    except Exception as e:
        print(f"An unexpected error occurred: {e}")

@app.post("/start-automation")
def start_automation_endpoint(background_tasks: BackgroundTasks):
    """
    API endpoint to trigger the automation script in the background.
    """
    background_tasks.add_task(run_automation_script)
    return {"message": "Automation service started in the background", "status": "Accepted"}, 202
