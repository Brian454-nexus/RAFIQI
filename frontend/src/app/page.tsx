import Link from "next/link";

export default function Home() {
  return (
    <div className="flex min-h-svh items-center justify-center px-6 py-12">
      <div className="w-full max-w-xl space-y-4">
        <div className="space-y-1">
          <h1 className="text-3xl font-semibold tracking-tight">RAFIQI</h1>
          <p className="text-muted-foreground">
            Local JARVIS-style assistant, now with an Agents UI voice interface.
          </p>
        </div>
        <Link
          href="/rafiqi"
          className="bg-primary text-primary-foreground inline-flex items-center justify-center rounded-lg px-4 py-2 text-sm font-medium"
        >
          Open Rafiqi Interface
        </Link>
      </div>
    </div>
  );
}
