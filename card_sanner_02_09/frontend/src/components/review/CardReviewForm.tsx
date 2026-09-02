"use client";

import React, { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import {
  Building2,
  Save,
  ArrowLeft,
  ArrowRight,
  QrCode,
  MapPin,
  ExternalLink,
  Image as ImageIcon,
} from "lucide-react";

import { ExtractedCard } from "@/types/card";
import { saveCard, getCards } from "@/services/api";

import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import LoadingSpinner from "@/components/ui/LoadingSpinner";

export default function CardReviewForm() {
  const router = useRouter();

  // ============================================================
  // MULTIPLE CARD STATE
  // ============================================================

  const [cards, setCards] = useState<ExtractedCard[]>([]);
  const [currentIndex, setCurrentIndex] = useState(0);

  // ============================================================
  // DUPLICATE CONFIRMATION
  // ============================================================

  const [showDuplicateConfirm, setShowDuplicateConfirm] =
    useState(false);

  const [pendingSaveData, setPendingSaveData] =
    useState<any>(null);

  // ============================================================
  // UI STATE
  // ============================================================

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [isReady, setIsReady] = useState(false);

  // ============================================================
  // EMPTY CARD
  // ============================================================

  const createEmptyCard = (): ExtractedCard => ({
    owner_name: "",
    designation: "",
    company_name: "",
    address: "",
    email: "",
    phone: "",
    gst_number: "",

    company_logo: null,

    website_url: "",
    instagram_url: "",
    facebook_url: "",
    linkedin_url: "",

    front_image_url: null,
    back_image_url: null,

    source_type: "scan",
    original_file_url: null,

    qr_raw: null,
    qr_codes: [],

    other_details: "",
  });

  // ============================================================
  // NORMALIZE CARD
  // ============================================================

  const normalizeCard = (card: any): ExtractedCard => {
    let qrCodes: string[] = [];

    // ----------------------------------------------------------
    // NEW FORMAT
    // ----------------------------------------------------------

    if (Array.isArray(card?.qr_codes)) {
      qrCodes = card.qr_codes
        .filter(
          (qr: unknown): qr is string =>
            typeof qr === "string" && qr.trim().length > 0
        )
        .map((qr: string) => qr.trim());
    }

    // ----------------------------------------------------------
    // OLD FORMAT
    // ----------------------------------------------------------

    if (qrCodes.length === 0 && card?.qr_raw) {
      qrCodes = String(card.qr_raw)
        .split(" ||| ")
        .map((qr: string) => qr.trim())
        .filter(Boolean);
    }

    return {
      owner_name: card?.owner_name ?? "",
      designation: card?.designation ?? "",
      company_name: card?.company_name ?? "",
      address: card?.address ?? "",
      email: card?.email ?? "",
      phone: card?.phone ?? "",
      gst_number: card?.gst_number ?? "",

      company_logo: card?.company_logo ?? null,

      website_url: card?.website_url ?? "",
      instagram_url: card?.instagram_url ?? "",
      facebook_url: card?.facebook_url ?? "",
      linkedin_url: card?.linkedin_url ?? "",

      front_image_url: card?.front_image_url ?? null,
      back_image_url: card?.back_image_url ?? null,

      source_type: card?.source_type ?? "scan",
      original_file_url: card?.original_file_url ?? null,

      qr_raw: qrCodes.length > 0 ? qrCodes[0] : null,

      qr_codes: qrCodes,

      other_details: card?.other_details ?? "",
    };
  };

  // ============================================================
  // LOAD EXTRACTED CARDS
  // ============================================================

  useEffect(() => {
    const loadExtractedCards = () => {
      try {
        // ======================================================
        // MULTIPLE CARDS
        // ======================================================

        const storedCards =
          sessionStorage.getItem("extractedCards");

        if (storedCards) {
          const parsedCards = JSON.parse(storedCards);

          if (
            Array.isArray(parsedCards) &&
            parsedCards.length > 0
          ) {
            const normalizedCards =
              parsedCards.map(normalizeCard);

            console.log(
              "========================================"
            );

            console.log(
              "MULTIPLE EXTRACTED CARDS:",
              normalizedCards
            );

            console.log(
              "TOTAL CARDS:",
              normalizedCards.length
            );

            console.log(
              "========================================"
            );

            setCards(normalizedCards);
            setCurrentIndex(0);
            setIsReady(true);

            return;
          }
        }

        // ======================================================
        // SINGLE CARD FALLBACK
        // ======================================================

        const storedCard =
          sessionStorage.getItem("extractedCard");

        if (!storedCard) {
          router.push("/");
          return;
        }

        const parsedCard = JSON.parse(storedCard);

        const normalizedCard =
          normalizeCard(parsedCard);

        console.log(
          "SINGLE EXTRACTED CARD:",
          normalizedCard
        );

        setCards([normalizedCard]);
        setCurrentIndex(0);
        setIsReady(true);
      } catch (err) {
        console.error(
          "LOAD EXTRACTED CARDS ERROR:",
          err
        );

        setError(
          "Invalid extracted card data"
        );

        setIsReady(true);
      }
    };

    loadExtractedCards();
  }, [router]);

  // ============================================================
  // KEEP FORM DATA SYNCHRONIZED WITH CURRENT CARD
  // ============================================================

  const [formData, setFormData] =
    useState<ExtractedCard>(
      createEmptyCard()
    );

  useEffect(() => {
    if (
      cards.length > 0 &&
      cards[currentIndex]
    ) {
      setFormData(
        normalizeCard(
          cards[currentIndex]
        )
      );
    }
  }, [cards, currentIndex]);

  // ============================================================
  // HANDLE FORM CHANGE
  // ============================================================

  const handleChange = (
    e: React.ChangeEvent<
      HTMLInputElement | HTMLTextAreaElement
    >
  ) => {
    const {
      name,
      value,
    } = e.target;

    setFormData((previous) => ({
      ...previous,
      [name]: value,
    }));
  };

  // ============================================================
  // PREPARE SAVE DATA
  // ============================================================

  const prepareSaveData = (
    card: ExtractedCard
  ) => {
    // ----------------------------------------------------------
    // CLEAN ALL QR CODES
    // ----------------------------------------------------------

    let qrCodes: string[] = [];

    if (Array.isArray(card.qr_codes)) {
      qrCodes = card.qr_codes
        .filter(
          (qr): qr is string =>
            typeof qr === "string" &&
            qr.trim().length > 0
        )
        .map((qr) => qr.trim());
    }

    // ----------------------------------------------------------
    // BACKWARD COMPATIBILITY
    // ----------------------------------------------------------

    if (
      qrCodes.length === 0 &&
      card.qr_raw
    ) {
      qrCodes = String(card.qr_raw)
        .split(" ||| ")
        .map((qr) => qr.trim())
        .filter(Boolean);
    }

    // ----------------------------------------------------------
    // REMOVE DUPLICATE QR URLs
    // ----------------------------------------------------------

    qrCodes = Array.from(
      new Set(qrCodes)
    );

    // ----------------------------------------------------------
    // qr_raw
    //
    // IMPORTANT:
    //
    // If your current Supabase table DOES NOT have qr_codes,
    // we only send qr_raw.
    //
    // qr_raw contains all QR values:
    //
    // QR1 ||| QR2 ||| QR3
    //
    // ----------------------------------------------------------

    const joinedQrRaw =
      qrCodes.length > 0
        ? qrCodes.join(" ||| ")
        : null;

    const dataToSave = {
      owner_name:
        card.owner_name?.trim() ||
        "Unknown",

      designation:
        card.designation?.trim() ||
        null,

      company_name:
        card.company_name?.trim() ||
        null,

      address:
        card.address?.trim() ||
        null,

      email:
        card.email?.trim() ||
        null,

      phone:
        card.phone?.trim() ||
        null,

      gst_number:
        card.gst_number?.trim() ||
        null,

      company_logo:
        card.company_logo ||
        null,

      website_url:
        card.website_url?.trim() ||
        null,

      instagram_url:
        card.instagram_url?.trim() ||
        null,

      facebook_url:
        card.facebook_url?.trim() ||
        null,

      linkedin_url:
        card.linkedin_url?.trim() ||
        null,

      other_details:
        card.other_details?.trim() ||
        null,

      // ========================================================
      // QR DATA
      // ========================================================

      qr_raw: joinedQrRaw,
    };

    return dataToSave;
  };

  // ============================================================
  // SAVE CURRENT CARD TO DATABASE
  // ============================================================

  const saveCurrentCardToDatabase = async (
    card: ExtractedCard
  ) => {
    const dataToSave =
      prepareSaveData(card);

    console.log(
      "========================================"
    );

    console.log(
      "SAVING CARD:",
      currentIndex + 1
    );

    console.log(
      "COMPANY:",
      dataToSave.company_name
    );

    console.log(
      "QR DATA:",
      dataToSave.qr_raw
    );

    console.log(
      "========================================"
    );

    // ==========================================================
    // DUPLICATE COMPANY CHECK
    // ==========================================================

    const companyName =
      dataToSave.company_name?.trim() ||
      null;

    if (companyName) {
      const existing =
        await getCards();

      if (
        existing.success &&
        existing.data
      ) {
        const isDuplicate =
          existing.data.some(
            (existingCard: any) =>
              existingCard.company_name &&
              existingCard.company_name
                .toLowerCase()
                .trim() ===
                companyName.toLowerCase()
          );

        if (isDuplicate) {
          // ----------------------------------------------------
          // DO NOT SAVE YET
          //
          // Caller will show confirmation popup.
          // ----------------------------------------------------

          setPendingSaveData(
            dataToSave
          );

          setShowDuplicateConfirm(
            true
          );

          return false;
        }
      }
    }

    // ==========================================================
    // SAVE
    // ==========================================================

    const response =
      await saveCard(
        dataToSave as any
      );

    if (!response.success) {
      throw new Error(
        response.message ||
          "Failed to save card"
      );
    }

    console.log(
      `CARD ${currentIndex + 1} SAVED SUCCESSFULLY`
    );

    return true;
  };

  // ============================================================
  // SAVE & NEXT
  // ============================================================

  const handleNext = async () => {
    if (
      currentIndex >=
      cards.length - 1
    ) {
      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      // ========================================================
      // IMPORTANT:
      //
      // First create the updated current card using formData.
      //
      // Do NOT wait for setCards().
      // React state updates are asynchronous.
      // ========================================================

      const updatedCurrentCard: ExtractedCard =
        normalizeCard(
          formData
        );

      // ========================================================
      // UPDATE LOCAL CARD ARRAY
      // ========================================================

      const updatedCards = [
        ...cards,
      ];

      updatedCards[
        currentIndex
      ] = updatedCurrentCard;

      setCards(
        updatedCards
      );

      // ========================================================
      // SAVE CURRENT CARD FIRST
      // ========================================================

      const saved =
        await saveCurrentCardToDatabase(
          updatedCurrentCard
        );

      // ========================================================
      // DUPLICATE FOUND
      //
      // Do NOT move to next card.
      // Popup will handle it.
      // ========================================================

      if (!saved) {
        setIsLoading(false);
        return;
      }

      // ========================================================
      // MOVE TO NEXT CARD
      // ========================================================

      const nextIndex =
        currentIndex + 1;

      setCurrentIndex(
        nextIndex
      );

      setFormData(
        normalizeCard(
          updatedCards[nextIndex]
        )
      );

      setError(null);

      window.scrollTo({
        top: 0,
        behavior: "smooth",
      });
    } catch (err: any) {
      console.error(
        "SAVE & NEXT ERROR:",
        err
      );

      setError(
        err?.message ||
          "Failed to save this card"
      );
    } finally {
      setIsLoading(false);
    }
  };

  // ============================================================
  // PREVIOUS CARD
  // ============================================================

  const handlePrevious = () => {
    if (
      currentIndex <= 0 ||
      isLoading
    ) {
      return;
    }

    // ----------------------------------------------------------
    // Save current edits locally
    // ----------------------------------------------------------

    const updatedCurrentCard =
      normalizeCard(formData);

    const updatedCards = [
      ...cards,
    ];

    updatedCards[
      currentIndex
    ] = updatedCurrentCard;

    setCards(
      updatedCards
    );

    // ----------------------------------------------------------
    // Move previous
    // ----------------------------------------------------------

    const previousIndex =
      currentIndex - 1;

    setCurrentIndex(
      previousIndex
    );

    setFormData(
      normalizeCard(
        updatedCards[
          previousIndex
        ]
      )
    );

    setError(null);

    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  // ============================================================
  // SAVE LAST CARD
  // ============================================================

  const handleSave = async () => {
    setIsLoading(true);
    setError(null);

    try {
      // ========================================================
      // SAVE CURRENT EDITED CARD LOCALLY
      // ========================================================

      const updatedCurrentCard =
        normalizeCard(formData);

      const updatedCards = [
        ...cards,
      ];

      updatedCards[
        currentIndex
      ] = updatedCurrentCard;

      setCards(
        updatedCards
      );

      // ========================================================
      // SAVE CURRENT CARD
      // ========================================================

      const saved =
        await saveCurrentCardToDatabase(
          updatedCurrentCard
        );

      // ========================================================
      // DUPLICATE FOUND
      // ========================================================

      if (!saved) {
        setIsLoading(false);
        return;
      }

      // ========================================================
      // CHECK IF THIS WAS REALLY THE LAST CARD
      // ========================================================

      if (
        currentIndex <
        updatedCards.length - 1
      ) {
        // ------------------------------------------------------
        // There are still cards remaining.
        // ------------------------------------------------------

        const nextIndex =
          currentIndex + 1;

        setCurrentIndex(
          nextIndex
        );

        setFormData(
          normalizeCard(
            updatedCards[
              nextIndex
            ]
          )
        );

        setError(null);

        window.scrollTo({
          top: 0,
          behavior: "smooth",
        });

        return;
      }

      // ========================================================
      // ALL CARDS SAVED
      // ========================================================

      console.log(
        "========================================"
      );

      console.log(
        "ALL CARDS SAVED SUCCESSFULLY"
      );

      console.log(
        "TOTAL:",
        updatedCards.length
      );

      console.log(
        "========================================"
      );

      // --------------------------------------------------------
      // Clear session storage
      // --------------------------------------------------------

      sessionStorage.removeItem(
        "extractedCard"
      );

      sessionStorage.removeItem(
        "extractedCards"
      );

      // --------------------------------------------------------
      // Go to cards page
      // --------------------------------------------------------

      router.push(
        "/cards"
      );
    } catch (err: any) {
      console.error(
        "SAVE CARD ERROR:",
        err
      );

      setError(
        err?.message ||
          "Something went wrong while saving the card"
      );
    } finally {
      setIsLoading(false);
    }
  };

  // ============================================================
  // CONFIRM DUPLICATE SAVE
  // ============================================================

  const handleDuplicateSaveAnyway =
    async () => {
      if (!pendingSaveData) {
        return;
      }

      setIsLoading(true);
      setError(null);

      try {
        // ======================================================
        // SAVE DUPLICATE CARD
        // ======================================================

        const response =
          await saveCard(
            pendingSaveData
          );

        if (!response.success) {
          throw new Error(
            response.message ||
              "Failed to save card"
          );
        }

        console.log(
          "DUPLICATE CARD SAVED SUCCESSFULLY"
        );

        // ======================================================
        // CLOSE POPUP
        // ======================================================

        setShowDuplicateConfirm(
          false
        );

        setPendingSaveData(
          null
        );

        // ======================================================
        // CHECK NEXT CARD
        // ======================================================

        if (
          currentIndex <
          cards.length - 1
        ) {
          const nextIndex =
            currentIndex + 1;

          setCurrentIndex(
            nextIndex
          );

          setFormData(
            normalizeCard(
              cards[nextIndex]
            )
          );

          setError(null);

          window.scrollTo({
            top: 0,
            behavior: "smooth",
          });

          return;
        }

        // ======================================================
        // ALL CARDS SAVED
        // ======================================================

        sessionStorage.removeItem(
          "extractedCard"
        );

        sessionStorage.removeItem(
          "extractedCards"
        );

        router.push(
          "/cards"
        );
      } catch (err: any) {
        console.error(
          "DUPLICATE SAVE ERROR:",
          err
        );

        setError(
          err?.message ||
            "Failed to save duplicate card"
        );
      } finally {
        setIsLoading(false);
      }
    };

  // ============================================================
  // CANCEL DUPLICATE
  // ============================================================

  const handleDuplicateCancel =
    () => {
      if (isLoading) {
        return;
      }

      setShowDuplicateConfirm(
        false
      );

      setPendingSaveData(
        null
      );
    };

  // ============================================================
  // GOOGLE MAPS
  // ============================================================

  const openMap = () => {
    if (!formData.address) {
      return;
    }

    const encodedAddress =
      encodeURIComponent(
        formData.address
      );

    window.open(
      `https://www.google.com/maps/search/?api=1&query=${encodedAddress}`,
      "_blank"
    );
  };

  // ============================================================
  // QR DATA
  // ============================================================

  const qrCodes =
    Array.isArray(
      formData.qr_codes
    ) &&
    formData.qr_codes.length > 0
      ? formData.qr_codes
      : formData.qr_raw
        ? String(
            formData.qr_raw
          )
            .split(" ||| ")
            .filter(Boolean)
        : [];

  const qrCount =
    qrCodes.length;

  // ============================================================
  // LOADING
  // ============================================================

  if (!isReady) {
    return (
      <div className="py-20">
        <LoadingSpinner
          size="lg"
          text="Loading extracted card data..."
        />
      </div>
    );
  }

  // ============================================================
  // PAGE
  // ============================================================

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 sm:p-8">

        {/* =====================================================
            TITLE
        ===================================================== */}

        <div className="mb-8">
          <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4">

            <div>
              <h2 className="text-2xl font-semibold text-gray-900">
                Review Extracted Details
              </h2>

              <p className="mt-1 text-sm text-gray-500">
                Review the scanned card information before saving.
              </p>
            </div>

            {/* CARD COUNTER */}

            {cards.length > 1 && (
              <div className="flex items-center gap-2 bg-primary-50 border border-primary-200 rounded-lg px-4 py-2">

                <span className="text-sm font-medium text-primary-700">
                  PDF / Card
                </span>

                <span className="text-sm font-bold text-primary-900">
                  {currentIndex + 1}
                </span>

                <span className="text-sm text-primary-600">
                  of
                </span>

                <span className="text-sm font-bold text-primary-900">
                  {cards.length}
                </span>

              </div>
            )}

          </div>
        </div>

        {/* =====================================================
            MULTIPLE CARD NAVIGATION
        ===================================================== */}

        {cards.length > 1 && (
          <div className="mb-8 rounded-xl border border-gray-200 bg-gray-50 p-4">

            <div className="flex items-center justify-between gap-3">

              <Button
                variant="outline"
                onClick={
                  handlePrevious
                }
                disabled={
                  currentIndex === 0 ||
                  isLoading
                }
              >
                <ArrowLeft className="h-4 w-4 mr-2" />
                Previous
              </Button>

              <div className="text-center">

                <p className="text-sm font-semibold text-gray-800">
                  Card{" "}
                  {currentIndex + 1}
                </p>

                <p className="text-xs text-gray-500 mt-1">
                  {currentIndex ===
                  cards.length - 1
                    ? "Last card"
                    : "Review and save this card"}
                </p>

              </div>

              <Button
                variant="outline"
                onClick={
                  handleNext
                }
                disabled={
                  currentIndex >=
                    cards.length - 1 ||
                  isLoading
                }
              >
                Next
                <ArrowRight className="h-4 w-4 ml-2" />
              </Button>

            </div>

          </div>
        )}

        {/* =====================================================
            SCANNED CARD IMAGES
        ===================================================== */}

        <div className="mb-8">

          <div className="flex items-center gap-2 mb-4">

            <ImageIcon className="h-5 w-5 text-primary-600" />

            <h3 className="text-lg font-semibold text-gray-900">
              Scanned Business Card
            </h3>

          </div>

          <div className="grid grid-cols-1 md:grid-cols-2 gap-6">

            {/* FRONT */}

            <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">

              <div className="flex items-center justify-between mb-3">

                <div>

                  <p className="font-medium text-gray-800">
                    Front Side
                  </p>

                  <p className="text-xs text-gray-500">
                    Scanned card front
                  </p>

                </div>

                {formData.front_image_url && (
                  <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full">
                    Scanned
                  </span>
                )}

              </div>

              {formData.front_image_url ? (
                <div className="rounded-lg overflow-hidden border border-gray-200 bg-white">

                  <img
                    src={
                      formData.front_image_url
                    }
                    alt="Business card front side"
                    className="w-full h-64 object-contain"
                  />

                </div>
              ) : (
                <div className="h-64 rounded-lg border border-dashed border-gray-300 bg-white flex flex-col items-center justify-center">

                  <ImageIcon className="h-10 w-10 text-gray-400 mb-2" />

                  <p className="text-sm text-gray-500">
                    Front side not available
                  </p>

                </div>
              )}

            </div>

            {/* BACK */}

            <div className="rounded-xl border border-gray-200 bg-gray-50 p-4">

              <div className="flex items-center justify-between mb-3">

                <div>

                  <p className="font-medium text-gray-800">
                    Back Side
                  </p>

                  <p className="text-xs text-gray-500">
                    Scanned card back
                  </p>

                </div>

                {formData.back_image_url && (
                  <span className="text-xs bg-green-100 text-green-700 px-2 py-1 rounded-full">
                    Scanned
                  </span>
                )}

              </div>

              {formData.back_image_url ? (
                <div className="rounded-lg overflow-hidden border border-gray-200 bg-white">

                  <img
                    src={
                      formData.back_image_url
                    }
                    alt="Business card back side"
                    className="w-full h-64 object-contain"
                  />

                </div>
              ) : (
                <div className="h-64 rounded-lg border border-dashed border-gray-300 bg-white flex flex-col items-center justify-center">

                  <ImageIcon className="h-10 w-10 text-gray-400 mb-2" />

                  <p className="text-sm text-gray-500">
                    Back side not available
                  </p>

                </div>
              )}

            </div>

          </div>
        </div>

        {/* =====================================================
            LOGO + QR SUMMARY
        ===================================================== */}

        <div className="flex flex-wrap gap-6 mb-8">

          {/* LOGO */}

          <div className="flex items-center gap-4">

            {formData.company_logo ? (
              <img
                src={
                  formData.company_logo
                }
                alt="Company Logo"
                className="h-20 w-20 rounded-xl object-contain border border-gray-200 bg-white"
              />
            ) : (
              <div className="h-20 w-20 rounded-xl bg-gray-100 flex items-center justify-center">
                <Building2 className="h-8 w-8 text-gray-400" />
              </div>
            )}

            <div>

              <p className="text-sm font-medium text-gray-700">
                Company Logo
              </p>

              <p className="text-xs text-gray-500">
                {formData.company_logo
                  ? "Detected"
                  : "Not found"}
              </p>

            </div>

          </div>

          {/* QR */}

          <div className="flex items-center gap-4">

            <div
              className={`h-20 w-20 rounded-xl flex items-center justify-center ${
                qrCount > 0
                  ? "bg-green-50 border border-green-200"
                  : "bg-gray-100"
              }`}
            >

              <QrCode
                className={`h-8 w-8 ${
                  qrCount > 0
                    ? "text-green-600"
                    : "text-gray-400"
                }`}
              />

            </div>

            <div>

              <p className="text-sm font-medium text-gray-700">
                QR Code
                {qrCount > 1
                  ? "s"
                  : ""}
              </p>

              <p className="text-xs text-gray-500">
                {qrCount > 0
                  ? `${qrCount} detected`
                  : "Not found"}
              </p>

            </div>

          </div>

        </div>

        {/* =====================================================
            EXTRACTED INFORMATION
        ===================================================== */}

        <div className="mb-4">

          <h3 className="text-lg font-semibold text-gray-900">
            Extracted Information
          </h3>

          <p className="text-sm text-gray-500 mt-1">
            Information detected from this business card.
          </p>

        </div>

        <div className="grid grid-cols-1 md:grid-cols-2 gap-4">

          <Input
            id="owner_name"
            name="owner_name"
            label="Owner / Person Name"
            value={
              formData.owner_name || ""
            }
            onChange={
              handleChange
            }
            placeholder="Rahul Patel"
          />

          <Input
            id="company_name"
            name="company_name"
            label="Company Name"
            value={
              formData.company_name || ""
            }
            onChange={
              handleChange
            }
            placeholder="ABC Technologies"
          />

          <Input
            id="designation"
            name="designation"
            label="Designation"
            value={
              formData.designation || ""
            }
            onChange={
              handleChange
            }
            placeholder="Founder & CEO"
          />

          <Input
            id="phone"
            name="phone"
            label="Phone Number"
            value={
              formData.phone || ""
            }
            onChange={
              handleChange
            }
            placeholder="+91 9876543210"
          />

          <Input
            id="email"
            name="email"
            type="email"
            label="Email"
            value={
              formData.email || ""
            }
            onChange={
              handleChange
            }
            placeholder="contact@company.com"
          />

          <Input
            id="website_url"
            name="website_url"
            label="Website"
            value={
              formData.website_url || ""
            }
            onChange={
              handleChange
            }
            placeholder="https://company.com"
          />

          <Input
            id="instagram_url"
            name="instagram_url"
            label="Instagram"
            value={
              formData.instagram_url || ""
            }
            onChange={
              handleChange
            }
            placeholder="@username or full link"
          />

          <Input
            id="facebook_url"
            name="facebook_url"
            label="Facebook"
            value={
              formData.facebook_url || ""
            }
            onChange={
              handleChange
            }
            placeholder="Facebook profile / page link"
          />

          <Input
            id="linkedin_url"
            name="linkedin_url"
            label="LinkedIn"
            value={
              formData.linkedin_url || ""
            }
            onChange={
              handleChange
            }
            placeholder="LinkedIn profile link"
          />

          <Input
            id="gst_number"
            name="gst_number"
            label="GST Number"
            value={
              formData.gst_number || ""
            }
            onChange={
              handleChange
            }
            placeholder="24ABCDE1234F1Z5"
          />

        </div>

        {/* =====================================================
            ADDRESS
        ===================================================== */}

        <div className="mt-6">

          <div className="flex items-center justify-between mb-2">

            <label
              htmlFor="address"
              className="flex items-center gap-2 text-sm font-medium text-gray-700"
            >

              <MapPin className="h-4 w-4 text-primary-600" />

              Address / Location

            </label>

            {formData.address && (
              <button
                type="button"
                onClick={
                  openMap
                }
                className="flex items-center gap-1 text-sm text-primary-600 hover:text-primary-700"
              >

                <ExternalLink className="h-4 w-4" />

                View on Map

              </button>
            )}

          </div>

          <textarea
            id="address"
            name="address"
            rows={3}
            value={
              formData.address || ""
            }
            onChange={
              handleChange
            }
            placeholder="Company address / City / State / Country"
            className="w-full rounded-lg border border-gray-300 px-3 py-3 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          />

          {formData.address && (
            <div className="mt-2 flex items-start gap-2 text-sm text-gray-500">

              <MapPin className="h-4 w-4 mt-0.5 flex-shrink-0" />

              <span>
                {
                  formData.address
                }
              </span>

            </div>
          )}

        </div>

        {/* =====================================================
            OTHER DETAILS
        ===================================================== */}

        <div className="mt-6">

          <label
            htmlFor="other_details"
            className="block text-sm font-medium text-gray-700 mb-1"
          >
            Other Details
          </label>

          <textarea
            id="other_details"
            name="other_details"
            rows={3}
            value={
              formData.other_details || ""
            }
            onChange={
              handleChange
            }
            placeholder="Any other information found on the card..."
            className="w-full rounded-lg border border-gray-300 px-3 py-2 text-sm shadow-sm focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500"
          />

        </div>

        {/* =====================================================
            ALL QR DATA
        ===================================================== */}

        {qrCount > 0 && (
          <div className="mt-6 space-y-3">

            <div className="flex items-center gap-2">

              <QrCode className="h-5 w-5 text-green-600" />

              <p className="font-medium text-green-800">
                QR Code
                {qrCount > 1
                  ? "s"
                  : ""}{" "}
                Detected
              </p>

            </div>

            {qrCodes.map(
              (
                qr,
                index
              ) => (
                <div
                  key={`${qr}-${index}`}
                  className="rounded-lg border border-green-200 bg-green-50 p-4"
                >

                  <p className="text-xs text-green-600 mb-1">
                    QR {index + 1}
                  </p>

                  <p className="text-sm text-green-700 break-all">
                    {qr}
                  </p>

                </div>
              )
            )}

          </div>
        )}

        {/* =====================================================
            ERROR
        ===================================================== */}

        {error && (
          <div className="mt-6 bg-red-50 border border-red-200 text-red-700 text-sm p-4 rounded-lg">
            {error}
          </div>
        )}

        {/* =====================================================
            ACTION BUTTONS
        ===================================================== */}

        <div className="mt-8 flex flex-col sm:flex-row gap-3">

          <Button
            variant="outline"
            onClick={() =>
              router.push("/")
            }
            className="flex-1"
            disabled={
              isLoading
            }
          >

            <ArrowLeft className="h-4 w-4 mr-2" />

            Cancel

          </Button>

          {/* =================================================
              MULTIPLE CARDS
          ================================================= */}

          {cards.length > 1 &&
          currentIndex <
            cards.length - 1 ? (

            <Button
              onClick={
                handleNext
              }
              className="flex-1"
              isLoading={
                isLoading
              }
              disabled={
                isLoading
              }
            >

              Save & Next

              <ArrowRight className="h-4 w-4 ml-2" />

            </Button>

          ) : (

            <Button
              onClick={
                handleSave
              }
              className="flex-1"
              isLoading={
                isLoading
              }
              disabled={
                isLoading
              }
            >

              <Save className="h-4 w-4 mr-2" />

              {cards.length > 1
                ? "Confirm & Save Last Card"
                : "Confirm & Save"}

            </Button>

          )}

        </div>

        {/* =====================================================
            DUPLICATE COMPANY CONFIRMATION
        ===================================================== */}

        {showDuplicateConfirm && (
          <div className="fixed inset-0 z-[100] flex items-center justify-center p-4">

            <div
              className="absolute inset-0 bg-black/50 backdrop-blur-sm"
              onClick={
                handleDuplicateCancel
              }
            />

            <div className="relative bg-white rounded-2xl shadow-xl w-full max-w-md p-6">

              <div className="flex flex-col items-center text-center">

                <div className="w-14 h-14 rounded-full bg-amber-100 flex items-center justify-center mb-4">

                  <Building2 className="h-7 w-7 text-amber-600" />

                </div>

                <h3 className="text-lg font-semibold text-gray-900 mb-2">
                  Company Already Exists
                </h3>

                <p className="text-sm text-gray-600 mb-6">

                  A card with company name{" "}

                  <span className="font-semibold text-gray-900">

                    “
                    {
                      pendingSaveData?.company_name
                    }
                    ”

                  </span>{" "}

                  is already saved.

                  <br />

                  Do you still want to save this card?

                </p>

                <div className="flex gap-3 w-full">

                  <Button
                    variant="outline"
                    className="flex-1"
                    onClick={
                      handleDuplicateCancel
                    }
                    disabled={
                      isLoading
                    }
                  >
                    No, Cancel
                  </Button>

                  <Button
                    className="flex-1"
                    onClick={
                      handleDuplicateSaveAnyway
                    }
                    isLoading={
                      isLoading
                    }
                    disabled={
                      isLoading
                    }
                  >
                    Yes, Save Anyway
                  </Button>

                </div>

              </div>

            </div>

          </div>
        )}

      </div>
    </div>
  );
}