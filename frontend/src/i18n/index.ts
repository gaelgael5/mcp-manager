import { createContext, useContext } from "react";
import en from "./en.json";

type TranslationDict = typeof en;

const TranslationContext = createContext<TranslationDict>(en);

export const TranslationProvider = TranslationContext.Provider;

export function useTranslation() {
  const dict = useContext(TranslationContext);

  function t(key: string, params?: Record<string, string | number>): string {
    const parts = key.split(".");
    let value: unknown = dict;
    for (const part of parts) {
      if (value && typeof value === "object" && part in value) {
        value = (value as Record<string, unknown>)[part];
      } else {
        return key;
      }
    }
    if (typeof value !== "string") return key;
    if (!params) return value;
    return value.replace(/\{(\w+)\}/g, (_, k) => String(params[k] ?? `{${k}}`));
  }

  return { t };
}

export { en };
export type { TranslationDict };
