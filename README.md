HOW TO RUN:

Windows
open a powershell terminal and run:
.\wayenv\Scripts\activate
cd .\backend\
uvicorn main::app --reload --host 0.0.0.0 --port 8000

open a new powershell terminal and run:
python -m http.server 8080

keep both of these terminals open

Open the website at local host:
localhost:8080 <- index.html for workers
localhost:8080/admin.html <- admin.html for toys assign