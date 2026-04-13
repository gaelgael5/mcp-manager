import { useState, useEffect } from "react";
import { useCurrentUser } from "../api/auth";
import { useLanguages } from "../api/languages";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../api/client";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";
import { useTranslation } from "../i18n";

const AVATAR_PLATFORMS = [
  { name: "DiceBear Playground", url: "https://www.dicebear.com/playground/", description: "Personnalisez un avatar parmi 15+ styles, copiez l'URL API" },
  { name: "Gravatar", url: "https://gravatar.com/", description: "Uploadez votre photo, utilisez l'URL gravatar" },
  { name: "Multiavatar", url: "https://multiavatar.com/", description: "Entrez un texte, clic droit > copier l'adresse de l'image" },
  { name: "Robohash", url: "https://robohash.org/", description: "Entrez un texte dans l'URL, copiez l'adresse" },
  { name: "UI Avatars", url: "https://ui-avatars.com/", description: "Initiales auto-generees, construisez l'URL avec vos parametres" },
];

function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { pseudo?: string; avatar_url?: string; language?: string }) =>
      apiFetch<{ pseudo: string; avatar_url: string; language: string }>("/auth/profile", {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["auth"] }),
  });
}

export function ProfilePage() {
  const { t } = useTranslation();
  const { data: user } = useCurrentUser();
  const { data: languages = [] } = useLanguages();
  const updateProfile = useUpdateProfile();

  const [pseudo, setPseudo] = useState("");
  const [avatarUrl, setAvatarUrl] = useState("");
  const [language, setLanguage] = useState("en");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (user?.pseudo) setPseudo(user.pseudo);
    else if (user?.name) setPseudo(user.name);
  }, [user?.pseudo, user?.name]);

  useEffect(() => {
    if (user?.avatar_url) setAvatarUrl(user.avatar_url);
  }, [user?.avatar_url]);

  useEffect(() => {
    if (user?.language) setLanguage(user.language);
  }, [user?.language]);

  if (!user?.authenticated) {
    return <div className="text-center py-16 text-gray-500">{t("pages.profile.loginRequiredMessage")}</div>;
  }

  const handleSave = () => {
    setSaved(false);
    updateProfile.mutate(
      { pseudo: pseudo.trim() || undefined, avatar_url: avatarUrl.trim() || undefined, language },
      { onSuccess: () => setSaved(true) },
    );
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">{t("pages.profile.title")}</h1>

      <Card title={t("pages.profile.pseudoLabel")}>
        <input
          type="text"
          value={pseudo}
          onChange={(e) => setPseudo(e.target.value)}
          placeholder={t("pages.profile.pseudoPlaceholder")}
          className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
      </Card>

      <Card title={t("pages.profile.languageLabel")}>
        <select
          value={language}
          onChange={(e) => setLanguage(e.target.value)}
          className="w-full max-w-xs rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        >
          {languages.filter((l) => l.is_active).map((l) => (
            <option key={l.code} value={l.code}>{l.name} ({l.code})</option>
          ))}
        </select>
        <p className="text-xs text-gray-400 mt-2">{t("pages.profile.languageHint")}</p>
      </Card>

      <Card title={t("pages.profile.avatarTitle")}>
        <div className="space-y-4">
          <div className="flex items-start gap-6">
            <div className="flex-shrink-0">
              {avatarUrl ? (
                <img
                  src={avatarUrl}
                  alt="Avatar"
                  className="w-20 h-20 rounded-full border-2 border-gray-200 bg-gray-50 object-cover"
                  onError={(e) => { (e.target as HTMLImageElement).src = `https://ui-avatars.com/api/?name=${encodeURIComponent(pseudo || "?")}&size=80&background=random`; }}
                />
              ) : (
                <div className="w-20 h-20 rounded-full bg-gray-100 flex items-center justify-center text-gray-400 text-sm">
                  ?
                </div>
              )}
            </div>
            <div className="flex-1">
              <label className="block text-xs text-gray-500 mb-1">{t("pages.profile.avatarUrlLabel")}</label>
              <input
                type="url"
                value={avatarUrl}
                onChange={(e) => setAvatarUrl(e.target.value)}
                placeholder="https://..."
                className="w-full rounded border border-gray-300 px-3 py-2 text-sm font-mono focus:outline-none focus:ring-2 focus:ring-blue-400"
              />
              <p className="text-xs text-gray-400 mt-1">{t("pages.profile.avatarUrlHint")}</p>
            </div>
          </div>

          <div>
            <p className="text-xs text-gray-500 font-medium mb-2">{t("pages.profile.avatarPlatformsTitle")}</p>
            <div className="space-y-2">
              {AVATAR_PLATFORMS.map((p) => (
                <a
                  key={p.name}
                  href={p.url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="flex items-center gap-3 rounded border border-gray-100 bg-gray-50 px-3 py-2 hover:bg-blue-50 hover:border-blue-200 transition-colors"
                >
                  <span className="text-sm font-medium text-blue-600">{p.name}</span>
                  <span className="text-xs text-gray-400">{p.description}</span>
                  <span className="ml-auto text-gray-300">&#8599;</span>
                </a>
              ))}
            </div>
          </div>
        </div>
      </Card>

      <div className="flex items-center gap-3">
        <Button onClick={handleSave} loading={updateProfile.isPending}>
          {saved ? t("common.buttons.saved") : t("common.buttons.save")}
        </Button>
        {updateProfile.isError && (
          <span className="text-sm text-red-500">{(updateProfile.error as Error).message}</span>
        )}
      </div>
    </div>
  );
}
