import os


log_file_path = '/var/log/vittorioviarengo.pythonanywhere.com.error.log'  

# Check if the file exists before trying to clear it
if os.path.exists(log_file_path):
    with open(log_file_path, 'w') as log_file:
        log_file.write('')
    print(f"Cleared log file: {log_file_path}")
else:
    print(f"Log file does not exist: {log_file_path}")
