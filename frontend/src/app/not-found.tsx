import Link from "next/link";

import { buttonVariants } from "@/components/ui/button";

export default function NotFound() {
  return (
    <div className="space-y-4 py-10 text-center">
      <h1 className="text-xl font-semibold">Medicine not found</h1>
      <p className="text-muted-foreground">
        We couldn’t find that medicine in our data. Try searching by brand or generic name.
      </p>
      <Link href="/" className={buttonVariants()}>
        Search medicines
      </Link>
    </div>
  );
}
