# Save as get_token.py
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google.oauth2 import service_account
from google_auth_oauthlib.flow import InstalledAppFlow
import os.path

# This will give your app permission to *send* email
SCOPES = ["https://www.googleapis.com/auth/gmail.send"]

def main():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                "credentials.json", SCOPES,
                redirect_uri='http://127.0.0.1:5000/oauth2callback' # Make sure this matches
            )
            creds = flow.run_local_server(port=5000)
        # Save the credentials for the next run
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    print("✅ token.json file was created successfully. You can now run your app.")
    print("⚠️ IMPORTANT: You must now copy the content of 'token.json' to your .env file and your Render Environment Variables.")

if __name__ == "__main__":
    main()