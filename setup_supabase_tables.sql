-- Create the ocr_processing_history table
CREATE TABLE IF NOT EXISTS public.ocr_processing_history (
  id UUID PRIMARY KEY DEFAULT uuid_generate_v4(),
  file_name TEXT NOT NULL,
  extracted_data JSONB,
  status TEXT DEFAULT 'completed',
  user_id UUID NOT NULL,
  processed_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
  sheet_name TEXT,
  sheet_url TEXT
);

-- Add indexes for better performance
CREATE INDEX IF NOT EXISTS idx_ocr_processing_history_user_id ON public.ocr_processing_history(user_id);
CREATE INDEX IF NOT EXISTS idx_ocr_processing_history_file_name ON public.ocr_processing_history(file_name);
CREATE INDEX IF NOT EXISTS idx_ocr_processing_history_processed_at ON public.ocr_processing_history(processed_at);

-- Set up RLS (Row Level Security) policies
ALTER TABLE public.ocr_processing_history ENABLE ROW LEVEL SECURITY;

-- Create policy to allow users to see only their own records
CREATE POLICY "Users can view their own processing history"
  ON public.ocr_processing_history
  FOR SELECT
  USING (auth.uid() = user_id);

-- Create policy to allow users to insert their own records
CREATE POLICY "Users can insert their own processing history"
  ON public.ocr_processing_history
  FOR INSERT
  WITH CHECK (auth.uid() = user_id);

-- Create policy to allow users to update their own records
CREATE POLICY "Users can update their own processing history"
  ON public.ocr_processing_history
  FOR UPDATE
  USING (auth.uid() = user_id);

-- Create policy to allow users to delete their own records
CREATE POLICY "Users can delete their own processing history"
  ON public.ocr_processing_history
  FOR DELETE
  USING (auth.uid() = user_id);

-- Allow anonymous access for development purposes
CREATE POLICY "Allow anonymous access for development"
  ON public.ocr_processing_history
  FOR ALL
  USING (true);
