"use client";

import React, { useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import Button from "@/components/ui/Button";
import Input from "@/components/ui/Input";
import { ArrowRight } from "lucide-react";
import { signupUser } from "@/services/api";

export default function SignupPage() {
  const router = useRouter();

  const [fullName, setFullName] = useState("");
  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");

  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const handleSignup = async (e: React.FormEvent) => {
    e.preventDefault();

    setIsLoading(true);
    setError(null);

    try {
      const data = await signupUser(
        fullName,
        email,
        password
      );

      console.log("Account created:", data);

      router.push("/login");
    } catch (err) {
      console.error("Signup error:", err);

      if (err instanceof Error) {
        setError(err.message);
      } else {
        setError("Something went wrong");
      }
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div className="min-h-[75vh] flex items-center justify-center">
      <div className="w-full max-w-md">

        {/* Header */}
        <div className="text-center mb-8">
          <div className="w-16 h-16 bg-primary-600 rounded-2xl flex items-center justify-center mx-auto mb-5 shadow-lg shadow-primary-200">
            <svg
              xmlns="http://www.w3.org/2000/svg"
              className="h-8 w-8 text-white"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
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
            Create account
          </h1>

          <p className="text-gray-500 mt-2">
            Start scanning business cards
          </p>
        </div>

        {/* Card */}
        <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-8">

          <form
            onSubmit={handleSignup}
            className="space-y-5"
          >

            <Input
              id="fullName"
              type="text"
              label="Full Name"
              placeholder="John Doe"
              value={fullName}
              onChange={(e) =>
                setFullName(e.target.value)
              }
              required
            />

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

            {/* Error message */}
            {error && (
              <div className="bg-red-50 text-red-600 text-sm p-3 rounded-lg">
                {error}
              </div>
            )}

            <Button
              type="submit"
              className="w-full"
              size="lg"
              isLoading={isLoading}
            >
              Create Account
              <ArrowRight className="h-4 w-4 ml-2" />
            </Button>

          </form>

          <p className="text-center text-sm text-gray-600 mt-6">
            Already have an account?{" "}

            <Link
              href="/login"
              className="text-primary-600 font-semibold hover:underline"
            >
              Sign in
            </Link>
          </p>

        </div>
      </div>
    </div>
  );
}