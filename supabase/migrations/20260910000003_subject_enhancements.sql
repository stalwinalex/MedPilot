-- Migration 003: Subject enhancements (faculty, academic_year)
ALTER TABLE public.subjects
ADD COLUMN IF NOT EXISTS faculty VARCHAR(100) DEFAULT '',
ADD COLUMN IF NOT EXISTS academic_year VARCHAR(50) DEFAULT '';
