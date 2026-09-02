import Link from "next/link";
import { Plus } from "lucide-react";

import CardTable from "@/components/cards/CardTable";
import Button from "@/components/ui/Button";


export default function CardsPage() {
  return (
    <div className="py-6">
      {/* Page Header */}
      <div className="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-4 mb-8">
        <div>
          <h1 className="text-2xl sm:text-3xl font-bold text-gray-900">
            My Business Cards
          </h1>

          <p className="text-gray-600 mt-1">
            All previously uploaded business cards
          </p>
        </div>

        <Link href="/">
          <Button>
            <Plus className="h-4 w-4 mr-2" />
            Add New Card
          </Button>
        </Link>
      </div>

      {/* Cards Table */}
      <CardTable />
    </div>
  );
}