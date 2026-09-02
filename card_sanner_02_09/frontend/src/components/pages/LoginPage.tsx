"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowRight } from "lucide-react";

import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import { loginUser } from "@/services/api";


export default function LoginPage() {
  const router = useRouter();

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);


  const handleLogin = async (e: React.FormEvent) => {
    e.preventDefault();

    setIsLoading(true);
    setError(null);

    try {
      const data = await loginUser(
        email.trim(),
        password
      );

      console.log("Login successful:", data);

      // Store logged-in user
      localStorage.setItem(
        "card_scanner_user",
        JSON.stringify(data.user)
      );

        // Store logged-in user
      if (data.access_token) {
      localStorage.setItem(
        "card_scanner_token",
        data.access_token
      );
    }

      // Go to application
      router.push("/");

    } catch (err) {
      console.error("Login error:", err);

      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError(
          "Something went wrong. Please try again."
        );
      }

    } finally {
      setIsLoading(false);
    }
  };


  return (
    <div className="min-h-[calc(100vh-140px)] flex items-center justify-center py-8">

      <div className="w-full max-w-md">

        {/* Login Heading */}
        <div className="text-center mb-8">

          <div
            className="
              w-16 h-16
              bg-primary-600
              rounded-2xl
              flex items-center justify-center
              mx-auto mb-5
              shadow-lg shadow-primary-200
            "
          >
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-8 w-8 text-white"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <rect
                width="20"
                height="14"
                x="2"
                y="5"
                rx="2"
              />

              <line
                x1="2"
                x2="22"
                y1="10"
                y2="10"
              />
            </svg>
          </div>


          <h1 className="text-3xl font-bold text-gray-900">
            Welcome back
          </h1>

          <p className="text-gray-500 mt-2">
            Sign in to continue to Card Scanner
          </p>

        </div>


        {/* Login Card */}
        <div
          className="
            bg-white
            rounded-2xl
            shadow-sm
            border border-gray-200
            p-8
          "
        >

          <form
            onSubmit={handleLogin}
            className="space-y-5"
          >

            <Input
              id="email"
              type="email"
              label="Email address"
              placeholder="you@example.com"
              value={email}
              onChange={(e) =>
                setEmail(e.target.value)
              }
              required
            />


            <Input
              id="password"
              type="password"
              label="Password"
              placeholder="••••••••"
              value={password}
              onChange={(e) =>
                setPassword(e.target.value)
              }
              required
            />


            {/* Remember + Forgot */}
            <div className="flex items-center justify-between text-sm">

              <label className="flex items-center gap-2 cursor-pointer">

                <input
                  type="checkbox"
                  className="
                    rounded
                    border-gray-300
                    text-primary-600
                    focus:ring-primary-500
                  "
                />
              </label>

            </div>


            {/* Error */}
            {error && (
              <div
                className="
                  bg-red-50
                  border border-red-100
                  text-red-600
                  text-sm
                  p-3
                  rounded-lg
                "
              >
                {error}
              </div>
            )}


            {/* Login Button */}
            <Button
              type="submit"
              className="w-full"
              size="lg"
              isLoading={isLoading}
            >
              Sign In

              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>

          </form>


          {/* Divider */}
          <div className="relative my-7">

            <div className="absolute inset-0 flex items-center">
              <div className="w-full border-t border-gray-200" />
            </div>

            <div className="relative flex justify-center text-sm">
              <span className="px-4 bg-white text-gray-400">
                or
              </span>
            </div>

          </div>


          {/* Signup */}
          <p className="text-center text-sm text-gray-600">

            Don&apos;t have an account?{" "}

            <Link
              href="/signup"
              className="
                text-primary-600
                font-semibold
                hover:underline
              "
            >
              Create account
            </Link>

          </p>

        </div>

      </div>

    </div>
  );
}