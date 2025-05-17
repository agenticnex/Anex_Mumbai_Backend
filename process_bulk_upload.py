import os
import base64
import json
import uuid
from datetime import datetime
import tempfile

async def process_bulk_upload(job_id, files, extraction_type, bulk_upload_jobs, blob_storage, document_ai, supabase_client, search_page_details_for_ids):
    """
    Process a bulk upload job in the background.

    This function:
    1. Uploads each file to Azure Blob Storage
    2. Then processes each file from blob storage with Azure Document AI
    3. Saves the results to the Supabase database using the same method as single file upload
    4. Updates the job status

    Args:
        job_id: The ID of the bulk upload job
        files: List of files to process
        extraction_type: Type of extraction to perform
        bulk_upload_jobs: Dictionary to store job status
        blob_storage: Azure Blob Storage client
        document_ai: Azure Document AI client
        supabase_client: Supabase client
        search_page_details_for_ids: Function to search for IDs in page details
    """
    try:
        job = bulk_upload_jobs[job_id]
        container_name = "documents"  # Use the default documents container

        # Step 1: Upload all files to blob storage first
        print(f"Starting upload of {len(files)} files to Azure Blob Storage")
        uploaded_files = []

        for i, file in enumerate(files):
            try:
                # Decode base64 content
                file_content = base64.b64decode(file.content)

                # Upload directly to the documents container without creating folders
                blob_path = f"{i}_{file.name}"
                upload_result = blob_storage.upload_file(blob_path, file_content, container_name)

                if upload_result["success"]:
                    print(f"Successfully uploaded file {file.name} to blob storage")
                    uploaded_files.append({
                        "index": i,
                        "name": file.name,
                        "blob_path": blob_path
                    })
                else:
                    job["errors"].append({
                        "file": file.name,
                        "stage": "upload",
                        "error": upload_result.get("error", "Unknown error")
                    })
                    print(f"Error uploading file {file.name}: {upload_result.get('error')}")

            except Exception as e:
                job["errors"].append({
                    "file": file.name,
                    "stage": "upload",
                    "error": str(e)
                })
                print(f"Error uploading file {file.name}: {str(e)}")

        # Update job status
        job["status"] = "processing"
        print(f"Successfully uploaded {len(uploaded_files)} files to blob storage")

        # Step 2: Process each file from blob storage
        print(f"Starting processing of {len(uploaded_files)} files from blob storage")

        for uploaded_file in uploaded_files:
            try:
                file_name = uploaded_file["name"]
                blob_path = uploaded_file["blob_path"]

                print(f"Processing file {file_name} from blob storage")

                # Download file from blob storage using the same path format as upload
                file_content = blob_storage.download_file(blob_path, container_name)

                if not file_content:
                    job["errors"].append({
                        "file": file_name,
                        "stage": "download",
                        "error": "Failed to download file from blob storage"
                    })
                    print(f"Error: Failed to download file {file_name} from blob storage")
                    continue

                print(f"Successfully downloaded file {file_name} from blob storage")

                # Save to temporary file
                with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp_file:
                    tmp_file.write(file_content)
                    tmp_file_path = tmp_file.name

                print(f"Processing file {file_name} with Azure Document AI")

                # Process with Azure Document AI - same as single file upload
                result = document_ai.process_document(tmp_file_path)

                # Extract structured data
                name = result.get("name")
                suid = result.get("suid")

                # Get ID card information
                id_cards = result.get("id_cards", {})
                government_of_india_number = id_cards.get("government_of_india_number")
                income_tax_department_number = id_cards.get("income_tax_department_number")
                election_commission_number = id_cards.get("election_commission_number")

                print(f"Extracted data from file {file_name}: Name={name}, SUID={suid}")

                # Format data for frontend - same as single file upload
                detailed_data = {
                    "Name": name or "Not found",
                    "SUID": suid,
                    "Form_Responses": {
                        "Sections": {
                            "Personal": {
                                "Age": result.get("age", "Not found"),
                                "DOB": result.get("dob", "Not found"),
                                "Gender": result.get("gender", "Not found"),
                                "Address": result.get("address", "Not found"),
                                "Phone": result.get("phone", "Not found")
                            }
                        }
                    },
                    "ID_Cards": []
                }

                # Add ID cards if available
                if government_of_india_number:
                    detailed_data["ID_Cards"].append({
                        "ID_Type": "Government of India",
                        "Card_Holder_Name": name or "Not found",
                        "Aadhar_Number": government_of_india_number,
                        "Gender": result.get("gender", "Not found"),
                        "Address": result.get("address", "Not found")
                    })

                if income_tax_department_number:
                    detailed_data["ID_Cards"].append({
                        "ID_Type": "Income Tax Department",
                        "Card_Holder_Name": name or "Not found",
                        "PAN_Number": income_tax_department_number
                    })

                if election_commission_number:
                    detailed_data["ID_Cards"].append({
                        "ID_Type": "Election Commission of India",
                        "Card_Holder_Name": name or "Not found",
                        "EPIC_Number": election_commission_number
                    })

                # Add page details
                detailed_data["Page_Details"] = {}
                for j, page_text in enumerate(result.get("raw_text", [])):
                    detailed_data["Page_Details"][f"Page_{j+1}"] = {
                        "Text": page_text[:500] + ("..." if len(page_text) > 500 else ""),
                        "Extracted_Name": name or "Not found",
                        "Extracted_SUID": suid or "Not found"
                    }

                # Search through Page_Details for ID information that might have been missed
                search_page_details_for_ids(detailed_data)

                # Update ID information from detailed_data
                updated_aadhar = None
                updated_pan = None
                updated_epic = None

                # Get updated ID information from ID_Cards
                for card in detailed_data.get("ID_Cards", []):
                    if card.get("ID_Type") == "Government of India" and card.get("Aadhar_Number"):
                        updated_aadhar = card.get("Aadhar_Number")
                    elif card.get("ID_Type") == "Income Tax Department" and card.get("PAN_Number"):
                        updated_pan = card.get("PAN_Number")
                    elif card.get("ID_Type") == "Election Commission of India" and card.get("EPIC_Number"):
                        updated_epic = card.get("EPIC_Number")

                # Create result object - same as single file upload
                result_obj = {
                    "id": str(uuid.uuid4()),
                    "fileName": file_name,
                    "timestamp": datetime.now().isoformat(),
                    "text": "\n\n".join(result.get("raw_text", [""])) if result.get("raw_text") else "",
                    "entities": {
                        "name": name,
                        "suid": suid,
                        "pan": updated_pan or income_tax_department_number,
                        "epic": updated_epic or election_commission_number,
                        "aadhar": updated_aadhar or government_of_india_number,
                        "age": result.get("age"),
                        "dob": result.get("dob"),
                        "gender": result.get("gender"),
                        "address": result.get("address"),
                        "phone": result.get("phone")
                    },
                    "detailedData": detailed_data
                }

                print(f"Created result object for file {file_name}")

                # Step 3: Save to database using the same method as single file upload
                print(f"Saving file {file_name} to database with SUID: {suid}")

                # Create a result object for the frontend
                result_obj_for_db = {
                    "id": str(uuid.uuid4()),
                    "fileName": file_name,
                    "timestamp": datetime.now().isoformat(),
                    "text": "\n\n".join(result.get("raw_text", [""])) if result.get("raw_text") else "",
                    "entities": {
                        "name": name,
                        "suid": suid,
                        "pan": updated_pan or income_tax_department_number,
                        "epic": updated_epic or election_commission_number,
                        "aadhar": updated_aadhar or government_of_india_number,
                        "age": result.get("age"),
                        "dob": result.get("dob"),
                        "gender": result.get("gender"),
                        "address": result.get("address"),
                        "phone": result.get("phone")
                    },
                    "detailedData": detailed_data
                }

                # Convert to JSON string
                result_obj_json = json.dumps(result_obj_for_db)

                # Use direct PostgreSQL connection to save to database
                try:
                    import psycopg2

                    # Use the direct connection string from environment variables
                    postgres_url = os.getenv("POSTGRES_URL_NON_POOLING")

                    # Connect to PostgreSQL using the connection string
                    conn = psycopg2.connect(postgres_url)

                    # Create cursor
                    cur = conn.cursor()

                    # Check if table exists
                    cur.execute("SELECT EXISTS (SELECT FROM information_schema.tables WHERE table_name = 'documents')")
                    table_exists = cur.fetchone()[0]

                    if not table_exists:
                        # Create table if it doesn't exist
                        try:
                            # First try to create the uuid-ossp extension if it doesn't exist
                            cur.execute("CREATE EXTENSION IF NOT EXISTS \"uuid-ossp\";")
                            conn.commit()

                            # Create table with the correct schema
                            cur.execute("""
                            CREATE TABLE IF NOT EXISTS documents (
                                id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
                                file_name TEXT NOT NULL,
                                extracted_data JSONB NOT NULL,
                                suid TEXT NOT NULL,
                                created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                            )
                            """)
                            conn.commit()
                            print("Created documents table")
                        except Exception as table_error:
                            print(f"Error creating table: {str(table_error)}")

                            # Try a simpler schema without UUID
                            try:
                                cur.execute("""
                                CREATE TABLE IF NOT EXISTS documents (
                                    id SERIAL PRIMARY KEY,
                                    file_name TEXT NOT NULL,
                                    extracted_data JSONB NOT NULL,
                                    suid TEXT NOT NULL,
                                    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
                                )
                                """)
                                conn.commit()
                                print("Created documents table with SERIAL primary key")
                            except Exception as simple_table_error:
                                print(f"Error creating simple table: {str(simple_table_error)}")
                                raise

                    # Check if document with this SUID already exists
                    cur.execute("SELECT id FROM documents WHERE suid = %s", (suid,))
                    existing_doc = cur.fetchone()

                    if existing_doc:
                        # Update existing document
                        cur.execute(
                            "UPDATE documents SET file_name = %s, extracted_data = %s WHERE id = %s",
                            (file_name, result_obj_json, existing_doc[0])
                        )
                        print(f"Updated existing document with ID: {existing_doc[0]}")
                        save_result = {"success": True, "id": existing_doc[0]}
                    else:
                        # Insert new document
                        cur.execute(
                            "INSERT INTO documents (file_name, extracted_data, suid) VALUES (%s, %s, %s) RETURNING id",
                            (file_name, result_obj_json, suid or f"DOC-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}")
                        )
                        new_id = cur.fetchone()[0]
                        print(f"Inserted new document with ID: {new_id}")
                        save_result = {"success": True, "id": new_id}

                    # Commit changes
                    conn.commit()

                    # Close cursor and connection
                    cur.close()
                    conn.close()

                except Exception as e:
                    print(f"Error saving to PostgreSQL: {str(e)}")

                    # Fallback to Supabase REST API
                    try:
                        print("Trying fallback to Supabase REST API...")
                        import httpx

                        # Get Supabase credentials
                        supabase_url = os.getenv("SUPABASE_URL")
                        supabase_key = os.getenv("SUPABASE_KEY")

                        if not supabase_url or not supabase_key:
                            print("Supabase credentials not found in environment variables")
                            save_result = {"success": False, "error": "Supabase credentials not found"}
                        else:
                            # Prepare headers
                            headers = {
                                "apikey": supabase_key,
                                "Authorization": f"Bearer {supabase_key}",
                                "Content-Type": "application/json",
                                "Prefer": "return=representation"
                            }

                            # Prepare data
                            document_data = {
                                "file_name": file_name,
                                "extracted_data": result_obj_json,
                                "suid": suid or f"DOC-{datetime.now().strftime('%Y%m%d%H%M%S')}-{str(uuid.uuid4())[:8]}"
                            }

                            # Send request
                            with httpx.Client() as client:
                                response = client.post(
                                    f"{supabase_url}/rest/v1/documents",
                                    headers=headers,
                                    json=document_data,
                                    timeout=30.0
                                )

                                if response.status_code in (200, 201, 204):
                                    print(f"Successfully saved file {file_name} to database using REST API")
                                    save_result = {"success": True, "id": "rest-api-save"}
                                else:
                                    print(f"REST API save failed: {response.status_code}, {response.text}")

                                    # Try one more time with service role key
                                    service_key = os.getenv("SUPABASE_SERVICE_ROLE_KEY")
                                    if service_key:
                                        print("Trying with service role key...")
                                        admin_headers = {
                                            "apikey": service_key,
                                            "Authorization": f"Bearer {service_key}",
                                            "Content-Type": "application/json",
                                            "Prefer": "return=representation"
                                        }

                                        service_response = client.post(
                                            f"{supabase_url}/rest/v1/documents",
                                            headers=admin_headers,
                                            json=document_data,
                                            timeout=30.0
                                        )

                                        if service_response.status_code in (200, 201, 204):
                                            print(f"Successfully saved file {file_name} to database using service role key")
                                            save_result = {"success": True, "id": "service-role-save"}
                                        else:
                                            print(f"Service role save failed: {service_response.status_code}, {service_response.text}")
                                            save_result = {"success": False, "error": f"All save methods failed"}
                                    else:
                                        save_result = {"success": False, "error": f"REST API save failed: {response.status_code}, {response.text}"}
                    except Exception as rest_error:
                        print(f"Error using REST API fallback: {str(rest_error)}")
                        save_result = {"success": False, "error": str(e)}

                print(f"Database save result for {file_name}: {save_result}")

                if "success" in save_result and save_result["success"]:
                    print(f"Successfully saved file {file_name} to database with ID: {save_result.get('id')}")
                else:
                    print(f"Failed to save file {file_name} to database: {save_result.get('error')}")
                    job["errors"].append({
                        "file": file_name,
                        "stage": "database",
                        "error": save_result.get("error", "Unknown error")
                    })

                # Add to results
                job["results"].append(result_obj)

                # Update processed files count
                job["processed_files"] += 1

                # Print progress update for debugging
                print(f"Progress update: {job['processed_files']}/{job['total_files']} files processed ({(job['processed_files']/job['total_files']*100):.1f}%)")

                # Clean up temporary file
                os.unlink(tmp_file_path)

            except Exception as e:
                print(f"Error processing file {uploaded_file['name']}: {str(e)}")
                job["errors"].append({
                    "file": uploaded_file["name"],
                    "stage": "processing",
                    "error": str(e)
                })

                # Still increment processed files count
                job["processed_files"] += 1

                # Print progress update for debugging
                print(f"Progress update (with error): {job['processed_files']}/{job['total_files']} files processed ({(job['processed_files']/job['total_files']*100):.1f}%)")

        # Update job status
        job["status"] = "completed"
        print(f"Bulk upload job {job_id} completed. Processed {job['processed_files']} files.")

    except Exception as e:
        print(f"Error in bulk upload processing: {str(e)}")
        if job_id in bulk_upload_jobs:
            bulk_upload_jobs[job_id]["status"] = "failed"
            bulk_upload_jobs[job_id]["error"] = str(e)
