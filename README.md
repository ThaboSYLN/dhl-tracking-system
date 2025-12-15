## Steps on how to run the app
  - Create a virtual environment
      - `py -3.12 -m venv venv`
  - Navigate to the virtual environment
      - venv\Scripts\activate
  - Run the automation process
      - python -m app.Automation.automation_service
  - Run the live server
      - uvicorn app.main:app --reload
 
