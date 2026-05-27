import http from "node:http";
import fs from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";

const root = path.resolve(path.dirname(fileURLToPath(import.meta.url)), "..", "out");
const port = Number(process.env.PORT || 4143);
const host = process.env.HOSTNAME || "0.0.0.0";

const contentTypes = new Map([
  [".css", "text/css; charset=utf-8"],
  [".html", "text/html; charset=utf-8"],
  [".ico", "image/x-icon"],
  [".js", "text/javascript; charset=utf-8"],
  [".json", "application/json; charset=utf-8"],
  [".svg", "image/svg+xml"],
  [".txt", "text/plain; charset=utf-8"],
  [".wasm", "application/wasm"],
  [".webmanifest", "application/manifest+json"],
]);

function resolveRequest(url) {
  const pathname = decodeURIComponent(new URL(url, `http://${host}:${port}`).pathname);
  const cleanPath = pathname.replace(/^\/+/, "");
  const candidates = [];

  if (pathname === "/") {
    candidates.push(path.join(root, "dashboard", "index.html"));
  }

  candidates.push(path.join(root, cleanPath));
  candidates.push(path.join(root, cleanPath, "index.html"));
  candidates.push(path.join(root, `${cleanPath}.html`));

  return candidates.find((candidate) => {
    const relative = path.relative(root, candidate);
    return relative && !relative.startsWith("..") && fs.existsSync(candidate) && fs.statSync(candidate).isFile();
  });
}

const server = http.createServer((req, res) => {
  const filePath = resolveRequest(req.url || "/");

  if (!filePath) {
    res.writeHead(404, { "content-type": "text/plain; charset=utf-8" });
    res.end("Not found");
    return;
  }

  const ext = path.extname(filePath);
  res.writeHead(200, {
    "cache-control": filePath.includes(`${path.sep}_next${path.sep}`) ? "public, max-age=31536000, immutable" : "no-cache",
    "content-type": contentTypes.get(ext) || "application/octet-stream",
  });
  fs.createReadStream(filePath).pipe(res);
});

server.listen(port, host, () => {
  console.log(`Relic demo static UI listening on http://${host}:${port}`);
});
