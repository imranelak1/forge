export function GET() {
  return Response.json(
    { status: "ok", service: "forge-web" },
    { headers: { "Cache-Control": "no-store" } },
  );
}
