import UploadTabs from "@/components/upload/UploadTabs";

export default function HomePage() {
  return (
    <div className="py-6">
      {/* Page Header */}
      <div className="text-center mb-10">
        <h1 className="text-3xl sm:text-4xl font-bold text-gray-900 mb-3">
          Business Card Scanner
        </h1>
        <p className="text-gray-600 max-w-xl mx-auto">
          Upload a business card by scanning, PDF, or URL. We will extract the details automatically.
        </p>
      </div>

      {/* Upload Section */}
      <div className="bg-white rounded-2xl shadow-sm border border-gray-200 p-6 sm:p-8">
        <UploadTabs />
      </div>
    </div>
  );
}