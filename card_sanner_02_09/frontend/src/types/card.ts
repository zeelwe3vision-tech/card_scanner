export type SourceType = "scan" | "pdf" | "url";

// =====================================================
// SAVED CARD - EXACT SUPABASE DATA
// =====================================================

export interface BusinessCard {
  id: string;

  owner_name: string;
  company_name: string | null;
  designation: string | null;

  address: string | null;

  qr_codes: string[] | null;

  email: string | null;
  phone: string | null;

  gst_number: string | null;
  company_logo: string | null;

  instagram_url: string | null;
  website_url: string | null;
  facebook_url: string | null;
  linkedin_url: string | null;

  other_details: string | null;
  qr_raw: string | null;

  created_at: string;
  updated_at: string;
}


// =====================================================
// QR DETAIL
// =====================================================

export interface QrDetail {
  raw: string;

  type:
    | "instagram"
    | "whatsapp"
    | "phone"
    | "email"
    | "location"
    | "website"
    | "other";

  label: string;

  url: string | null;
}


// =====================================================
// EXTRACTED CARD
// Scanner can contain additional temporary information
// =====================================================

export interface ExtractedCard {
  owner_name: string;

  company_name?: string | null;
  designation?: string | null;

  qr_codes?: string[] | null;
  qr_details?: QrDetail[] | null;

  address?: string | null;

  email?: string | null;
  phone?: string | null;

  gst_number?: string | null;
  company_logo?: string | null;

  website_url?: string | null;
  instagram_url?: string | null;
  facebook_url?: string | null;
  linkedin_url?: string | null;

  other_details?: string | null;

  // Temporary scanner/review information
  front_image_url?: string | null;
  back_image_url?: string | null;

  qr_raw?: string | null;

  source_type?: SourceType | null;

  original_file_url?: string | null;
}


// =====================================================
// API RESPONSE
// =====================================================

export interface ApiResponse<T> {
  success: boolean;

  message?: string;

  data?: T;

  card?: T;
}