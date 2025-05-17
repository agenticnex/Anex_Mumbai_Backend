-- Create documents table
CREATE TABLE IF NOT EXISTS documents (
    id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
    file_name TEXT NOT NULL,
    file_content TEXT NOT NULL, -- Base64 encoded PDF content
    extracted_data JSONB NOT NULL, -- JSON containing all extracted data
    suid TEXT NOT NULL, -- Document SUID
    created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW()
);

-- Create index on SUID for faster lookups
CREATE INDEX IF NOT EXISTS idx_documents_suid ON documents(suid);

-- Create RLS policies for security
ALTER TABLE documents ENABLE ROW LEVEL SECURITY;

-- Allow authenticated users to select documents
CREATE POLICY select_documents ON documents
    FOR SELECT
    TO authenticated
    USING (true);

-- Allow authenticated users to insert documents
CREATE POLICY insert_documents ON documents
    FOR INSERT
    TO authenticated
    WITH CHECK (true);

-- Allow authenticated users to update their own documents
CREATE POLICY update_documents ON documents
    FOR UPDATE
    TO authenticated
    USING (true);

-- Allow authenticated users to delete their own documents
CREATE POLICY delete_documents ON documents
    FOR DELETE
    TO authenticated
    USING (true);
