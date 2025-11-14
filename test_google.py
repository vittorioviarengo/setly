import os

def check_credentials_path():
    path = os.getenv('GOOGLE_APPLICATION_CREDENTIALS')
    if path:
        print("Credential path set to:", path)
    else:
        print("No credentials path set.")

if __name__ == "__main__":
    check_credentials_path()
