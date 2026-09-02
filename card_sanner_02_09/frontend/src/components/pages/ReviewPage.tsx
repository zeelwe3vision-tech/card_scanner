import CardReviewForm from "@/components/review/CardReviewForm";

export default function ReviewPage() {
  return (
    <div className="py-6">
      {/* Page Header */}
      <div className="text-center mb-8">
        <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">
          Review Extracted Details
        </h1>
        <p className="text-gray-600 mt-2">
          Please verify the information before saving
        </p>
      </div>

      {/* Review Form */}
      <CardReviewForm />
    </div>
  );
}