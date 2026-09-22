import { DeliveryDetail } from "@/features/delivery/delivery-details";
export default async function Page({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  return <DeliveryDetail kind="ci" id={id} />;
}
