import Client from "./client";

export const dynamic = "force-static";
export const dynamicParams = true;

export function generateStaticParams() {
  return [];
}

export default function Page({ params }: { params: { code: string } }) {
  return <Client />;
}
