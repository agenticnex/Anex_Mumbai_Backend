import os
import json
import base64
from typing import Dict, Any, List, Optional
import httpx
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class SupabaseClient:
    def __init__(self):
        """Initialize Supabase client with credentials from environment variables."""
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY")

        if not self.url or not self.key:
            raise ValueError("Supabase credentials not found in environment variables")

        # We'll use direct REST API calls instead of the Python client
        self.base_url = f"{self.url}/rest/v1"
        self.headers = {
            "apikey": self.key,
            "Authorization": f"Bearer {self.key}",
            "Content-Type": "application/json",
            "Prefer": "return=representation"
        }

        # Ensure the necessary tables exist
        self._initialize_tables()

    def _initialize_tables(self):
        """Check if required tables exist and create them if they don't."""
        try:
            # Check if the documents table exists
            with httpx.Client() as client:
                response = client.get(
                    f"{self.base_url}/documents",
                    headers=self.headers,
                    params={
                        "select": "count",
                        "limit": 1
                    }
                )

                # If we get a 404, the table doesn't exist
                if response.status_code == 404:
                    print("Documents table doesn't exist. Attempting to create it...")
                    self._create_documents_table()
                else:
                    print("Documents table exists.")
        except Exception as e:
            print(f"Error checking if tables exist: {str(e)}")
            # Try to create the table anyway
            self._create_documents_table()

    def save_document_data(self,
                          file_name: str,
                          file_content: bytes,
                          extracted_data: Dict[str, Any],
                          suid: Optional[str] = None) -> Dict[str, Any]:
        """
        Save document data to Supabase.

        Args:
            file_name: Original file name
            file_content: Binary content of the file
            extracted_data: Dictionary containing extracted data
            suid: SUID of the document (if available)

        Returns:
            Dictionary containing the saved record information
        """
        try:
            # Encode file content as base64 for storage
            encoded_file = base64.b64encode(file_content).decode('utf-8')

            # Generate a default SUID if none is provided
            if not suid or suid == "Not found":
                import uuid
                import datetime
                # Generate a unique ID based on timestamp and random UUID
                timestamp = datetime.datetime.now().strftime("%Y%m%d%H%M%S")
                random_id = str(uuid.uuid4())[:8]
                suid = f"DOC-{timestamp}-{random_id}"

            # Ensure extracted_data is properly formatted for JSON storage
            print(f"Processing extracted_data for {file_name}, type: {type(extracted_data)}")

            if isinstance(extracted_data, dict):
                print(f"Processing dictionary data with keys: {list(extracted_data.keys())}")
                # Deep copy to avoid modifying the original
                import copy
                extracted_data_copy = copy.deepcopy(extracted_data)

                # Helper function to recursively convert non-serializable objects
                def make_serializable(obj):
                    if isinstance(obj, dict):
                        return {k: make_serializable(v) for k, v in obj.items()}
                    elif isinstance(obj, list):
                        return [make_serializable(item) for item in obj]
                    elif isinstance(obj, (str, int, float, bool, type(None))):
                        return obj
                    else:
                        return str(obj)

                # Convert any non-serializable objects to strings
                extracted_data_copy = make_serializable(extracted_data_copy)

                # Convert to JSON string
                try:
                    extracted_data_json = json.dumps(extracted_data_copy)
                    print(f"Successfully converted extracted_data to JSON string")
                except Exception as e:
                    print(f"Error converting extracted_data to JSON: {str(e)}")
                    # Fallback to a simplified version
                    simplified_data = {
                        "simplified": True,
                        "original_keys": list(extracted_data.keys()),
                        "error": str(e)
                    }
                    extracted_data_json = json.dumps(simplified_data)
                    print(f"Using simplified data instead")
            else:
                # If it's already a string, make sure it's valid JSON
                try:
                    if isinstance(extracted_data, str):
                        json.loads(extracted_data)
                        extracted_data_json = extracted_data
                        print(f"Using provided JSON string")
                    else:
                        print(f"Non-dict, non-string data type: {type(extracted_data)}")
                        extracted_data_json = json.dumps({"raw_data": str(extracted_data)})
                except (TypeError, json.JSONDecodeError) as e:
                    print(f"Error parsing JSON string: {str(e)}")
                    extracted_data_json = json.dumps({"raw_data": str(extracted_data)})

            # Prepare data for insertion
            document_data = {
                "file_name": file_name,
                "file_content": encoded_file,
                "extracted_data": extracted_data_json,
                "suid": suid
            }

            # Check if document with this SUID already exists
            with httpx.Client() as client:
                response = client.get(
                    f"{self.base_url}/documents",
                    headers=self.headers,
                    params={"select": "id", "suid": f"eq.{suid}"}
                )

                if response.status_code == 200 and len(response.json()) > 0:
                    # Document with this SUID already exists
                    existing_id = response.json()[0]["id"]

                    # Update the existing document instead of creating a new one
                    update_response = client.patch(
                        f"{self.base_url}/documents",
                        headers=self.headers,
                        params={"id": f"eq.{existing_id}"},
                        json=document_data
                    )

                    if update_response.status_code in (200, 201, 204):
                        return {"success": True, "id": existing_id, "message": "Document updated successfully"}
                    else:
                        # If update fails, try to insert a new document with a modified SUID
                        document_data["suid"] = f"{suid}-{str(uuid.uuid4())[:8]}"

            # Insert data into documents table
            print(f"Attempting to insert document into database with SUID: {suid}")
            try:
                with httpx.Client() as client:
                    print(f"Sending POST request to {self.base_url}/documents")
                    response = client.post(
                        f"{self.base_url}/documents",
                        headers=self.headers,
                        json=document_data,
                        timeout=30.0  # Increase timeout for large documents
                    )

                    print(f"Response status code: {response.status_code}")

                    if response.status_code in (200, 201):
                        response_data = response.json()
                        print(f"Response data: {response_data}")

                        if len(response_data) > 0:
                            return {"success": True, "id": response_data[0]["id"]}
                        else:
                            print("Response data is empty")
                            return {"success": False, "error": "Empty response data"}
                    else:
                        # Print detailed error for debugging
                        print(f"Failed to save document. Status: {response.status_code}, Response: {response.text}")
                        print(f"Request URL: {self.base_url}/documents")

                        # Try alternative approach with SQL
                        print("Attempting to insert using SQL query")
                        try:
                            # Use service role key for this operation
                            service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                            if service_key:
                                admin_headers = {
                                    "apikey": service_key,
                                    "Authorization": f"Bearer {service_key}",
                                    "Content-Type": "application/json"
                                }

                                # Create SQL insert statement
                                insert_sql = f"""
                                INSERT INTO documents (file_name, suid, extracted_data, file_content)
                                VALUES (
                                    '{file_name.replace("'", "''")}',
                                    '{suid.replace("'", "''")}',
                                    '{extracted_data_json.replace("'", "''")}',
                                    '{encoded_file}'
                                )
                                RETURNING id;
                                """

                                sql_response = client.post(
                                    f"{self.url}/rest/v1/rpc/execute_sql",
                                    headers=admin_headers,
                                    json={"query": insert_sql},
                                    timeout=30.0
                                )

                                if sql_response.status_code in (200, 201):
                                    print(f"SQL insert successful: {sql_response.text}")
                                    return {"success": True, "id": "sql-insert", "message": "Inserted using SQL"}
                                else:
                                    print(f"SQL insert failed: {sql_response.text}")
                            else:
                                print("Service role key not found for SQL insert")
                        except Exception as sql_error:
                            print(f"Error during SQL insert: {str(sql_error)}")

                        # Try one more time with a simplified payload
                        print("Trying with simplified payload")
                        simplified_data = {
                            "file_name": file_name,
                            "file_content": "BASE64_CONTENT_REMOVED_FOR_DEBUGGING",
                            "extracted_data": json.dumps({"simplified": "for debugging", "suid": suid}),
                            "suid": suid
                        }

                        try:
                            simplified_response = client.post(
                                f"{self.base_url}/documents",
                                headers=self.headers,
                                json=simplified_data,
                                timeout=15.0
                            )

                            if simplified_response.status_code in (200, 201):
                                print(f"Simplified insert successful: {simplified_response.text}")
                                return {"success": True, "id": "simplified-insert", "message": "Inserted using simplified data"}
                            else:
                                print(f"Simplified insert failed: {simplified_response.text}")
                        except Exception as simplified_error:
                            print(f"Error during simplified insert: {str(simplified_error)}")

                        return {"success": False, "error": f"Failed to save document data: {response.text}"}
            except Exception as insert_error:
                print(f"Exception during database insert: {str(insert_error)}")
                return {"success": False, "error": f"Insert exception: {str(insert_error)}"}

        except Exception as e:
            import traceback
            print(f"Error saving document data: {str(e)}")
            print(traceback.format_exc())
            return {"success": False, "error": str(e)}

    def get_document_by_suid(self, suid: str) -> Optional[Dict[str, Any]]:
        """
        Retrieve document data by SUID.

        Args:
            suid: SUID of the document

        Returns:
            Dictionary containing document data or None if not found
        """
        try:
            with httpx.Client() as client:
                response = client.get(
                    f"{self.base_url}/documents",
                    headers=self.headers,
                    params={"select": "*", "suid": f"eq.{suid}"}
                )

                if response.status_code == 200 and len(response.json()) > 0:
                    # Parse the JSON data
                    doc = response.json()[0]
                    if isinstance(doc["extracted_data"], str):
                        doc["extracted_data"] = json.loads(doc["extracted_data"])
                    return doc
                else:
                    return None

        except Exception as e:
            print(f"Error retrieving document by SUID: {str(e)}")
            return None

    def get_all_documents(self, include_data: bool = False) -> List[Dict[str, Any]]:
        """
        Retrieve all documents.

        Args:
            include_data: Whether to include the extracted_data field in the response

        Returns:
            List of dictionaries containing document data
        """
        try:
            with httpx.Client() as client:
                # First check if the table exists
                response = client.get(
                    f"{self.base_url}/documents",
                    headers=self.headers,
                    params={
                        "select": "count",
                        "limit": 1
                    }
                )

                # If we get a 404, the table might not exist
                if response.status_code == 404:
                    print("Documents table might not exist. Attempting to create it...")
                    self._create_documents_table()

                # Determine which fields to select
                select_fields = "id,file_name,suid,created_at"
                if include_data:
                    select_fields = "*"  # Include all fields, including extracted_data

                # Now try to get all documents
                response = client.get(
                    f"{self.base_url}/documents",
                    headers=self.headers,
                    params={
                        "select": select_fields,
                        "order": "created_at.desc"
                    }
                )

                if response.status_code == 200:
                    documents = response.json()
                    print(f"Retrieved {len(documents)} documents from database")
                    return documents
                else:
                    print(f"Failed to retrieve documents. Status: {response.status_code}, Response: {response.text}")
                    return []

        except Exception as e:
            import traceback
            print(f"Error retrieving all documents: {str(e)}")
            print(traceback.format_exc())
            return []

    def _create_documents_table(self):
        """Create the documents table if it doesn't exist."""
        try:
            # SQL to create the documents table
            sql = """
            CREATE TABLE IF NOT EXISTS documents (
                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                file_name TEXT NOT NULL,
                file_content TEXT NOT NULL,
                extracted_data JSONB NOT NULL,
                suid TEXT NOT NULL,
                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
            );
            """

            # Try to execute the SQL using the REST API
            with httpx.Client() as client:
                # We need to use the service role key for this operation
                service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                if service_key:
                    admin_headers = {
                        "apikey": service_key,
                        "Authorization": f"Bearer {service_key}",
                        "Content-Type": "application/json"
                    }

                    response = client.post(
                        f"{self.url}/rest/v1/rpc/execute_sql",
                        headers=admin_headers,
                        json={"query": sql}
                    )

                    if response.status_code in (200, 201):
                        print("Documents table created successfully!")
                        return True
                    else:
                        print(f"Failed to create documents table: {response.text}")
                        return False
                else:
                    print("Service role key not found. Cannot create table.")
                    return False

        except Exception as e:
            print(f"Error creating documents table: {str(e)}")
            return False

    def delete_document(self, document_id: str) -> bool:
        """
        Delete a document by ID.

        Args:
            document_id: ID of the document to delete

        Returns:
            Boolean indicating success or failure
        """
        try:
            with httpx.Client() as client:
                response = client.delete(
                    f"{self.base_url}/documents",
                    headers=self.headers,
                    params={"id": f"eq.{document_id}"}
                )

                if response.status_code in (200, 204):
                    return True
                else:
                    return False

        except Exception as e:
            print(f"Error deleting document: {str(e)}")
            return False
