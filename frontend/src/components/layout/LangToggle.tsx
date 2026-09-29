import { Languages } from "lucide-react";

import { Button } from "@/components/ui/button";
import { useI18n } from "@/hooks/useI18n";

export function LangToggle() {
  const { lang, toggleLang, t } = useI18n();
  const ariaLabel = lang === "en" ? t("lang.switchToZh") : t("lang.switchToEn");

  return (
    <Button
      variant="ghost"
      size="sm"
      onClick={toggleLang}
      aria-label={ariaLabel}
      title={ariaLabel}
      className="gap-1 px-2 font-medium"
    >
      <Languages className="size-3.5" />
      {lang === "en" ? "中" : "EN"}
    </Button>
  );
}
