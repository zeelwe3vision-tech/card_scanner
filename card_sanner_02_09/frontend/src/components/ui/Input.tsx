"use client";

import React, { useState } from "react";
import { Eye, EyeOff } from "lucide-react";

interface InputProps
  extends React.InputHTMLAttributes<HTMLInputElement> {
  label?: string;
}

export default function Input({
  label,
  type,
  className = "",
  ...props
}: InputProps) {
  const [showPassword, setShowPassword] = useState(false);

  const isPassword = type === "password";

  return (
    <div className="w-full">
      {/* Label */}
      {label && (
        <label
          htmlFor={props.id}
          className="block text-sm font-medium text-gray-700 mb-2"
        >
          {label}
        </label>
      )}

      <div className="relative">
        {/* Input */}
        <input
          {...props}
          type={
            isPassword
              ? showPassword
                ? "text"
                : "password"
              : type
          }
          className={`
            w-full
            px-4 py-3
            border border-gray-300
            rounded-lg
            text-gray-900
            placeholder:text-gray-400
            focus:outline-none
            focus:ring-2
            focus:ring-primary-500
            focus:border-primary-500
            transition
            ${isPassword ? "pr-12" : ""}
            ${className}
          `}
        />

        {/* Password Eye */}
        {isPassword && (
          <button
            type="button"
            onClick={() => setShowPassword(!showPassword)}
            className="
              absolute
              right-3
              top-1/2
              -translate-y-1/2
              text-gray-400
              hover:text-gray-700
              transition-colors
            "
            aria-label={
              showPassword
                ? "Hide password"
                : "Show password"
            }
          >
            {showPassword ? (
              <EyeOff className="w-5 h-5" />
            ) : (
              <Eye className="w-5 h-5" />
            )}
          </button>
        )}
      </div>
    </div>
  );
}