-- Create the ocr_processing_history table
CREATE TABLE IF NOT EXISTS public.ocr_processing_history (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  file_name TEXT NOT NULL,
  extracted_data JSONB,
  status TEXT DEFAULT 'completed',
  user_id UUID NOT NULL DEFAULT '00000000-0000-0000-0000-000000000000',
  processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  sheet_name TEXT,
  sheet_url TEXT
);

-- Add indexes for better performance
CREATE INDEX IF NOT EXISTS idx_ocr_processing_history_file_name ON public.ocr_processing_history(file_name);
CREATE INDEX IF NOT EXISTS idx_ocr_processing_history_processed_at ON public.ocr_processing_history(processed_at);

-- Allow anonymous access for development purposes
ALTER TABLE public.ocr_processing_history ENABLE ROW LEVEL SECURITY;
CREATE POLICY "Allow anonymous access for development"
  ON public.ocr_processing_history
  FOR ALL
  USING (true);
