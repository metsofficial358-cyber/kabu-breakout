"use client";
// 表示設定（上昇・下落色の反転）。localStorage に保存する。
import { createContext, useCallback, useContext, useEffect, useState } from "react";
import { useTheme } from "next-themes";

type ColorMode = "jp" | "inverted";

interface Prefs {
  colorMode: ColorMode;
  toggleColorMode: () => void;
  /** チャート用の実色（テーマと反転設定を反映） */
  colors: { up: string; down: string; grid: string; text: string; border: string; hl: string; bg: string };
}

const PALETTE = {
  light: { up: "#d1242f", down: "#1f6feb", grid: "#eef0f3", text: "#57606a", border: "#d0d7de", hl: "#d97706", bg: "#ffffff" },
  dark: { up: "#ff6b6b", down: "#58a6ff", grid: "#21262d", text: "#8b949e", border: "#30363d", hl: "#f0b429", bg: "#0d1117" },
};

const Ctx = createContext<Prefs | null>(null);
const KEY = "kabu-breakout:colorMode";

export function PrefsProvider({ children }: { children: React.ReactNode }) {
  const [colorMode, setColorMode] = useState<ColorMode>("jp");
  const { resolvedTheme } = useTheme();

  useEffect(() => {
    try {
      if (localStorage.getItem(KEY) === "inverted") setColorMode("inverted");
    } catch {
      /* 保存領域が使えなくても既定で動かす */
    }
  }, []);

  useEffect(() => {
    document.documentElement.dataset.colors = colorMode;
    try {
      localStorage.setItem(KEY, colorMode);
    } catch {
      /* noop */
    }
  }, [colorMode]);

  const toggleColorMode = useCallback(() => setColorMode((m) => (m === "jp" ? "inverted" : "jp")), []);
  const base = PALETTE[resolvedTheme === "dark" ? "dark" : "light"];
  const colors = colorMode === "jp" ? base : { ...base, up: base.down, down: base.up };

  return <Ctx.Provider value={{ colorMode, toggleColorMode, colors }}>{children}</Ctx.Provider>;
}

export function usePrefs(): Prefs {
  const v = useContext(Ctx);
  if (!v) throw new Error("PrefsProvider がありません");
  return v;
}
