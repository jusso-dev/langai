import { Workspace } from "@/components/workspace";
export default async function Page({
  params,
}: {
  params: Promise<{ id: string; section?: string[] }>;
}) {
  const p = await params;
  return <Workspace languageId={p.id} section={p.section?.[0] || "overview"} />;
}
