import { CommitDetail } from "@/features/analytics/history-pages";
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <CommitDetail id={id} />;
}
