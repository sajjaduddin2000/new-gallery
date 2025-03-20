import os
from azure.storage.blob import BlobServiceClient, generate_blob_sas, BlobSasPermissions, ContentSettings
from azure.storage.fileshare import ShareServiceClient, ShareFileClient
from flask import Flask, request, redirect
from datetime import datetime, timedelta
from dotenv import load_dotenv

# Load environment variables from .env
load_dotenv()

app = Flask(__name__)

# Fetch connection string and account details from environment
connect_str = os.getenv("AZURE_STORAGE_CONNECTION_STRING")
account_name = os.getenv("AZURE_STORAGE_ACCOUNT_NAME")
account_key = os.getenv("AZURE_STORAGE_ACCOUNT_KEY")
container_name = "photos"
file_share_name = "myfileshare"
file_share_sas_url = os.getenv("AZURE_FILE_SHARE_SAS_URL")
share_service_client = ShareServiceClient(account_url=file_share_sas_url)
file_share_client = share_service_client.get_share_client(file_share_name)


# Validate credentials
if not connect_str or not account_name or not account_key:
    raise ValueError("AZURE_STORAGE_CONNECTION_STRING, AZURE_STORAGE_ACCOUNT_NAME, or AZURE_STORAGE_ACCOUNT_KEY is missing in .env!")

# Initialize Blob Service Client
blob_service_client = BlobServiceClient.from_connection_string(connect_str)
container_client = blob_service_client.get_container_client(container_name)

# Initialize File Share Client
share_service_client = ShareServiceClient(account_url=f"https://{account_name}.file.core.windows.net", credential=account_key)
file_share_client = share_service_client.get_share_client(file_share_name)


@app.route("/")
def view_photos():
    blobs = container_client.list_blobs()
    img_html = "<div style='display: flex; flex-wrap: wrap; gap: 1em;'>"

    for blob in blobs:
        try:
            sas_token = generate_blob_sas(
                account_name=account_name,
                container_name=container_name,
                blob_name=blob.name,
                account_key=account_key,
                permission=BlobSasPermissions(read=True),
                expiry=datetime.utcnow() + timedelta(hours=1)
            )

            blob_url = f"https://{account_name}.blob.core.windows.net/{container_name}/{blob.name}?{sas_token}"
            img_html += f'<div><img src="{blob_url}" width="270" height="180" style="border-radius: 10px; border: 1px solid #ddd; margin: 5px;"></div>'
        except Exception as e:
            print(f"Error generating SAS token for {blob.name}: {e}")

    img_html += "</div>"
    return f"""
    <head>
        <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
    </head>
    <body>
        <nav class="navbar navbar-dark bg-primary mb-4">
            <div class="container">
                <a class="navbar-brand" href="/">Photos App</a>
            </div>
        </nav>
        <div class="container">
            <h3>Upload File to Blob Storage</h3>
            <form method="post" action="/upload-photos" enctype="multipart/form-data">
                <input type="file" name="photos" multiple accept=".png,.jpg,.jpeg">
                <button type="submit" class="btn btn-primary mt-2">Upload</button>
            </form>
            
            <hr>
           
            <h3>Uploaded Images</h3>
            {img_html}
        </div>
    </body>
    """


@app.route("/upload-photos", methods=["POST"])
def upload_photos():
    if "photos" not in request.files:
        return redirect("/")

    for file in request.files.getlist("photos"):
        if file.filename == "":
            continue

        try:
            # Upload to Azure Blob Storage
            blob_client = container_client.get_blob_client(file.filename)
            blob_client.upload_blob(
                file.read(),
                overwrite=True,
                content_settings=ContentSettings(content_type=file.content_type)
            )
            print(f"Uploaded {file.filename} to Azure Blob Storage.")

            # Upload to Azure File Share
            file_path = file.filename  # File name inside Azure File Share
            file_client = file_share_client.get_directory_client("").get_file_client(file_path)
            file.seek(0)  # Reset file pointer
            file_client.upload_file(file.read())
            print(f"Uploaded {file.filename} to Azure File Share.")

        except Exception as e:
            print(f"Upload failed: {str(e)}")

    return redirect("/")


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
