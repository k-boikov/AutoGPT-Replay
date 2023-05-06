""""File Management Lifter"""

import os
import shutil
import zipfile

# Get the current directory
current_dir = os.getcwd()

# Get the destination directory for the zip files
dest_dir = os.path.abspath(os.path.join(current_dir, "../../Auto-GPT/plugins"))

# Loop through all the items in the current directory
for item in os.listdir(current_dir):
    # Check if the item is a folder
    if os.path.isdir(item):
        # Create the name of the zip file by appending ".zip" to the folder name
        zip_name = item + ".zip"
        # Create the path to the zip file
        zip_path = os.path.join(current_dir, zip_name)
        # Create a zip file of the folder
        with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zip_file:
            # Create a folder inside the zip file with the same name as the original folder
            zip_folder = os.path.basename(item)
            # Loop through all the files and subdirectories in the original folder
            for root, dirs, files in os.walk(item):
                # Create a subdirectory inside the zip file for each subdirectory in the original folder
                for dir in dirs:
                    zip_file.write(
                        os.path.join(root, dir),
                        os.path.join(
                            zip_folder, os.path.relpath(os.path.join(root, dir), item)
                        ),
                    )
                # Add each file in the original folder to the zip file
                for file in files:
                    zip_file.write(
                        os.path.join(root, file),
                        os.path.join(
                            zip_folder, os.path.relpath(os.path.join(root, file), item)
                        ),
                    )
        # Copy the zip file to the destination directory
        shutil.copy2(zip_path, dest_dir)
