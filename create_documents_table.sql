-- Create the documents table
CREATE TABLE IF NOT EXISTS public.documents (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  file_name TEXT NOT NULL,
  suid TEXT,
  extracted_data JSONB,
  status TEXT DEFAULT 'completed',
  created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  updated_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  pdf_data BYTEA
);

-- Create the extension for UUID generation if it doesn't exist
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";

-- Add indexes for better performance
CREATE INDEX IF NOT EXISTS idx_documents_file_name ON public.documents(file_name);
CREATE INDEX IF NOT EXISTS idx_documents_created_at ON public.documents(created_at);
CREATE INDEX IF NOT EXISTS idx_documents_suid ON public.documents(suid);

-- Allow public access for development purposes
ALTER TABLE public.documents ENABLE ROW LEVEL SECURITY;
DROP POLICY IF EXISTS "Allow public access for development" ON public.documents;
CREATE POLICY "Allow public access for development"
  ON public.documents
  FOR ALL
  USING (true);

-- Create a function to update the updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
   NEW.updated_at = NOW();
   RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create a trigger to automatically update the updated_at column
CREATE TRIGGER update_documents_updated_at
BEFORE UPDATE ON public.documents
FOR EACH ROW
EXECUTE FUNCTION update_updated_at_column();

-- Insert sample data
INSERT INTO public.documents (file_name, suid, extracted_data, status)
VALUES
  ('Sample_Document.pdf',
   '4/9/2/127A_U/G/14_1',
   '{
      "Name": "John Doe",
      "SUID": "4/9/2/127A_U/G/14_1",
      "Form_Responses": {
        "Sections": {
          "Personal": {
            "Age": "35",
            "DOB": "15/05/1988",
            "Gender": "Male",
            "Address": "123 Main St, Mumbai, India"
          }
        }
      },
      "ID_Cards": [
        {
          "ID_Type": "Government of India",
          "Card_Holder_Name": "John Doe",
          "Aadhar_Number": "1234 5678 9012",
          "Gender": "Male",
          "Address": "123 Main St, Mumbai, India"
        },
        {
          "ID_Type": "Income Tax Department",
          "Card_Holder_Name": "John Doe",
          "PAN_Number": "ABCDE1234F"
        }
      ],
      "Page_Details": {
        "Page_1": {
          "Text": "Sample text from page 1",
          "Extracted_Name": "John Doe",
          "Extracted_SUID": "4/9/2/127A_U/G/14_1"
        }
      }
    }',
   'completed'),
  ('Sample_Document_2.pdf',
   '5/10/3/128B_V/H/15_2',
   '{
      "Name": "Jane Smith",
      "SUID": "5/10/3/128B_V/H/15_2",
      "Form_Responses": {
        "Sections": {
          "Personal": {
            "Age": "28",
            "DOB": "22/09/1995",
            "Gender": "Female",
            "Address": "456 Park Ave, Delhi, India"
          }
        }
      },
      "ID_Cards": [
        {
          "ID_Type": "Government of India",
          "Card_Holder_Name": "Jane Smith",
          "Aadhar_Number": "9876 5432 1098",
          "Gender": "Female",
          "Address": "456 Park Ave, Delhi, India"
        },
        {
          "ID_Type": "Election Commission of India",
          "Card_Holder_Name": "Jane Smith",
          "EPIC_Number": "MT/10/053/017854"
        }
      ],
      "Page_Details": {
        "Page_1": {
          "Text": "Sample text from page 1",
          "Extracted_Name": "Jane Smith",
          "Extracted_SUID": "5/10/3/128B_V/H/15_2"
        }
      }
    }',
   'completed');
