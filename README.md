SETUP:

1. Copy the example config files and fill in your own values:
   cp config.example.js config.js   <- Supabase URL, publishable key, backend URL
   cp .env.example .env             <- backend settings

   config.js and .env are gitignored, so your values stay local.

2. Secure Supabase:
   - Run supabase/policies.sql in the Supabase SQL editor (enables RLS, read-only for anonymous users)
   - Authentication > Sign In / Providers: turn off "Allow new users to sign up"
   - Authentication > Users: add a user for each person who should sign in

3. Install backend dependencies:
   python -m venv wayenv
   pip install -r backend/requirements.txt

HOW TO RUN:

Windows
open a powershell terminal and run:
.\wayenv\Scripts\activate
cd .\backend\
uvicorn main:app --reload --host 0.0.0.0 --port 8000

open a new powershell terminal and run:
python -m http.server 8080

keep both of these terminals open

Open the website at local host:
localhost:8080 <- index.html for workers
localhost:8080/admin.html <- admin.html for toys assign
