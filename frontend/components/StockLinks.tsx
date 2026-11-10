import { ExternalLink } from "lucide-react";
import { kabutanUrl, yahooUrl } from "@/lib/format";

/** コード → 株探、アイコン → Yahoo!ファイナンス（別タブ） */
export function CodeLink({ code, className = "" }: { code: string; className?: string }) {
  return (
    <a
      href={kabutanUrl(code)}
      target="_blank"
      rel="noopener noreferrer"
      title="株探で開く"
      className={`tabular font-mono font-semibold text-sky-700 hover:underline dark:text-sky-400 ${className}`}
    >
      {code}
    </a>
  );
}

export function YahooLink({ code }: { code: string }) {
  return (
    <a
      href={yahooUrl(code)}
      target="_blank"
      rel="noopener noreferrer"
      title="Yahoo!ファイナンスで開く"
      aria-label={`${code} を Yahoo!ファイナンスで開く`}
      className="inline-flex shrink-0 text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
    >
      <ExternalLink className="h-3.5 w-3.5" />
    </a>
  );
}
