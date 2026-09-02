"use client";

import { useEffect, useState } from "react";
import { usePathname, useRouter } from "next/navigation";

export default function AuthGuard({
  children,
}: {
  children: React.ReactNode;
}) {
  const router = useRouter();
  const pathname = usePathname();

  const [checking, setChecking] = useState(true);

  useEffect(() => {
    const publicPages = ["/login", "/signup"];

    // Login/signup don't require authentication
    if (publicPages.includes(pathname)) {
      setChecking(false);
      return;
    }

    const currentUser =
      localStorage.getItem("card_scanner_user");

    // No logged-in user
    if (!currentUser) {
      router.replace("/login");
      return;
    }

    setChecking(false);
  }, [pathname, router]);

  if (checking) {
    return (
      <div className="min-h-screen flex items-center justify-center">
        <p className="text-gray-500">
          Loading...
        </p>
      </div>
    );
  }

  return <>{children}</>;
}