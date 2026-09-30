import { pathToFileURL } from "node:url";
import { searchDeals } from "./lib/search.mjs";

function json(body, status) {
  return new Response(JSON.stringify(body), {
    status,
    headers: {
      "content-type": "application/json; charset=utf-8",
      "cache-control": "no-store",
    },
  });
}

export default async function handler(req) {
  const url = new URL(req.url, "https://cheaphub.com");
  const query = url.searchParams.get("q") || "";
  try {
    const body = await searchDeals(query);
    const status = body.httpStatus || 200;
    delete body.httpStatus;
    return json(body, status);
  } catch {
    return json({ error: "The price check failed before it could finish.", results: [], unchecked: [], skipped: [] }, 500);
  }
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href && process.argv[2] === "search") {
  const query = process.argv.slice(3).join(" ");
  const body = await searchDeals(query);
  const status = body.httpStatus || 200;
  delete body.httpStatus;
  process.stdout.write(JSON.stringify(body));
  if (status >= 400) process.exitCode = 1;
}
