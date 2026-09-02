import {
  BusinessCard,
  ExtractedCard,
  ApiResponse,
} from "@/types/card";

const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// =====================================================
// AUTH TYPES
// =====================================================

interface AuthUser {
  id: string;
  email: string;
  full_name: string | null;
}

interface AuthResponse {
  success: boolean;
  message: string;
  user: AuthUser;
  access_token?: string;
}

interface LogoutResponse {
  success: boolean;
  message: string;
}

interface RetentionResponse {
  success: boolean;
  message?: string;
  retention_days: number | null;
}
// =====================================================
// PDF RESPONSE TYPES
// =====================================================

interface MultiplePdfResponse {
  success: boolean;
  message: string;
  cards?: ExtractedCard[];
  card?: ExtractedCard | ExtractedCard[];
  count?: number;
}

// =====================================================
// COMMON RESPONSE HANDLER
// =====================================================

async function handleResponse<T>(
  response: Response
): Promise<T> {
  const contentType =
    response.headers.get("content-type");

  // -----------------------------------------
  // Backend did not return JSON
  // -----------------------------------------

  if (!contentType?.includes("application/json")) {
    const text = await response.text();

    console.error(
      "Invalid backend response:",
      text
    );

    throw new Error(
      text ||
        "Backend returned an invalid response"
    );
  }

  const data = await response.json();

  // -----------------------------------------
  // Backend returned an error
  // -----------------------------------------

  if (!response.ok) {
    console.error(
      "Backend error:",
      data
    );

    let errorMessage =
      "Something went wrong";

    if (
      typeof data?.detail === "string"
    ) {
      errorMessage = data.detail;

    } else if (
      typeof data?.message === "string"
    ) {
      errorMessage = data.message;

    } else if (data?.detail) {
      errorMessage = JSON.stringify(
        data.detail,
        null,
        2
      );

    } else if (data) {
      errorMessage = JSON.stringify(
        data,
        null,
        2
      );
    }

    throw new Error(
      errorMessage
    );
  }

  return data;
}

  function getAuthHeaders(): Record<string, string> {
    if (typeof window === "undefined") {
      return {};
    }

    const token = localStorage.getItem(
      "card_scanner_token"
    );

    if (!token) {
      return {};
    }

    return {
      Authorization: `Bearer ${token}`,
    };
  }


// =====================================================
// CREATE ACCOUNT
// =====================================================

export async function signupUser(
  fullName: string,
  email: string,
  password: string
): Promise<AuthResponse> {
  const response = await fetch(
    `${API_BASE}/auth/signup`,
    {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({
        full_name: fullName,
        email: email.trim(),
        password,
      }),
    }
  );

  return handleResponse<AuthResponse>(
    response
  );
}

// =====================================================
// LOGIN
// =====================================================

export async function loginUser(
  email: string,
  password: string
): Promise<AuthResponse> {
  const response = await fetch(
    `${API_BASE}/auth/login`,
    {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({
        email: email.trim(),
        password,
      }),
    }
  );

  return handleResponse<AuthResponse>(
    response
  );
}

// =====================================================
// GET CARD RETENTION SETTING
// =====================================================

export async function getRetention():
  Promise<RetentionResponse> {
  const response = await fetch(
    `${API_BASE}/auth/retention`,
    {
      method: "GET",

      headers: {
        ...getAuthHeaders(),
      },

      cache: "no-store",
    }
  );

  return handleResponse<RetentionResponse>(
    response
  );
}

// =====================================================
// UPDATE CARD RETENTION SETTING
// =====================================================

export async function updateRetention(
  retentionDays: number | null
): Promise<RetentionResponse> {
  const response = await fetch(
    `${API_BASE}/auth/retention`,
    {
      method: "PUT",

      headers: {
        "Content-Type": "application/json",
        ...getAuthHeaders(),
      },

      body: JSON.stringify({
        retention_days: retentionDays,
      }),
    }
  );

  return handleResponse<RetentionResponse>(
    response
  );
}

// =====================================================
// UPLOAD FROM CAMERA / IMAGE
// =====================================================

export async function uploadScan(
  frontFile: File,
  backFile?: File | null
): Promise<
  ApiResponse<ExtractedCard>
> {
  const formData = new FormData();

  // MUST MATCH FASTAPI PARAMETER NAMES

  formData.append(
    "front_file",
    frontFile
  );

  if (backFile) {
    formData.append(
      "back_file",
      backFile
    );
  }

  const response = await fetch(
    `${API_BASE}/api/cards/scan`,
    {
      method: "POST",
      body: formData,
    }
  );

  return handleResponse<
    ApiResponse<ExtractedCard>
  >(response);
}

export async function uploadPdf(
  file: File
): Promise<
  ApiResponse<ExtractedCard>
> {
  const formData = new FormData();

  // IMPORTANT:
  // Backend expects "files", not "file".

  formData.append(
    "files",
    file
  );

  const response = await fetch(
    `${API_BASE}/api/cards/pdf`,
    {
      method: "POST",
      body: formData,
    }
  );

  const data =
    await handleResponse<
      MultiplePdfResponse
    >(response);

  let extractedCard:
    | ExtractedCard
    | undefined;

  if (
    Array.isArray(data.cards) &&
    data.cards.length > 0
  ) {
    extractedCard =
      data.cards[0];

  } else if (
    data.card &&
    !Array.isArray(data.card)
  ) {
    extractedCard =
      data.card;
  } else if (
    Array.isArray(data.card) &&
    data.card.length > 0
  ) {
    extractedCard =
      data.card[0];
  }

  if (!extractedCard) {
    throw new Error(
      data.message ||
        "No business card details were extracted from the PDF."
    );
  }

  return {
    success: true,
    message:
      data.message ||
      "Business card PDF processed successfully",
    card: extractedCard,
  };
}

export async function uploadPdfs(
  files: File[]
): Promise<
  ApiResponse<ExtractedCard[]>
> {
  // -----------------------------------------
  // Validate files
  // -----------------------------------------

  if (
    !files ||
    files.length === 0
  ) {
    throw new Error(
      "Please select at least one PDF file."
    );
  }

  // -----------------------------------------
  // Create multipart FormData
  // -----------------------------------------

  const formData = new FormData();

  files.forEach(
    (file, index) => {
      console.log(
        `Adding PDF ${index + 1}/${files.length}:`,
        file.name
      );

      formData.append(
        "files",
        file
      );
    }
  );

  // -----------------------------------------
  // Send ONE request containing ALL PDFs
  // -----------------------------------------

  console.log(
    `Uploading ${files.length} PDF(s) to backend...`
  );

  const response = await fetch(
    `${API_BASE}/api/cards/pdf`,
    {
      method: "POST",

      // IMPORTANT:
      // Do NOT manually set Content-Type.
      //
      // Browser automatically sets:
      //
      // multipart/form-data;
      // boundary=...
      //
      body: formData,
    }
  );

  // -----------------------------------------
  // Read backend response
  // -----------------------------------------

  const data =
    await handleResponse<
      MultiplePdfResponse
    >(response);

  // -----------------------------------------
  // Extract cards
  // -----------------------------------------

  let extractedCards:
    ExtractedCard[] = [];

  // Preferred new response:
  //
  // cards: [...]
  if (
    Array.isArray(data.cards)
  ) {
    extractedCards =
      data.cards;
  }

  // -----------------------------------------
  // Backward compatibility
  // -----------------------------------------
  //
  // If backend sends:
  //
  // card: [...]
  //
  // use it.

  else if (
    Array.isArray(data.card)
  ) {
    extractedCards =
      data.card;
  }

  // -----------------------------------------
  // Single-card fallback
  // -----------------------------------------
  //
  // If backend sends:
  //
  // card: {...}
  //
  // convert it to:
  //
  // [{...}]
  //
  else if (
    data.card &&
    !Array.isArray(data.card)
  ) {
    extractedCards = [
      data.card,
    ];
  }

  // -----------------------------------------
  // No cards
  // -----------------------------------------

  if (
    extractedCards.length === 0
  ) {
    return {
      success: false,

      message:
        data.message ||
        "No business card details were extracted from the PDFs.",

      card: [],
    };
  }

  // -----------------------------------------
  // Debug output
  // -----------------------------------------

  console.log(
    "========================================"
  );

  console.log(
    "TOTAL PDFs UPLOADED:",
    files.length
  );

  console.log(
    "TOTAL CARDS EXTRACTED:",
    extractedCards.length
  );

  extractedCards.forEach(
    (card, index) => {
      console.log(
        `CARD ${index + 1}:`,
        card
      );

      console.log(
        `CARD ${index + 1} QR CODES:`,
        card.qr_codes
      );

      console.log(
        `CARD ${index + 1} QR COUNT:`,
        Array.isArray(
          card.qr_codes
        )
          ? card.qr_codes.length
          : 0
      );
    }
  );

  console.log(
    "========================================"
  );

  // -----------------------------------------
  // Return all cards
  // -----------------------------------------

  return {
    success: true,

    message:
      data.message ||
      `Successfully processed ${extractedCards.length} ${
        extractedCards.length === 1
          ? "PDF"
          : "PDFs"
      }.`,

    card: extractedCards,
  };
}

// =====================================================
// UPLOAD FROM URL
// =====================================================

export async function uploadUrl(
  url: string
): Promise<
  ApiResponse<ExtractedCard>
> {
  const response = await fetch(
    `${API_BASE}/api/cards/url`,
    {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({
        url: url.trim(),
      }),
    }
  );

  return handleResponse<
    ApiResponse<ExtractedCard>
  >(response);
}


export async function saveCard(
  card: ExtractedCard
): Promise<
  ApiResponse<BusinessCard>
> {
  const response = await fetch(
    `${API_BASE}/api/cards`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        ...getAuthHeaders(),
      },

      body: JSON.stringify({
        ...card,

        // Make sure all QR codes are preserved.
        qr_codes:
          Array.isArray(
            card.qr_codes
          )
            ? card.qr_codes
            : [],

        // Backward-compatible first QR.
        qr_raw:
          card.qr_raw ??
          (
            Array.isArray(
              card.qr_codes
            ) &&
            card.qr_codes.length > 0
              ? card.qr_codes[0]
              : null
          ),
      }),
    }
  );

  return handleResponse<
    ApiResponse<BusinessCard>
  >(response);
}

// =====================================================
// GET ALL CARDS
// =====================================================

export async function getCards():
  Promise<
    ApiResponse<BusinessCard[]>
  > {
  const response = await fetch(
    `${API_BASE}/api/cards`,
    {
      method: "GET",

      headers: {
        ...getAuthHeaders(),
      },

      cache: "no-store",
    }
  );

  return handleResponse<
    ApiResponse<BusinessCard[]>
  >(response);
}
// =====================================================
// DELETE CARD
// =====================================================

export async function deleteCard(
  id: string
): Promise<
  ApiResponse<null>
> {
  const response = await fetch(
    `${API_BASE}/api/cards/${id}`,
    {
      method: "DELETE",

      headers: {
        ...getAuthHeaders(),
      },
    }
  );

  return handleResponse<
    ApiResponse<null>
  >(response);
}
// =====================================================
// LOGOUT
// =====================================================

export async function logoutUser(
  userId: string
): Promise<LogoutResponse> {
  const response = await fetch(
    `${API_BASE}/auth/logout`,
    {
      method: "POST",

      headers: {
        "Content-Type": "application/json",
      },

      body: JSON.stringify({
        user_id: userId,
      }),
    }
  );

  return handleResponse<LogoutResponse>(
    response
  );
}