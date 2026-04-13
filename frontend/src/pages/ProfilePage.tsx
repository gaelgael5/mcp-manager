import { useState, useEffect } from "react";
import { useCurrentUser } from "../api/auth";
import { useMutation, useQueryClient } from "@tanstack/react-query";
import { apiFetch } from "../api/client";
import { Card } from "../components/ui/Card";
import { Button } from "../components/ui/Button";

const PLATFORMS = [
  {
    id: "dicebear",
    label: "DiceBear",
    styles: ["avataaars", "bottts", "pixel-art", "identicon", "thumbs", "fun-emoji", "lorelei", "notionists", "open-peeps", "personas"],
    buildUrl: (seed: string, style: string) => `https://api.dicebear.com/9.x/${style}/svg?seed=${encodeURIComponent(seed)}`,
  },
  {
    id: "uiavatars",
    label: "UI Avatars",
    styles: [],
    buildUrl: (seed: string) => `https://ui-avatars.com/api/?name=${encodeURIComponent(seed)}&background=random&size=128&bold=true`,
  },
  {
    id: "robohash",
    label: "Robohash",
    styles: ["set1", "set2", "set3", "set4", "set5"],
    buildUrl: (seed: string, style: string) => `https://robohash.org/${encodeURIComponent(seed)}?set=${style}&size=128x128`,
  },
  {
    id: "multiavatar",
    label: "Multiavatar",
    styles: [],
    buildUrl: (seed: string) => `https://api.multiavatar.com/${encodeURIComponent(seed)}.svg`,
  },
  {
    id: "gravatar",
    label: "Gravatar",
    styles: ["identicon", "monsterid", "wavatar", "retro", "robohash"],
    buildUrl: (_seed: string, style: string, emailHash?: string) =>
      `https://gravatar.com/avatar/${emailHash || "00000000000000000000000000000000"}?d=${style}&s=128`,
  },
];

const STYLE_LABELS: Record<string, string> = {
  set1: "Robots",
  set2: "Monstres",
  set3: "Têtes",
  set4: "Chats",
  set5: "Humains",
  identicon: "Identicon",
  monsterid: "Monstre",
  wavatar: "Wavatar",
  retro: "Retro",
  robohash: "Robot",
};

function useUpdateProfile() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: (body: { pseudo?: string; avatar_url?: string }) =>
      apiFetch<{ pseudo: string; avatar_url: string }>("/auth/profile", {
        method: "PUT",
        body: JSON.stringify(body),
      }),
    onSuccess: () => qc.invalidateQueries({ queryKey: ["auth"] }),
  });
}

export function ProfilePage() {
  const { data: user } = useCurrentUser();
  const updateProfile = useUpdateProfile();

  const [pseudo, setPseudo] = useState("");
  const [platformId, setPlatformId] = useState("dicebear");
  const [style, setStyle] = useState("avataaars");
  const [previewUrl, setPreviewUrl] = useState("");
  const [saved, setSaved] = useState(false);

  useEffect(() => {
    if (user?.pseudo) setPseudo(user.pseudo);
    else if (user?.name) setPseudo(user.name);
  }, [user?.pseudo, user?.name]);

  useEffect(() => {
    if (!pseudo) return;
    const platform = PLATFORMS.find((p) => p.id === platformId);
    if (!platform) return;
    const emailHash = (user as any)?.email
      ? undefined
      : undefined;
    const url = platform.buildUrl(pseudo, style, emailHash);
    setPreviewUrl(url);
  }, [pseudo, platformId, style, user]);

  if (!user?.authenticated) {
    return <div className="text-center py-16 text-gray-500">Connectez-vous pour acceder a votre profil.</div>;
  }

  const platform = PLATFORMS.find((p) => p.id === platformId)!;

  const handleSave = () => {
    setSaved(false);
    updateProfile.mutate(
      { pseudo: pseudo.trim() || undefined, avatar_url: previewUrl || undefined },
      { onSuccess: () => setSaved(true) },
    );
  };

  return (
    <div className="max-w-2xl mx-auto space-y-6">
      <h1 className="text-2xl font-bold">Profil</h1>

      <Card title="Pseudo">
        <input
          type="text"
          value={pseudo}
          onChange={(e) => setPseudo(e.target.value)}
          placeholder="Votre pseudo"
          className="w-full rounded border border-gray-300 px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400"
        />
      </Card>

      <Card title="Avatar">
        <div className="space-y-4">
          {/* Platform tabs */}
          <div className="flex flex-wrap gap-2">
            {PLATFORMS.map((p) => (
              <button
                key={p.id}
                onClick={() => {
                  setPlatformId(p.id);
                  if (p.styles.length > 0) setStyle(p.styles[0]);
                }}
                className={`px-3 py-1.5 rounded-full text-sm font-medium transition-colors ${
                  platformId === p.id
                    ? "bg-blue-600 text-white"
                    : "bg-gray-100 text-gray-600 hover:bg-gray-200"
                }`}
              >
                {p.label}
              </button>
            ))}
          </div>

          {/* Style selector */}
          {platform.styles.length > 0 && (
            <div>
              <label className="block text-xs text-gray-500 mb-2">Style</label>
              <div className="flex flex-wrap gap-2">
                {platform.styles.map((s) => (
                  <button
                    key={s}
                    onClick={() => setStyle(s)}
                    className={`px-2.5 py-1 rounded text-xs font-medium transition-colors ${
                      style === s
                        ? "bg-blue-100 text-blue-700 ring-1 ring-blue-300"
                        : "bg-gray-50 text-gray-600 hover:bg-gray-100"
                    }`}
                  >
                    {STYLE_LABELS[s] || s}
                  </button>
                ))}
              </div>
            </div>
          )}

          {/* Preview */}
          <div className="flex items-center gap-6 pt-2">
            <div className="flex-shrink-0">
              {previewUrl ? (
                <img
                  src={previewUrl}
                  alt="Avatar preview"
                  className="w-24 h-24 rounded-full border-2 border-gray-200 bg-gray-50 object-cover"
                  onError={(e) => { (e.target as HTMLImageElement).style.display = "none"; }}
                />
              ) : (
                <div className="w-24 h-24 rounded-full bg-gray-100 flex items-center justify-center text-gray-400 text-xs">
                  Aucun
                </div>
              )}
            </div>
            <div className="flex-1 min-w-0">
              <p className="text-xs text-gray-400 truncate">{previewUrl}</p>
              <p className="text-sm text-gray-600 mt-1">
                {platformId === "gravatar"
                  ? "Gravatar utilise votre email pour generer l'avatar. Configurez-le sur gravatar.com."
                  : `Genere a partir de votre pseudo "${pseudo}"`}
              </p>
            </div>
          </div>
        </div>
      </Card>

      <div className="flex items-center gap-3">
        <Button onClick={handleSave} loading={updateProfile.isPending}>
          {saved ? "Enregistre !" : "Enregistrer"}
        </Button>
        {updateProfile.isError && (
          <span className="text-sm text-red-500">{(updateProfile.error as Error).message}</span>
        )}
      </div>
    </div>
  );
}
