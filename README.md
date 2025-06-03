# FastAPI Form Submission with Azure Integration

A simple tutorial project that demonstrates how to build a FastAPI application with Azure services integration, containerization, and CI/CD deployment to AKS.

## Features

- 📝 HTML form for user data and file upload
- 🗄️ PostgreSQL for storing form metadata
- 🗃️ Azure Blob Storage for image uploads
- 📨 Azure Service Bus for message queuing
- 🔐 Azure Key Vault for secret management
- 🐳 Docker containerization
- ⚙️ GitHub Actions CI/CD
- ☸️ Kubernetes (AKS) deployment

## Prerequisites

- Azure subscription
- GitHub account
- Docker installed locally (for testing)

## Azure Resources Setup (via Portal UI)

### 1. Create Resource Group
- Go to Azure Portal
- Create a new Resource Group named `form-autofill-rg`

### 2. Create Storage Account
- Create a new Storage Account in the resource group
- Note down the connection string
- Create a container named `form-images`

### 3. Create PostgreSQL Flexible Server
- Create a PostgreSQL Flexible Server
- Note down the connection string
- Allow Azure services to access the server

### 4. Create Service Bus Namespace
- Create a Service Bus Namespace
- Create a queue named `form-submission-job`
- Note down the connection string

### 5. Create Key Vault
- Create a Key Vault
- Add the following secrets:
  - `storage-connection-string`: Your storage account connection string
  - `postgres-connection-string`: Your PostgreSQL connection string
  - `servicebus-connection-string`: Your Service Bus connection string

### 6. Create Container Registry (ACR)
- Create an Azure Container Registry
- Note down the login server, username, and password

### 7. Create AKS Cluster
- Create an Azure Kubernetes Service cluster
- Attach it to the ACR created above

### 8. Create Service Principal
Create a service principal for GitHub Actions:
```bash
az ad sp create-for-rbac --name "github-actions-sp" --role contributor --scopes /subscriptions/{subscription-id}/resourceGroups/form-autofill-rg --sdk-auth
```

## GitHub Setup

### 1. Fork/Clone Repository
- Fork this repository or create a new one with these files

### 2. Configure GitHub Secrets
Add these secrets to your GitHub repository:
- `AZURE_CREDENTIALS`: The JSON output from service principal creation
- `ACR_USERNAME`: Your ACR username
- `ACR_PASSWORD`: Your ACR password

### 3. Update Configuration
Update the following files with your Azure resource names:

#### `.github/workflows/deploy.yml`
```yaml
env:
  REGISTRY_NAME: your-acr-name  # Replace with your ACR name
  CLUSTER_NAME: your-aks-cluster  # Replace with your AKS cluster name
```

#### `k8s/deployment.yaml`
```yaml
env:
- name: KEY_VAULT_URL
  value: "https://your-keyvault.vault.azure.net/"  # Replace with your Key Vault URL
```

## Local Development

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Set Environment Variables
Create a `.env` file:
```env
KEY_VAULT_URL=https://your-keyvault.vault.azure.net/
STORAGE_CONNECTION_STRING=your-storage-connection-string
POSTGRES_CONNECTION_STRING=your-postgres-connection-string
SERVICEBUS_CONNECTION_STRING=your-servicebus-connection-string
```

### 3. Run the Application
```bash
python main.py
```

Visit `http://localhost:8000` to see the form.

## Docker Build and Test

```bash
# Build the image
docker build -t form-submission-app .

# Run the container
docker run -p 8000:8000 --env-file .env form-submission-app
```

## Deployment

### Automatic Deployment
Push to the `main` branch to trigger automatic deployment via GitHub Actions.

### Manual Deployment
```bash
# Build and push to ACR
docker build -t your-acr.azurecr.io/form-submission-app .
docker push your-acr.azurecr.io/form-submission-app

# Deploy to AKS
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
```

## Project Structure

```
├── main.py                 # FastAPI application
├── requirements.txt        # Python dependencies
├── Dockerfile             # Container configuration
├── .github/workflows/
│   └── deploy.yml         # CI/CD pipeline
├── k8s/
│   ├── deployment.yaml    # Kubernetes deployment
│   └── service.yaml       # Kubernetes service
└── README.md              # This file
```

## Key Features Explained

### Form Processing Flow
1. User submits form through web interface
2. Image is uploaded to Azure Blob Storage
3. Metadata is stored in PostgreSQL
4. Message is sent to Service Bus queue for further processing
5. Response is returned to user

### Security
- Secrets are stored in Azure Key Vault
- Service principal authentication for Azure services
- Non-root user in Docker container
- Resource limits in Kubernetes

### Monitoring
- Health check endpoint at `/health`
- Kubernetes liveness and readiness probes
- Logging throughout the application

## Troubleshooting

### Common Issues

1. **Key Vault Access Denied**
   - Ensure the service principal has access to Key Vault
   - Check if the Key Vault URL is correct

2. **Database Connection Failed**
   - Ensure PostgreSQL allows Azure services access
   - Check connection string format

3. **Blob Upload Failed**
   - Ensure storage account is accessible
   - Check if container `form-images` exists

4. **Service Bus Message Failed**
   - Ensure queue `form-submission-job` exists
   - Check Service Bus connection string

### Logs
Check application logs:
```bash
kubectl logs -l app=form-submission-app
```

## Next Steps

- Add form validation
- Implement message processing from Service Bus
- Add monitoring and alerting
- Implement HTTPS/TLS
- Add authentication and authorization
- Scale the application based on load

## License

This project is for educational purposes and is provided as-is.
