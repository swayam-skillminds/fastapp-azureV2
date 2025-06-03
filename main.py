from fastapi import FastAPI, Form, File, UploadFile, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
import asyncpg
import asyncio
from azure.storage.blob import BlobServiceClient
from azure.servicebus import ServiceBusClient, ServiceBusMessage
from azure.keyvault.secrets import SecretClient
from azure.identity import DefaultAzureCredential
import os
import uuid
from datetime import datetime
import json
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(title="Form Submission App", description="Simple form submission with Azure integration")

# Azure Key Vault setup
credential = DefaultAzureCredential()
key_vault_url = os.getenv("KEY_VAULT_URL", "https://your-keyvault.vault.azure.net/")
secret_client = SecretClient(vault_url=key_vault_url, credential=credential)

# Global variables to store connections
db_pool = None
blob_service_client = None
servicebus_client = None

async def get_secret(secret_name: str) -> str:
    """Retrieve secret from Azure Key Vault"""
    try:
        secret = secret_client.get_secret(secret_name)
        return secret.value
    except Exception as e:
        logger.error(f"Failed to retrieve secret {secret_name}: {e}")
        # Fallback to environment variables for local development
        return os.getenv(secret_name.upper().replace("-", "_"))

async def initialize_azure_clients():
    """Initialize Azure service clients"""
    global db_pool, blob_service_client, servicebus_client
    
    try:
        # Get secrets from Key Vault
        storage_connection_string = await get_secret("storage-connection-string")
        postgres_connection_string = await get_secret("postgres-connection-string")
        servicebus_connection_string = await get_secret("servicebus-connection-string")
        
        # Initialize Azure Blob Storage client
        blob_service_client = BlobServiceClient.from_connection_string(storage_connection_string)
        
        # Initialize Service Bus client
        servicebus_client = ServiceBusClient.from_connection_string(servicebus_connection_string)
        
        # Initialize PostgreSQL connection pool
        db_pool = await asyncpg.create_pool(postgres_connection_string)
        
        # Create table if it doesn't exist
        async with db_pool.acquire() as connection:
            await connection.execute("""
                CREATE TABLE IF NOT EXISTS form_submissions (
                    id SERIAL PRIMARY KEY,
                    name VARCHAR(255) NOT NULL,
                    address TEXT NOT NULL,
                    id_number VARCHAR(100) NOT NULL,
                    image_filename VARCHAR(255),
                    blob_url TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
        
        logger.info("Azure clients initialized successfully")
        
    except Exception as e:
        logger.error(f"Failed to initialize Azure clients: {e}")
        raise

@app.on_event("startup")
async def startup_event():
    """Initialize connections on startup"""
    await initialize_azure_clients()

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up connections on shutdown"""
    global db_pool
    if db_pool:
        await db_pool.close()

@app.get("/", response_class=HTMLResponse)
async def get_form():
    """Serve the HTML form"""
    return """
    <!DOCTYPE html>
    <html>
    <head>
        <title>Form Submission</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 600px; margin: 50px auto; padding: 20px; }
            .form-group { margin-bottom: 15px; }
            label { display: block; margin-bottom: 5px; font-weight: bold; }
            input, textarea { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; }
            textarea { height: 100px; resize: vertical; }
            button { background-color: #007bff; color: white; padding: 10px 20px; border: none; border-radius: 4px; cursor: pointer; }
            button:hover { background-color: #0056b3; }
            .success { color: green; margin-top: 10px; }
            .error { color: red; margin-top: 10px; }
        </style>
    </head>
    <body>
        <h1>Form Submission</h1>
        <form id="submissionForm" enctype="multipart/form-data">
            <div class="form-group">
                <label for="name">Name:</label>
                <input type="text" id="name" name="name" required>
            </div>
            <div class="form-group">
                <label for="address">Address:</label>
                <textarea id="address" name="address" required></textarea>
            </div>
            <div class="form-group">
                <label for="id_number">ID Number:</label>
                <input type="text" id="id_number" name="id_number" required>
            </div>
            <div class="form-group">
                <label for="photograph">Photograph:</label>
                <input type="file" id="photograph" name="photograph" accept="image/*" required>
            </div>
            <button type="submit">Submit Form</button>
        </form>
        <div id="message"></div>

        <script>
            document.getElementById('submissionForm').addEventListener('submit', async function(e) {
                e.preventDefault();
                
                const formData = new FormData(this);
                const messageDiv = document.getElementById('message');
                
                try {
                    const response = await fetch('/submit', {
                        method: 'POST',
                        body: formData
                    });
                    
                    const result = await response.json();
                    
                    if (response.ok) {
                        messageDiv.innerHTML = '<div class="success">Form submitted successfully! ID: ' + result.submission_id + '</div>';
                        this.reset();
                    } else {
                        messageDiv.innerHTML = '<div class="error">Error: ' + result.detail + '</div>';
                    }
                } catch (error) {
                    messageDiv.innerHTML = '<div class="error">Error: ' + error.message + '</div>';
                }
            });
        </script>
    </body>
    </html>
    """

@app.post("/submit")
async def submit_form(
    name: str = Form(...),
    address: str = Form(...),
    id_number: str = Form(...),
    photograph: UploadFile = File(...)
):
    """Handle form submission"""
    try:
        # Validate file type
        if not photograph.content_type.startswith('image/'):
            raise HTTPException(status_code=400, detail="File must be an image")
        
        # Generate unique filename
        file_extension = photograph.filename.split('.')[-1] if '.' in photograph.filename else 'jpg'
        unique_filename = f"{uuid.uuid4()}.{file_extension}"
        
        # Upload to Azure Blob Storage
        container_name = "form-images"
        blob_client = blob_service_client.get_blob_client(
            container=container_name, 
            blob=unique_filename
        )
        
        # Read file content
        file_content = await photograph.read()
        
        # Upload to blob storage
        blob_client.upload_blob(file_content, overwrite=True)
        blob_url = blob_client.url
        
        # Store metadata in PostgreSQL
        async with db_pool.acquire() as connection:
            submission_id = await connection.fetchval(
                """
                INSERT INTO form_submissions (name, address, id_number, image_filename, blob_url)
                VALUES ($1, $2, $3, $4, $5)
                RETURNING id
                """,
                name, address, id_number, unique_filename, blob_url
            )
        
        # Send message to Service Bus Queue
        message_data = {
            "submission_id": submission_id,
            "name": name,
            "address": address,
            "id_number": id_number,
            "image_filename": unique_filename,
            "blob_url": blob_url,
            "timestamp": datetime.utcnow().isoformat()
        }
        
        sender = servicebus_client.get_queue_sender(queue_name="form-submission-job")
        message = ServiceBusMessage(json.dumps(message_data))
        sender.send_messages(message)
        sender.close()
        
        logger.info(f"Form submitted successfully with ID: {submission_id}")
        
        return {
            "message": "Form submitted successfully",
            "submission_id": submission_id,
            "blob_url": blob_url
        }
        
    except Exception as e:
        logger.error(f"Error processing form submission: {e}")
        raise HTTPException(status_code=500, detail=f"Internal server error: {str(e)}")

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
