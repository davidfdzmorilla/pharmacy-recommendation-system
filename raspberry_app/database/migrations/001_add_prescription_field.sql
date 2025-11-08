-- Migration: Add requires_prescription field to products table
-- Purpose: Enable legal compliance with Spanish medication regulation
-- Date: 2025-11-08

-- Add new column for prescription requirement
ALTER TABLE products ADD COLUMN requires_prescription BOOLEAN NOT NULL DEFAULT 0;

-- Create index for fast filtering of OTC vs prescription products
CREATE INDEX IF NOT EXISTS idx_products_prescription ON products(requires_prescription);

-- Update trigger to ensure prescription field is considered
-- (No changes needed to existing trigger)
