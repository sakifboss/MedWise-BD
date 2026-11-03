import { getDict } from "@/i18n/server";

export async function HowRankingWorks() {
  const { how } = await getDict();
  return (
    <p className="text-sm text-muted-foreground">
      {how.before}
      <strong className="font-medium text-foreground">{how.same}</strong>
      {how.middle}
      <strong className="font-medium text-foreground">{how.quality}</strong>
      {how.qualityDetail}
      <strong className="font-medium text-foreground">{how.price}</strong>
      {how.after}
    </p>
  );
}
