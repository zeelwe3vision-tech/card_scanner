"use client";

import React, {
  useRef,
  useState,
  useEffect,
} from "react";
import jsQR from "jsqr";
import { useRouter } from "next/navigation";

import {
  Camera,
  Upload,
  X,
  SwitchCamera,
  RotateCcw,
  Check,
} from "lucide-react";

import Button from "@/components/ui/Button";
import LoadingSpinner from "@/components/ui/LoadingSpinner";

import { uploadScan } from "@/services/api";


/* =========================================================
   TYPES
========================================================= */

type CaptureStep = "front" | "back" | "review";


interface ExtractedCard {
  owner_name: string | null;
  job_title: string | null;
  company_name: string | null;
  address: string | null;
  email: string | null;
  phone: string | null;
  gst_number: string | null;

  company_logo: string | null;

  website_url: string | null;
  instagram_url: string | null;
  facebook_url: string | null;
  linkedin_url: string | null;

  source_type?: string;
  original_file_url?: string | null;

  /*
   * Frontend preview URLs.
   *
   * These are stored temporarily so the Review page
   * can display the actual scanned images.
   */
  front_image_url?: string | null;
  back_image_url?: string | null;
}


/* =========================================================
   COMPONENT
========================================================= */

export default function ScanUploader() {
  const router = useRouter();
  const [autoCaptureEnabled, setAutoCaptureEnabled] = useState(true);
  const [stableQrFrames, setStableQrFrames] = useState(0);
  const [isAutoCapturing, setIsAutoCapturing] = useState(false);
  const lastQrRef = useRef<string | null>(null);
  const stableQrFramesRef = useRef(0);
  const animationRef = useRef<number | null>(null);
  /*
   * Camera references
   */
  const videoRef = useRef<HTMLVideoElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const streamRef = useRef<MediaStream | null>(null);

  /*
   * Capture state
   */
  const [step, setStep] =
    useState<CaptureStep>("front");

  /*
   * Image previews
   */
  const [frontPreview, setFrontPreview] =
    useState<string | null>(null);

  const [backPreview, setBackPreview] =
    useState<string | null>(null);

  /*
   * Actual files sent to backend
   */
  const [frontFile, setFrontFile] =
    useState<File | null>(null);

  const [backFile, setBackFile] =
    useState<File | null>(null);

  /*
   * Camera state
   */
  const [isCameraActive, setIsCameraActive] =
    useState(false);

  const [isStarting, setIsStarting] =
    useState(false);

  const [facingMode, setFacingMode] =
    useState<"environment" | "user">(
      "environment"
    );

  /*
   * Upload state
   */
  const [isLoading, setIsLoading] =
    useState(false);

  const [error, setError] =
    useState<string | null>(null);


  /* =========================================================
     CONVERT BLOB TO DATA URL
  ========================================================= */

  const blobToDataUrl = (
    blob: Blob
  ): Promise<string> => {
    return new Promise((resolve, reject) => {
      const reader = new FileReader();

      reader.onloadend = () => {
        if (typeof reader.result === "string") {
          resolve(reader.result);
        } else {
          reject(
            new Error(
              "Could not convert image"
            )
          );
        }
      };

      reader.onerror = () => {
        reject(
          new Error(
            "Failed to read image"
          )
        );
      };

      reader.readAsDataURL(blob);
    });
  };


  /* =========================================================
     START CAMERA
  ========================================================= */

  const startCamera = async (
    mode: "environment" | "user" = "environment"
  ) => {
    setIsStarting(true);
    setError(null);

    try {
      /*
       * Stop previous camera stream
       */
      if (streamRef.current) {
        streamRef.current
          .getTracks()
          .forEach((track) => track.stop());

        streamRef.current = null;
      }

      /*
       * Request camera
       */
      const mediaStream =
        await navigator.mediaDevices.getUserMedia({
          video: {
            facingMode: mode,
            width: {
              ideal: 1280,
            },
            height: {
              ideal: 720,
            },
          },
          audio: false,
        });

      streamRef.current = mediaStream;

      setFacingMode(mode);
      setIsCameraActive(true);

      /*
       * Attach camera stream to video
       */
      setTimeout(() => {
        const video = videoRef.current;

        if (!video) {
          setIsStarting(false);
          return;
        }

        video.srcObject = mediaStream;

        video.onloadedmetadata = () => {
          video
            .play()
            .then(() => {
              setIsStarting(false);
              startQRScanning();
            })
            .catch(() => {
              setError(
                "Could not start camera preview"
              );

              setIsStarting(false);
            });
        };
      }, 200);

    } catch (err: any) {
      console.error(
        "Camera error:",
        err
      );

      setError(
        err?.message ||
        "Camera access denied. Please allow camera permission."
      );

      setIsStarting(false);
      setIsCameraActive(false);
    }
  };


  /* =========================================================
     STOP CAMERA
  ========================================================= */

  const stopCamera = () => {
    if (animationRef.current) {
      cancelAnimationFrame(animationRef.current);
      animationRef.current = null;
    }
  
    if (streamRef.current) {
      streamRef.current.getTracks().forEach((track) => track.stop());
      streamRef.current = null;
    }
  
    if (videoRef.current) {
      videoRef.current.srcObject = null;
    }
  
    setIsCameraActive(false);
    setIsStarting(false);
    setStableQrFrames(0);
    stableQrFramesRef.current = 0;
    lastQrRef.current = null;
  };
/* =========================================================
   QR SCANNING + AUTO CAPTURE
========================================================= */
const startQRScanning = () => {
  if (animationRef.current) {
    cancelAnimationFrame(animationRef.current);
  }

  let lastImageData: ImageData | null = null;
  let stableCount = 0;
  let qrStableCount = 0;

  const scan = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;

    if (!video || !canvas || !streamRef.current) return;
    if (video.readyState !== video.HAVE_ENOUGH_DATA) {
      animationRef.current = requestAnimationFrame(scan);
      return;
    }

    const ctx = canvas.getContext("2d", { willReadFrequently: true });
    if (!ctx) {
      animationRef.current = requestAnimationFrame(scan);
      return;
    }

    const w = 160;
    const h = 120;
    canvas.width = w;
    canvas.height = h;
    ctx.drawImage(video, 0, 0, w, h);

    const imageData = ctx.getImageData(0, 0, w, h);
    const data = imageData.data;

    // ========== 1. Check if something is in the CENTER (card area) ==========
    // We only look at the middle part of the frame
    let variance = 0;
    let pixelCount = 0;
    let sum = 0;

    // Center area (where the guide frame is)
    for (let y = 30; y < 90; y++) {
      for (let x = 40; x < 120; x++) {
        const i = (y * w + x) * 4;
        const gray = (data[i] + data[i + 1] + data[i + 2]) / 3;
        sum += gray;
        pixelCount++;
      }
    }

    const avg = sum / pixelCount;

    for (let y = 30; y < 90; y++) {
      for (let x = 40; x < 120; x++) {
        const i = (y * w + x) * 4;
        const gray = (data[i] + data[i + 1] + data[i + 2]) / 3;
        variance += Math.abs(gray - avg);
      }
    }

    // If variance is too low → empty background (no card)
    const hasContent = variance > 2500;   // adjust if needed

    // ========== 2. QR Detection ==========
    const code = jsQR(data, w, h, { inversionAttempts: "dontInvert" });

    let hasQR = false;
    if (code?.data) {
      hasQR = true;
      if (lastQrRef.current === code.data) {
        qrStableCount++;
      } else {
        lastQrRef.current = code.data;
        qrStableCount = 1;
      }
    } else {
      qrStableCount = 0;
      lastQrRef.current = null;
    }

    // ========== 3. Stability (only if content exists) ==========
    if (hasContent && lastImageData) {
      let diff = 0;
      for (let i = 0; i < data.length; i += 24) {
        diff += Math.abs(data[i] - lastImageData.data[i]);
      }

      if (diff < 16000) {
        stableCount++;
      } else {
        stableCount = Math.max(0, stableCount - 2);
      }
    } else {
      // No card in frame → reset
      stableCount = 0;
    }

    lastImageData = imageData;
    setStableQrFrames(hasQR ? qrStableCount : stableCount);

    // ========== 4. Auto Capture ==========
    const shouldCapture =
      autoCaptureEnabled &&
      !isAutoCapturing &&
      hasContent &&                                 // must have something in center
      (
        (hasQR && qrStableCount > 18) ||
        (!hasQR && stableCount > 50)
      );

    if (shouldCapture) {
      setIsAutoCapturing(true);
      stableCount = 0;
      qrStableCount = 0;

      setTimeout(() => {
        capturePhoto();
        setIsAutoCapturing(false);
      }, 280);

      return;
    }

    animationRef.current = requestAnimationFrame(scan);
  };

  animationRef.current = requestAnimationFrame(scan);
};

  /* =========================================================
     CAPTURE PHOTO
  ========================================================= */

  const capturePhoto = () => {
    const video = videoRef.current;
    const canvas = canvasRef.current;

    if (!video || !canvas) {
      setError(
        "Camera is not ready."
      );

      return;
    }

    /*
     * Make sure video has actual dimensions
     */
    if (
      video.videoWidth === 0 ||
      video.videoHeight === 0
    ) {
      setError(
        "Camera is still loading. Please try again."
      );

      return;
    }

    /*
     * Use the actual camera resolution
     */
    canvas.width = video.videoWidth;
    canvas.height = video.videoHeight;

    const ctx =
      canvas.getContext("2d");

    if (!ctx) {
      setError(
        "Could not capture image."
      );

      return;
    }

    /*
     * Draw current camera frame
     */
    ctx.drawImage(
      video,
      0,
      0,
      canvas.width,
      canvas.height
    );

    /*
     * Convert image to JPEG
     */
    canvas.toBlob(
      async (blob) => {
        if (!blob) {
          setError(
            "Could not create image."
          );

          return;
        }

        try {
          /*
           * Create File for backend
           */
          const file = new File(
            [blob],
            `business-card-${step}.jpg`,
            {
              type: "image/jpeg",
            }
          );

          /*
           * IMPORTANT:
           *
           * Use a DATA URL instead of blob URL.
           *
           * This allows us to store the image
           * in sessionStorage and display it
           * on the /review page.
           */
          const dataUrl =
            await blobToDataUrl(blob);

          /*
           * FRONT SIDE
           */
          if (step === "front") {
            setFrontFile(file);
            setFrontPreview(dataUrl);

            stopCamera();

            /*
             * Move automatically to back side
             */
            setStep("back");

            return;
          }

          /*
           * BACK SIDE
           */
          if (step === "back") {
            setBackFile(file);
            setBackPreview(dataUrl);

            stopCamera();

            /*
             * Both sides are ready
             */
            setStep("review");

            return;
          }

        } catch (err) {
          console.error(
            "Capture error:",
            err
          );

          setError(
            "Failed to process captured image."
          );
        }
      },
      "image/jpeg",
      0.88
    );
  };


  /* =========================================================
     SWITCH CAMERA
  ========================================================= */

  const switchCamera = () => {
    const newMode =
      facingMode === "environment"
        ? "user"
        : "environment";

    startCamera(newMode);
  };


  /* =========================================================
     RETAKE FRONT
  ========================================================= */

  const retakeFront = () => {
    setFrontFile(null);
    setFrontPreview(null);

    setBackFile(null);
    setBackPreview(null);

    setError(null);

    setStep("front");

    startCamera(facingMode);
  };


  /* =========================================================
     RETAKE BACK
  ========================================================= */

  const retakeBack = () => {
    setBackFile(null);
    setBackPreview(null);

    setError(null);

    setStep("back");

    startCamera(facingMode);
  };


  /* =========================================================
     PROCESS / UPLOAD CARD
  ========================================================= */

  const handleUpload = async () => {
    /*
     * Front is required
     */
    if (!frontFile) {
      setError(
        "Please capture the front side of the card."
      );

      return;
    }

    /*
     * Back is required for the
     * two-sided scanning flow
     */
    if (!backFile) {
      setError(
        "Please capture the back side of the card."
      );

      return;
    }

    setIsLoading(true);
    setError(null);

    try {
      console.log(
        "Uploading business card..."
      );

      /*
       * Send BOTH images to backend
       *
       * The backend should call:
       *
       * Front image → VLM
       * Back image  → VLM
       *
       * and merge the results.
       */
      const response =
        await uploadScan(
          frontFile,
          backFile
        );

      console.log(
        "Scan response:",
        response
      );

      /*
       * Backend returned success
       */
      if (
        response.success &&
        response.card
      ) {

        /*
         * Merge backend VLM result
         * with frontend image previews.
         *
         * Backend may eventually return:
         *
         * front_image_url
         * back_image_url
         *
         * from Supabase Storage.
         *
         * Until then, the local data URLs
         * are used for the review screen.
         */
        const card: ExtractedCard = {
          ...response.card,

          /*
           * Prefer backend image URL if available.
           * Otherwise use the captured image.
           */
          front_image_url:
            response.card.front_image_url ||
            frontPreview,

          back_image_url:
            response.card.back_image_url ||
            backPreview,
        };


        /*
         * Save complete card information.
         *
         * The Review page reads this.
         */
        sessionStorage.setItem(
          "extractedCard",
          JSON.stringify(card)
        );


        /*
         * Also save separately.
         *
         * This makes it easier for the
         * Review page to access the images.
         */
        if (frontPreview) {
          sessionStorage.setItem(
            "frontCardImage",
            frontPreview
          );
        }

        if (backPreview) {
          sessionStorage.setItem(
            "backCardImage",
            backPreview
          );
        }


        /*
         * Go to Review page
         */
        router.push("/review");

      } else {
        setError(
          response.message ||
          "Failed to extract card details."
        );
      }

    } catch (err: any) {
      console.error(
        "Card processing error:",
        err
      );

      setError(
        err?.message ||
        "Something went wrong while scanning the card."
      );

    } finally {
      setIsLoading(false);
    }
  };


  /* =========================================================
     CLEANUP CAMERA
  ========================================================= */

  useEffect(() => {
    return () => {
      stopCamera();
    };
  }, []);


  /* =========================================================
     UI
  ========================================================= */

  return (
    <div className="space-y-6">

      {/* Hidden canvas used for capturing camera frames */}
      <canvas
        ref={canvasRef}
        className="hidden"
      />


      {/* =====================================================
          STEP INDICATOR
      ===================================================== */}

      {!isCameraActive && (
        <div className="flex items-center justify-center gap-3 mb-2">

          {/* FRONT */}
          <div
            className={`
              flex items-center gap-2
              px-3 py-1.5
              rounded-full
              text-sm font-medium
              ${
                step === "front"
                  ? "bg-primary-100 text-primary-700"
                  : frontPreview
                  ? "bg-green-100 text-green-700"
                  : "bg-gray-100 text-gray-500"
              }
            `}
          >
            {frontPreview ? (
              <Check className="h-4 w-4" />
            ) : (
              <span className="w-4 h-4 rounded-full bg-current opacity-30" />
            )}

            Front
          </div>


          <div className="w-8 h-0.5 bg-gray-200" />


          {/* BACK */}
          <div
            className={`
              flex items-center gap-2
              px-3 py-1.5
              rounded-full
              text-sm font-medium
              ${
                step === "back"
                  ? "bg-primary-100 text-primary-700"
                  : step === "review" &&
                    backPreview
                  ? "bg-green-100 text-green-700"
                  : "bg-gray-100 text-gray-500"
              }
            `}
          >
            {backPreview ? (
              <Check className="h-4 w-4" />
            ) : (
              <span className="w-4 h-4 rounded-full bg-current opacity-30" />
            )}

            Back
          </div>

        </div>
      )}


      {/* =====================================================
          ERROR
      ===================================================== */}

      {error && !isCameraActive && (
        <div className="bg-red-50 border border-red-200 text-red-700 text-sm p-4 rounded-xl">
          {error}
        </div>
      )}


      {/* =====================================================
          FRONT START
      ===================================================== */}

      {!isCameraActive &&
        step === "front" &&
        !frontPreview && (

          <div className="border-2 border-dashed border-gray-300 rounded-2xl p-10 text-center bg-gradient-to-b from-gray-50 to-white">

            <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-4">

              <Camera className="h-8 w-8 text-primary-600" />

            </div>


            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              Scan Business Card
            </h3>


            <p className="text-gray-500 mb-6 max-w-sm mx-auto">
              Take two photos — first the front side,
              then the back side.
            </p>


            <Button
              onClick={() =>
                startCamera("environment")
              }
              size="lg"
            >
              <Camera className="h-5 w-5 mr-2" />

              Start with Front Side
            </Button>

          </div>
        )}


      {/* =====================================================
          BACK INSTRUCTION
      ===================================================== */}

      {!isCameraActive &&
        step === "back" &&
        !backPreview && (

          <div className="border-2 border-dashed border-gray-300 rounded-2xl p-10 text-center bg-gradient-to-b from-gray-50 to-white">

            <div className="w-16 h-16 bg-primary-100 rounded-full flex items-center justify-center mx-auto mb-4">

              <Camera className="h-8 w-8 text-primary-600" />

            </div>


            <h3 className="text-xl font-semibold text-gray-900 mb-2">
              Now capture Back Side
            </h3>


            <p className="text-gray-500 mb-6">
              Flip the card and take a photo of the back side.
            </p>


            <div className="flex gap-3 justify-center">

              <Button
                variant="outline"
                onClick={retakeFront}
              >
                <RotateCcw className="h-4 w-4 mr-2" />

                Retake Front
              </Button>


              <Button
                onClick={() =>
                  startCamera(facingMode)
                }
              >
                <Camera className="h-4 w-4 mr-2" />

                Capture Back Side
              </Button>

            </div>

          </div>
        )}


      {/* =====================================================
          LIVE CAMERA
      ===================================================== */}

      {isCameraActive && (

        <div className="relative rounded-2xl overflow-hidden bg-black shadow-xl">

          <video
            ref={videoRef}
            autoPlay
            playsInline
            muted
            className="w-full aspect-[4/3] object-cover max-h-[480px]"
          />


          {/* Loading camera */}
          {isStarting && (

            <div className="absolute inset-0 bg-black/70 flex items-center justify-center">

              <LoadingSpinner
                text="Starting camera..."
              />

            </div>
          )}


          {/* Side label */}
          {!isStarting && (

            <div className="absolute top-4 left-1/2 -translate-x-1/2 bg-black/60 text-white text-sm font-medium px-4 py-1.5 rounded-full backdrop-blur-sm">

              {step === "front"
                ? "Front Side"
                : "Back Side"}

            </div>
          )}
          {/* Auto capture messages */}
{isAutoCapturing && (
  <div className="absolute top-16 left-1/2 -translate-x-1/2 bg-blue-600 text-white text-sm font-medium px-4 py-1.5 rounded-full animate-pulse z-20">
    Card Detected – Capturing...
  </div>
)}

{stableQrFrames > 10 && !isAutoCapturing && (
  <div className="absolute top-16 left-1/2 -translate-x-1/2 bg-green-500 text-white text-sm font-medium px-4 py-1.5 rounded-full z-20">
    Hold steady...
  </div>
)}


          {/* Guide frame */}
          {!isStarting && (

            <div className="absolute inset-0 pointer-events-none flex items-center justify-center">

              <div className="relative w-[88%] h-[62%]">

                <div className="absolute top-0 left-0 w-8 h-8 border-t-[3px] border-l-[3px] border-white rounded-tl-lg" />

                <div className="absolute top-0 right-0 w-8 h-8 border-t-[3px] border-r-[3px] border-white rounded-tr-lg" />

                <div className="absolute bottom-0 left-0 w-8 h-8 border-b-[3px] border-l-[3px] border-white rounded-bl-lg" />

                <div className="absolute bottom-0 right-0 w-8 h-8 border-b-[3px] border-r-[3px] border-white rounded-br-lg" />

              </div>

            </div>
          )}


          {/* Camera controls */}
          {!isStarting && (

            <div className="absolute bottom-6 left-0 right-0 flex justify-center items-center gap-6">

              {/* Switch camera */}
              <button
                onClick={switchCamera}
                className="bg-white/20 hover:bg-white/30 backdrop-blur-md p-3.5 rounded-full"
                type="button"
              >
                <SwitchCamera className="h-5 w-5 text-white" />
              </button>


              {/* Capture */}
              <button
                onClick={capturePhoto}
                className="group relative"
                type="button"
                aria-label={
                  step === "front"
                    ? "Capture front side"
                    : "Capture back side"
                }
              >

                <div className="w-[72px] h-[72px] rounded-full border-[4px] border-white flex items-center justify-center">

                  <div className="w-14 h-14 rounded-full bg-white group-hover:scale-90 transition-transform" />

                </div>

              </button>


              {/* Close camera */}
              <button
                onClick={stopCamera}
                className="bg-white/20 hover:bg-white/30 backdrop-blur-md p-3.5 rounded-full"
                type="button"
              >
                <X className="h-5 w-5 text-white" />
              </button>

            </div>
          )}

        </div>
      )}


      {/* =====================================================
          BOTH CARD SIDES REVIEW
      ===================================================== */}

      {step === "review" &&
        frontPreview && (

          <div className="space-y-6">

            {/* Images */}
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-5">

              {/* FRONT */}
              <div className="relative rounded-xl overflow-hidden border border-gray-200 bg-white shadow-sm">

                <img
                  src={frontPreview}
                  alt="Business card front side"
                  className="w-full h-56 object-contain bg-gray-50"
                />


                <div className="absolute top-3 left-3 bg-black/70 text-white text-xs font-medium px-3 py-1 rounded-full">
                  Front Side
                </div>


                <button
                  onClick={retakeFront}
                  className="absolute top-3 right-3 bg-white p-2 rounded-full shadow-md hover:bg-gray-100"
                  type="button"
                  title="Retake front side"
                >
                  <RotateCcw className="h-4 w-4 text-gray-700" />
                </button>

              </div>


              {/* BACK */}
              <div className="relative rounded-xl overflow-hidden border border-gray-200 bg-white shadow-sm">

                {backPreview ? (
                  <>

                    <img
                      src={backPreview}
                      alt="Business card back side"
                      className="w-full h-56 object-contain bg-gray-50"
                    />


                    <div className="absolute top-3 left-3 bg-black/70 text-white text-xs font-medium px-3 py-1 rounded-full">
                      Back Side
                    </div>


                    <button
                      onClick={retakeBack}
                      className="absolute top-3 right-3 bg-white p-2 rounded-full shadow-md hover:bg-gray-100"
                      type="button"
                      title="Retake back side"
                    >
                      <RotateCcw className="h-4 w-4 text-gray-700" />
                    </button>

                  </>
                ) : (

                  <div className="h-56 flex items-center justify-center bg-gray-50 text-gray-400">
                    No back side captured
                  </div>

                )}

              </div>

            </div>


            {/* Error */}
            {error && (

              <div className="bg-red-50 border border-red-200 text-red-700 text-sm p-4 rounded-xl">
                {error}
              </div>

            )}


            {/* Ready message */}
            {frontFile &&
              backFile && (

                <div className="bg-green-50 border border-green-200 rounded-xl p-4">

                  <div className="flex items-center gap-2 text-green-700 font-medium">

                    <Check className="h-5 w-5" />

                    Both sides are ready

                  </div>


                  <p className="text-sm text-green-600 mt-1">
                    The front and back images will be sent
                    to the backend for VLM extraction.
                  </p>

                </div>
              )}


            {/* Buttons */}
            <div className="flex flex-col sm:flex-row gap-3">

              <Button
                variant="outline"
                className="flex-1"
                onClick={retakeFront}
                disabled={isLoading}
              >
                <RotateCcw className="h-4 w-4 mr-2" />

                Start Over
              </Button>


              <Button
                className="flex-1"
                onClick={handleUpload}
                isLoading={isLoading}
                disabled={
                  !frontFile ||
                  !backFile ||
                  isLoading
                }
              >
                <Upload className="h-4 w-4 mr-2" />

                {isLoading
                  ? "Processing Card..."
                  : "Upload & Scan"}
              </Button>

            </div>

          </div>
        )}


      {/* =====================================================
          PROCESSING MESSAGE
      ===================================================== */}

      {isLoading && (

        <div className="text-center text-sm text-gray-500">

          <p>
            Sending front and back sides to the AI...
          </p>

          <p className="mt-1">
            Extracting business card information.
          </p>

        </div>
      )}

    </div>
  );
}