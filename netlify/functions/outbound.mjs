import { pathToFileURL } from "node:url";
import { resolveOutbound } from "./lib/go.mjs";

export default async function handler(req) {
  const url = new URL(req.url, "https://cheaphub.com");
  const destination = resolveOutbound(url.searchParams.get("u") || "");
  if (!destination) {
    return new Response("That link isn't a product page we can open.", {
      status: 400,
      headers: { "content-type": "text/plain; charset=utf-8", "cache-control": "no-store" },
    });
  }
  return new Response(null, {
    status: 302,
    headers: {
      location: destination,
      "cache-control": "no-store",
    },
  });
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href && process.argv[2] === "redirect") {
  const destination = resolveOutbound(process.argv[3] || "");
  if (!destination) {
    process.stderr.write("deny\n");
    process.exit(2);
  }
  process.stdout.write(destination);
}
