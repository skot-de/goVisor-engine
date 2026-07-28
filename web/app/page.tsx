import { redirect } from "next/navigation";

// Kanonische Startansicht — der Explorer lebt unter benannten URLs (/leads …).
export default function Page() {
  redirect("/leads");
}
