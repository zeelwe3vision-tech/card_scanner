"use client";

import { useEffect, useState } from "react";
import {
  User,
  Mail,
  Clock3,
  CheckCircle2,
  AlertCircle,
  Loader2,
} from "lucide-react";

import {
  getRetention,
  updateRetention,
} from "@/services/api";


interface CurrentUser {
  id: string;
  email: string;
  full_name: string | null;
}

type RetentionDays =
  | 1
  | 7
  | 30
  | null;


const retentionOptions: {
  label: string;
  value: RetentionDays;
  description: string;
}[] = [
  {
    label: "1 Day",
    value: 1,
    description: "Delete after 24 hours",
  },
  {
    label: "7 Days",
    value: 7,
    description: "Keep for one week",
  },
  {
    label: "30 Days",
    value: 30,
    description: "Keep for one month",
  },
  {
    label: "Never",
    value: null,
    description: "Keep until manually deleted",
  },
];


export default function ProfilePage() {
  const [user, setUser] =
    useState<CurrentUser | null>(null);

  const [retentionDays, setRetentionDays] =
    useState<RetentionDays>(null);

  const [isLoadingRetention, setIsLoadingRetention] =
    useState(true);

  const [isSavingRetention, setIsSavingRetention] =
    useState(false);

  const [retentionMessage, setRetentionMessage] =
    useState<string | null>(null);

  const [retentionError, setRetentionError] =
    useState<string | null>(null);


  // =====================================================
  // LOAD PROFILE
  // =====================================================

  useEffect(() => {
    const loadProfile = async () => {
      const storedUser =
        localStorage.getItem("card_scanner_user");

      if (!storedUser) {
        setIsLoadingRetention(false);
        return;
      }

      try {
        const parsedUser: CurrentUser =
          JSON.parse(storedUser);

        setUser(parsedUser);

        const response =
          await getRetention();

        const value =
          response.retention_days;

        if (
          value === 1 ||
          value === 7 ||
          value === 30
        ) {
          setRetentionDays(value);
        } else {
          setRetentionDays(null);
        }

      } catch (error) {
        console.error(
          "Failed to load retention setting:",
          error
        );

        setRetentionError(
          error instanceof Error
            ? error.message
            : "Unable to load retention setting"
        );

      } finally {
        setIsLoadingRetention(false);
      }
    };

    loadProfile();
  }, []);


  // =====================================================
  // UPDATE RETENTION
  // =====================================================

  const handleRetentionChange = async (
    newRetention: RetentionDays
  ) => {
    if (
      newRetention === retentionDays ||
      isSavingRetention
    ) {
      return;
    }

    setIsSavingRetention(true);
    setRetentionMessage(null);
    setRetentionError(null);

    try {
      const response =
        await updateRetention(
          newRetention
        );

      const value =
        response.retention_days;

      if (
        value === 1 ||
        value === 7 ||
        value === 30
      ) {
        setRetentionDays(value);
      } else {
        setRetentionDays(null);
      }

      setRetentionMessage(
        "Retention preference saved."
      );

    } catch (error) {
      console.error(
        "Failed to update retention setting:",
        error
      );

      setRetentionError(
        error instanceof Error
          ? error.message
          : "Unable to update retention setting"
      );

    } finally {
      setIsSavingRetention(false);
    }
  };


  if (!user) {
    return null;
  }


  const firstLetter =
    user.full_name
      ?.charAt(0)
      .toUpperCase() ??
    user.email
      .charAt(0)
      .toUpperCase();


  return (
    <div className="max-w-3xl mx-auto py-10 px-4">

      <div className="bg-white border border-gray-200 rounded-2xl shadow-sm overflow-hidden">

        {/* =====================================================
            PROFILE HEADER
        ===================================================== */}

        <div className="px-8 py-7 border-b border-gray-100">

          <div className="flex items-center gap-5">

            <div className="w-16 h-16 rounded-2xl bg-primary-600 text-white flex items-center justify-center text-2xl font-bold shadow-sm">
              {firstLetter}
            </div>

            <div>
              <h1 className="text-2xl font-bold text-gray-900">
                {user.full_name || "User"}
              </h1>

              <p className="text-sm text-gray-500 mt-1">
                Manage your profile and card preferences
              </p>
            </div>

          </div>

        </div>


        <div className="p-8 space-y-9">

          {/* =====================================================
              ACCOUNT INFORMATION
          ===================================================== */}

          <section>

            <div className="mb-4">

              <h2 className="text-sm font-semibold text-gray-900">
                Account Information
              </h2>

              <p className="text-sm text-gray-500 mt-1">
                Basic information associated with your account.
              </p>

            </div>


            <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">

              {/* Name */}

              <div className="flex items-center gap-4 p-5 bg-gray-50 border border-gray-100 rounded-xl">

                <div className="w-10 h-10 rounded-lg bg-white border border-gray-200 flex items-center justify-center shrink-0">

                  <User className="w-5 h-5 text-gray-500" />

                </div>

                <div className="min-w-0">

                  <p className="text-xs font-medium text-gray-500">
                    Full Name
                  </p>

                  <p className="font-semibold text-gray-900 mt-0.5 truncate">
                    {user.full_name || "Not provided"}
                  </p>

                </div>

              </div>


              {/* Email */}

              <div className="flex items-center gap-4 p-5 bg-gray-50 border border-gray-100 rounded-xl">

                <div className="w-10 h-10 rounded-lg bg-white border border-gray-200 flex items-center justify-center shrink-0">

                  <Mail className="w-5 h-5 text-gray-500" />

                </div>

                <div className="min-w-0">

                  <p className="text-xs font-medium text-gray-500">
                    Email Address
                  </p>

                  <p className="font-semibold text-gray-900 mt-0.5 truncate">
                    {user.email}
                  </p>

                </div>

              </div>

            </div>

          </section>


          {/* =====================================================
              CARD RETENTION
          ===================================================== */}

          <section>

            <div className="rounded-2xl border border-gray-200 overflow-hidden">

              {/* Retention Header */}

              <div className="flex items-start gap-4 p-5 bg-gray-50 border-b border-gray-200">

                <div className="w-10 h-10 rounded-lg bg-primary-50 flex items-center justify-center shrink-0">

                  <Clock3 className="w-5 h-5 text-primary-600" />

                </div>


                <div className="flex-1">

                  <div className="flex items-center justify-between gap-3">

                    <h2 className="font-semibold text-gray-900">
                      Card Auto-Delete
                    </h2>


                    {isSavingRetention && (
                      <div className="flex items-center gap-2 text-xs text-gray-500">

                        <Loader2 className="w-4 h-4 animate-spin" />

                        Saving

                      </div>
                    )}


                    {!isSavingRetention &&
                      retentionMessage && (
                        <div className="flex items-center gap-1.5 text-xs font-medium text-green-600">

                          <CheckCircle2 className="w-4 h-4" />

                          Saved

                        </div>
                      )}

                  </div>


                  <p className="text-sm text-gray-500 mt-1">
                    Choose how long your business cards should remain saved.
                    This preference applies to all cards in your account.
                  </p>

                </div>

              </div>


              {/* Options */}

              <div className="p-5">

                {isLoadingRetention ? (

                  <div className="flex items-center justify-center py-8 text-gray-500">

                    <Loader2 className="w-5 h-5 animate-spin mr-2" />

                    <span className="text-sm">
                      Loading preference...
                    </span>

                  </div>

                ) : (

                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">

                    {retentionOptions.map(
                      (option) => {

                        const isSelected =
                          retentionDays ===
                          option.value;

                        return (
                          <button
                            key={
                              option.value ??
                              "never"
                            }
                            type="button"
                            onClick={() =>
                              handleRetentionChange(
                                option.value
                              )
                            }
                            disabled={
                              isSavingRetention
                            }
                            className={`
                              relative
                              text-left
                              p-4
                              rounded-xl
                              border
                              transition-all
                              duration-200

                              ${
                                isSelected
                                  ? "border-primary-500 bg-primary-50 ring-1 ring-primary-200"
                                  : "border-gray-200 bg-white hover:border-gray-300 hover:bg-gray-50"
                              }

                              ${
                                isSavingRetention
                                  ? "cursor-not-allowed opacity-60"
                                  : "cursor-pointer"
                              }
                            `}
                          >

                            <div className="flex items-start justify-between gap-3">

                              <div>

                                <p
                                  className={`font-semibold ${
                                    isSelected
                                      ? "text-primary-700"
                                      : "text-gray-900"
                                  }`}
                                >
                                  {option.label}
                                </p>

                                <p className="text-xs text-gray-500 mt-1">
                                  {option.description}
                                </p>

                              </div>


                              <div
                                className={`
                                  w-5
                                  h-5
                                  rounded-full
                                  border
                                  flex
                                  items-center
                                  justify-center
                                  shrink-0

                                  ${
                                    isSelected
                                      ? "border-primary-600 bg-primary-600"
                                      : "border-gray-300 bg-white"
                                  }
                                `}
                              >

                                {isSelected && (
                                  <CheckCircle2 className="w-4 h-4 text-white" />
                                )}

                              </div>

                            </div>

                          </button>
                        );
                      }
                    )}

                  </div>

                )}


                {/* Helpful note */}

                <div className="mt-4 p-3 rounded-lg bg-gray-50">

                  <p className="text-xs leading-5 text-gray-500">
                    Changing this preference also updates the expiry
                    period of your existing saved cards.
                  </p>

                </div>


                {/* Error */}

                {retentionError && (
                  <div className="flex items-start gap-2 mt-4 p-3 rounded-lg bg-red-50 border border-red-100">

                    <AlertCircle className="w-4 h-4 text-red-500 mt-0.5 shrink-0" />

                    <p className="text-sm text-red-600">
                      {retentionError}
                    </p>

                  </div>
                )}

              </div>

            </div>

          </section>

        </div>

      </div>

    </div>
  );
}