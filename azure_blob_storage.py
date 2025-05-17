import os
import uuid
from typing import List, Dict, Any, Optional, BinaryIO
from azure.storage.blob import BlobServiceClient, BlobClient, ContainerClient
from azure.core.exceptions import ResourceExistsError, ResourceNotFoundError
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class AzureBlobStorage:
    def __init__(self):
        """Initialize Azure Blob Storage client with credentials from environment variables."""
        # Use the provided account key from the requirements
        self.account_key = os.getenv("AZURE_BLOB_STORAGE_KEY", "your_azure_blob_storage_key_here")
        self.account_name = os.getenv("AZURE_BLOB_STORAGE_ACCOUNT", "siudfiles")
        self.connection_string = os.getenv("AZURE_BLOB_STORAGE_CONNECTION_STRING", 
                                          f"DefaultEndpointsProtocol=https;AccountName={self.account_name};AccountKey={self.account_key};EndpointSuffix=core.windows.net")
        self.default_container = os.getenv("AZURE_BLOB_STORAGE_CONTAINER", "documents")

        # Initialize the blob service client
        try:
            self.blob_service_client = BlobServiceClient.from_connection_string(self.connection_string)
            print(f"Successfully connected to Azure Blob Storage account: {self.account_name}")
        except Exception as e:
            print(f"Error connecting to Azure Blob Storage: {str(e)}")
            raise

    def ensure_container_exists(self, container_name: str = None) -> bool:
        """
        Ensure that the specified container exists, creating it if necessary.
        
        Args:
            container_name: Name of the container to check/create (uses default if None)
            
        Returns:
            True if the container exists or was created successfully, False otherwise
        """
        container_name = container_name or self.default_container
        
        try:
            # Check if container exists
            container_client = self.blob_service_client.get_container_client(container_name)
            container_client.get_container_properties()  # Will raise if container doesn't exist
            print(f"Container '{container_name}' already exists")
            return True
        except ResourceNotFoundError:
            # Container doesn't exist, create it
            try:
                container_client = self.blob_service_client.create_container(container_name)
                print(f"Container '{container_name}' created successfully")
                return True
            except Exception as e:
                print(f"Error creating container '{container_name}': {str(e)}")
                return False
        except Exception as e:
            print(f"Error checking container '{container_name}': {str(e)}")
            return False

    def upload_file(self, file_path: str, file_content: bytes, container_name: str = None) -> Dict[str, Any]:
        """
        Upload a file to Azure Blob Storage.
        
        Args:
            file_path: Path where the file will be stored in the container
            file_content: Binary content of the file
            container_name: Name of the container (uses default if None)
            
        Returns:
            Dictionary with upload status and blob URL if successful
        """
        container_name = container_name or self.default_container
        
        try:
            # Ensure container exists
            if not self.ensure_container_exists(container_name):
                return {"success": False, "error": f"Container '{container_name}' does not exist and could not be created"}
            
            # Get a blob client and upload the file
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=file_path
            )
            
            # Upload the file
            blob_client.upload_blob(file_content, overwrite=True)
            
            # Get the blob URL
            blob_url = blob_client.url
            
            return {
                "success": True,
                "blob_url": blob_url,
                "container": container_name,
                "blob_path": file_path
            }
            
        except Exception as e:
            print(f"Error uploading file to '{file_path}': {str(e)}")
            return {"success": False, "error": str(e)}

    def download_file(self, blob_path: str, container_name: str = None) -> Optional[bytes]:
        """
        Download a file from Azure Blob Storage.
        
        Args:
            blob_path: Path to the blob in the container
            container_name: Name of the container (uses default if None)
            
        Returns:
            File content as bytes if successful, None otherwise
        """
        container_name = container_name or self.default_container
        
        try:
            # Get a blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_path
            )
            
            # Download the blob
            download_stream = blob_client.download_blob()
            file_content = download_stream.readall()
            
            return file_content
            
        except Exception as e:
            print(f"Error downloading file from '{blob_path}': {str(e)}")
            return None

    def list_blobs(self, container_name: str = None, prefix: str = None) -> List[Dict[str, Any]]:
        """
        List all blobs in a container, optionally filtered by prefix.
        
        Args:
            container_name: Name of the container (uses default if None)
            prefix: Optional prefix to filter blobs
            
        Returns:
            List of dictionaries with blob information
        """
        container_name = container_name or self.default_container
        
        try:
            # Get a container client
            container_client = self.blob_service_client.get_container_client(container_name)
            
            # List blobs
            blobs = container_client.list_blobs(name_starts_with=prefix)
            
            # Convert to list of dictionaries
            blob_list = []
            for blob in blobs:
                blob_list.append({
                    "name": blob.name,
                    "size": blob.size,
                    "last_modified": blob.last_modified,
                    "content_type": blob.content_settings.content_type
                })
            
            return blob_list
            
        except Exception as e:
            print(f"Error listing blobs in container '{container_name}': {str(e)}")
            return []

    def delete_blob(self, blob_path: str, container_name: str = None) -> bool:
        """
        Delete a blob from Azure Blob Storage.
        
        Args:
            blob_path: Path to the blob in the container
            container_name: Name of the container (uses default if None)
            
        Returns:
            True if successful, False otherwise
        """
        container_name = container_name or self.default_container
        
        try:
            # Get a blob client
            blob_client = self.blob_service_client.get_blob_client(
                container=container_name,
                blob=blob_path
            )
            
            # Delete the blob
            blob_client.delete_blob()
            
            return True
            
        except Exception as e:
            print(f"Error deleting blob '{blob_path}': {str(e)}")
            return False
