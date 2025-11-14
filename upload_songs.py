import os
import paramiko

def upload_file(local_path, remote_path, hostname, port, username, password):
    try:
        # Create SSH/SFTP client
        ssh_client = paramiko.SSHClient()
        ssh_client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
        ssh_client.connect(hostname, port=port, username=username, password=password)

        # Create SFTP client
        sftp_client = ssh_client.open_sftp()

        # Upload local file to remote server
        sftp_client.put(local_path, remote_path)

        # Close SFTP connection
        sftp_client.close()
        ssh_client.close()

        print(f"File '{local_path}' uploaded to '{remote_path}' successfully.")

    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    # Get local file path from user input
    local_file_path = input("Enter the local file path to upload: ")

    # Check if the local file exists
    if not os.path.isfile(local_file_path):
        print("Error: Local file does not exist.")
    else:
        # Define remote file path
        remote_file_path = input("Enter the remote file path to upload to: ")

        # Define SSH/SFTP connection parameters
        hostname = "your_server_hostname"
        port = 22  # Default SSH port
        username = "your_username"
        password = "your_password"

        # Call the upload_file function
        upload_file(local_file_path, remote_file_path, hostname, port, username, password)
