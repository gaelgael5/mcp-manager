import { createContext, useContext } from "react";
import en from "./en.json";
import fr from "./fr.json";
import es from "./es.json";
import pt from "./pt.json";
import de from "./de.json";
import it from "./it.json";
import ar from "./ar.json";
import zh from "./zh.json";

type TranslationDict = typeof en;

const dictionaries: Record<string, TranslationDict> = {
  en,
  fr: fr as unknown as TranslationDict,
  es: es as unknown as TranslationDict,
  pt: pt as unknown as TranslationDict,
  de: de as unknown as TranslationDict,
  it: it as unknown as TranslationDict,
  ar: ar as unknown as TranslationDict,
  zh: zh as unknown as TranslationDict,
};

export function getDictionary(lang: string): TranslationDict {
  return dictionaries[lang] || en;
}

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
